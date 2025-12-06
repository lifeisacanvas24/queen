"""
Queen Cockpit - Upstox WebSocket Service
Market Data Feed V3 Implementation

Connects to Upstox WebSocket for real-time market data.
Broadcasts updates to connected dashboard clients.

Version: 1.0
"""

import asyncio
import json
import logging
from typing import Optional, Dict, List, Set, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import aiohttp
import ssl

try:
    import websockets
    from websockets.client import WebSocketClientProtocol
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    WebSocketClientProtocol = Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("queen.websocket")


class SubscriptionMode(str, Enum):
    """Upstox WebSocket subscription modes"""
    LTPC = "ltpc"              # LTP + Close Price only
    OPTION_GREEKS = "option_greeks"  # Greeks for options
    FULL = "full"              # Full market data (5 levels)
    FULL_D30 = "full_d30"      # Full with 30 depth levels (Plus only)


class MarketStatus(str, Enum):
    """Market segment status"""
    NORMAL_OPEN = "NORMAL_OPEN"
    NORMAL_CLOSE = "NORMAL_CLOSE"
    PRE_OPEN = "PRE_OPEN"
    POST_CLOSE = "POST_CLOSE"


@dataclass
class TickData:
    """Processed tick data structure"""
    instrument_key: str
    symbol: str
    ltp: float
    close_price: float
    change: float
    change_pct: float
    last_trade_time: Optional[datetime] = None
    last_trade_qty: Optional[int] = None
    volume: Optional[int] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    oi: Optional[int] = None
    atp: Optional[float] = None
    bid_price: Optional[float] = None
    bid_qty: Optional[int] = None
    ask_price: Optional[float] = None
    ask_qty: Optional[int] = None
    tbq: Optional[int] = None  # Total buy quantity
    tsq: Optional[int] = None  # Total sell quantity
    # Option Greeks
    delta: Optional[float] = None
    theta: Optional[float] = None
    gamma: Optional[float] = None
    vega: Optional[float] = None
    iv: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MarketInfo:
    """Market segment status info"""
    segment_status: Dict[str, str] = field(default_factory=dict)
    timestamp: Optional[datetime] = None


class UpstoxWebSocketClient:
    """
    Upstox Market Data Feed V3 WebSocket Client

    Features:
    - Automatic reconnection with exponential backoff
    - Subscription management (add/remove instruments)
    - Mode switching (ltpc/full/option_greeks)
    - Heartbeat/ping-pong handling
    - Callback-based tick delivery

    Usage:
        client = UpstoxWebSocketClient(access_token="your_token")

        @client.on_tick
        def handle_tick(tick: TickData):
            print(f"{tick.symbol}: {tick.ltp}")

        await client.connect()
        await client.subscribe(["NSE_EQ|INE002A01018"], mode=SubscriptionMode.FULL)
    """

    # API Endpoints
    AUTH_URL = "https://api.upstox.com/v3/feed/market-data-feed/authorize"

    # Limits (Normal account)
    MAX_CONNECTIONS = 2
    LIMITS = {
        SubscriptionMode.LTPC: {"individual": 5000, "combined": 2000},
        SubscriptionMode.OPTION_GREEKS: {"individual": 3000, "combined": 2000},
        SubscriptionMode.FULL: {"individual": 2000, "combined": 1500},
    }

    def __init__(
        self,
        access_token: str,
        on_tick: Optional[Callable[[TickData], None]] = None,
        on_market_status: Optional[Callable[[MarketInfo], None]] = None,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        auto_reconnect: bool = True,
        max_reconnect_attempts: int = 10,
        reconnect_delay: float = 2.0,
    ):
        """
        Initialize WebSocket client.

        Args:
            access_token: Upstox API access token
            on_tick: Callback for tick data
            on_market_status: Callback for market status updates
            on_connect: Callback on successful connection
            on_disconnect: Callback on disconnection
            on_error: Callback for errors
            auto_reconnect: Enable automatic reconnection
            max_reconnect_attempts: Max reconnection attempts
            reconnect_delay: Base delay between reconnection attempts
        """
        if not HAS_WEBSOCKETS:
            raise ImportError("websockets library required. Install with: pip install websockets")

        self.access_token = access_token
        self._on_tick_callback = on_tick
        self._on_market_status_callback = on_market_status
        self._on_connect_callback = on_connect
        self._on_disconnect_callback = on_disconnect
        self._on_error_callback = on_error

        self.auto_reconnect = auto_reconnect
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_delay = reconnect_delay

        # State
        self._ws: Optional[WebSocketClientProtocol] = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._connected = False
        self._reconnect_count = 0
        self._subscriptions: Dict[SubscriptionMode, Set[str]] = {
            mode: set() for mode in SubscriptionMode
        }
        self._guid_counter = 0
        self._running = False
        self._receive_task: Optional[asyncio.Task] = None

        # Market status cache
        self.market_info: Optional[MarketInfo] = None

        # Instrument key to symbol mapping (for display)
        self._symbol_map: Dict[str, str] = {}

    # ==================== Decorators ====================

    def on_tick(self, callback: Callable[[TickData], None]):
        """Decorator to set tick callback"""
        self._on_tick_callback = callback
        return callback

    def on_market_status(self, callback: Callable[[MarketInfo], None]):
        """Decorator to set market status callback"""
        self._on_market_status_callback = callback
        return callback

    def on_connect(self, callback: Callable[[], None]):
        """Decorator to set connect callback"""
        self._on_connect_callback = callback
        return callback

    def on_disconnect(self, callback: Callable[[str], None]):
        """Decorator to set disconnect callback"""
        self._on_disconnect_callback = callback
        return callback

    def on_error(self, callback: Callable[[Exception], None]):
        """Decorator to set error callback"""
        self._on_error_callback = callback
        return callback

    # ==================== Connection ====================

    def _generate_guid(self) -> str:
        """Generate unique request ID"""
        self._guid_counter += 1
        return f"queen_{self._guid_counter}_{datetime.now().strftime('%H%M%S%f')}"

    async def _get_authorized_url(self) -> str:
        """Get authorized WebSocket URL from Upstox API"""
        if not self._session:
            self._session = aiohttp.ClientSession()

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
        }

        async with self._session.get(self.AUTH_URL, headers=headers) as response:
            if response.status != 200:
                text = await response.text()
                raise ConnectionError(f"Failed to get WebSocket URL: {response.status} - {text}")

            data = await response.json()
            if data.get("status") != "success":
                raise ConnectionError(f"API error: {data}")

            return data["data"]["authorized_redirect_uri"]

    async def connect(self) -> None:
        """Connect to Upstox WebSocket"""
        self._running = True

        try:
            # Get authorized WebSocket URL
            ws_url = await self._get_authorized_url()
            logger.info(f"Connecting to WebSocket...")

            # Create SSL context
            ssl_context = ssl.create_default_context()

            # Connect with follow_redirects
            self._ws = await websockets.connect(
                ws_url,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=5,
            )

            self._connected = True
            self._reconnect_count = 0
            logger.info("WebSocket connected successfully")

            # Notify callback
            if self._on_connect_callback:
                try:
                    self._on_connect_callback()
                except Exception as e:
                    logger.error(f"Error in on_connect callback: {e}")

            # Start receiving messages
            self._receive_task = asyncio.create_task(self._receive_loop())

            # Resubscribe existing subscriptions
            await self._resubscribe_all()

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            if self._on_error_callback:
                self._on_error_callback(e)

            if self.auto_reconnect:
                await self._reconnect()
            else:
                raise

    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff"""
        while self._running and self._reconnect_count < self.max_reconnect_attempts:
            self._reconnect_count += 1
            delay = self.reconnect_delay * (2 ** (self._reconnect_count - 1))
            delay = min(delay, 60)  # Cap at 60 seconds

            logger.info(f"Reconnecting in {delay:.1f}s (attempt {self._reconnect_count}/{self.max_reconnect_attempts})")
            await asyncio.sleep(delay)

            try:
                await self.connect()
                return
            except Exception as e:
                logger.error(f"Reconnection attempt {self._reconnect_count} failed: {e}")

        logger.error("Max reconnection attempts reached")
        if self._on_disconnect_callback:
            self._on_disconnect_callback("max_reconnect_attempts_reached")

    async def disconnect(self) -> None:
        """Disconnect from WebSocket"""
        self._running = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()
            self._ws = None

        if self._session:
            await self._session.close()
            self._session = None

        self._connected = False
        logger.info("WebSocket disconnected")

        if self._on_disconnect_callback:
            self._on_disconnect_callback("user_initiated")

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self._connected and self._ws is not None

    # ==================== Message Handling ====================

    async def _receive_loop(self) -> None:
        """Main message receiving loop"""
        try:
            async for message in self._ws:
                try:
                    # Messages are in JSON format (V3 uses JSON, not protobuf for response)
                    if isinstance(message, bytes):
                        message = message.decode('utf-8')

                    data = json.loads(message)
                    await self._handle_message(data)

                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse message: {e}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    if self._on_error_callback:
                        self._on_error_callback(e)

        except websockets.ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed: {e}")
            self._connected = False

            if self._on_disconnect_callback:
                self._on_disconnect_callback(f"connection_closed: {e.code}")

            if self.auto_reconnect and self._running:
                await self._reconnect()

        except Exception as e:
            logger.error(f"Receive loop error: {e}")
            self._connected = False

            if self._on_error_callback:
                self._on_error_callback(e)

            if self.auto_reconnect and self._running:
                await self._reconnect()

    async def _handle_message(self, data: Dict) -> None:
        """Process incoming WebSocket message"""
        msg_type = data.get("type")

        if msg_type == "market_info":
            # Market status update (first message)
            await self._handle_market_info(data)

        elif msg_type == "live_feed":
            # Live market data
            await self._handle_live_feed(data)

        else:
            logger.debug(f"Unknown message type: {msg_type}")

    async def _handle_market_info(self, data: Dict) -> None:
        """Handle market status message"""
        market_info_data = data.get("marketInfo", {})
        segment_status = market_info_data.get("segmentStatus", {})

        self.market_info = MarketInfo(
            segment_status=segment_status,
            timestamp=datetime.now()
        )

        logger.info(f"Market status received: {segment_status}")

        if self._on_market_status_callback:
            try:
                self._on_market_status_callback(self.market_info)
            except Exception as e:
                logger.error(f"Error in market status callback: {e}")

    async def _handle_live_feed(self, data: Dict) -> None:
        """Handle live market data feed"""
        feeds = data.get("feeds", {})
        current_ts = data.get("currentTs")

        for instrument_key, feed_data in feeds.items():
            if instrument_key == "currentTs":
                continue

            try:
                tick = self._parse_tick(instrument_key, feed_data, current_ts)

                if tick and self._on_tick_callback:
                    try:
                        self._on_tick_callback(tick)
                    except Exception as e:
                        logger.error(f"Error in tick callback: {e}")

            except Exception as e:
                logger.error(f"Error parsing tick for {instrument_key}: {e}")

    def _parse_tick(self, instrument_key: str, feed_data: Dict, current_ts: str) -> Optional[TickData]:
        """Parse feed data into TickData object"""

        # Determine data structure based on content
        ltpc_data = None
        market_ff = None
        first_level = None
        option_greeks = None
        ohlc_data = None

        if "ltpc" in feed_data:
            # Simple LTPC mode
            ltpc_data = feed_data["ltpc"]

        elif "fullFeed" in feed_data:
            # Full feed mode
            market_ff = feed_data["fullFeed"].get("marketFF", {})
            ltpc_data = market_ff.get("ltpc", {})
            option_greeks = market_ff.get("optionGreeks")
            ohlc_data = market_ff.get("marketOHLC", {}).get("ohlc", [])
            # First level depth
            market_level = market_ff.get("marketLevel", {})
            bid_ask_quotes = market_level.get("bidAskQuote", [])
            if bid_ask_quotes:
                first_level = bid_ask_quotes[0]

        elif "firstLevelWithGreeks" in feed_data:
            # Option Greeks mode
            flg = feed_data["firstLevelWithGreeks"]
            ltpc_data = flg.get("ltpc", {})
            option_greeks = flg.get("optionGreeks")
            first_level = flg.get("firstDepth")

        if not ltpc_data:
            return None

        # Extract LTP and close price
        ltp = ltpc_data.get("ltp", 0)
        close_price = ltpc_data.get("cp", ltp)

        # Calculate change
        change = ltp - close_price
        change_pct = (change / close_price * 100) if close_price else 0

        # Parse last trade time
        ltt = None
        if ltpc_data.get("ltt"):
            try:
                ltt = datetime.fromtimestamp(int(ltpc_data["ltt"]) / 1000)
            except (ValueError, TypeError):
                pass

        # Get symbol from mapping or extract from key
        symbol = self._symbol_map.get(
            instrument_key,
            instrument_key.split("|")[-1] if "|" in instrument_key else instrument_key
        )

        # Build TickData
        tick = TickData(
            instrument_key=instrument_key,
            symbol=symbol,
            ltp=ltp,
            close_price=close_price,
            change=change,
            change_pct=change_pct,
            last_trade_time=ltt,
            last_trade_qty=int(ltpc_data.get("ltq", 0)) if ltpc_data.get("ltq") else None,
        )

        # Add full feed data if available
        if market_ff:
            tick.volume = int(market_ff.get("vtt", 0)) if market_ff.get("vtt") else None
            tick.oi = market_ff.get("oi")
            tick.atp = market_ff.get("atp")
            tick.tbq = market_ff.get("tbq")
            tick.tsq = market_ff.get("tsq")
            tick.iv = market_ff.get("iv")

            # OHLC from daily interval
            if ohlc_data:
                for ohlc in ohlc_data:
                    if ohlc.get("interval") == "1d":
                        tick.open = ohlc.get("open")
                        tick.high = ohlc.get("high")
                        tick.low = ohlc.get("low")
                        break

        # Add first level depth
        if first_level:
            tick.bid_price = first_level.get("bidP")
            tick.bid_qty = int(first_level.get("bidQ", 0)) if first_level.get("bidQ") else None
            tick.ask_price = first_level.get("askP")
            tick.ask_qty = int(first_level.get("askQ", 0)) if first_level.get("askQ") else None

        # Add option greeks
        if option_greeks:
            tick.delta = option_greeks.get("delta")
            tick.theta = option_greeks.get("theta")
            tick.gamma = option_greeks.get("gamma")
            tick.vega = option_greeks.get("vega")

        # Parse current timestamp
        if current_ts:
            try:
                tick.timestamp = datetime.fromtimestamp(int(current_ts) / 1000)
            except (ValueError, TypeError):
                tick.timestamp = datetime.now()

        return tick

    # ==================== Subscription Management ====================

    async def subscribe(
        self,
        instrument_keys: List[str],
        mode: SubscriptionMode = SubscriptionMode.LTPC,
        symbol_map: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Subscribe to market data for instruments.

        Args:
            instrument_keys: List of instrument keys (e.g., ["NSE_EQ|INE002A01018"])
            mode: Subscription mode (ltpc/full/option_greeks)
            symbol_map: Optional mapping of instrument_key to display symbol

        Example:
            await client.subscribe(
                ["NSE_EQ|INE002A01018", "NSE_EQ|INE009A01021"],
                mode=SubscriptionMode.FULL,
                symbol_map={"NSE_EQ|INE002A01018": "RELIANCE", "NSE_EQ|INE009A01021": "INFY"}
            )
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to WebSocket")

        # Update symbol map
        if symbol_map:
            self._symbol_map.update(symbol_map)

        # Check limits
        current_count = len(self._subscriptions[mode])
        new_count = len(instrument_keys)
        limit = self.LIMITS[mode]["individual"]

        if current_count + new_count > limit:
            raise ValueError(f"Subscription limit exceeded: {current_count + new_count} > {limit}")

        # Build subscription message (must be sent as binary)
        message = {
            "guid": self._generate_guid(),
            "method": "sub",
            "data": {
                "mode": mode.value,
                "instrumentKeys": instrument_keys
            }
        }

        # Send as binary (V3 requirement)
        await self._ws.send(json.dumps(message).encode('utf-8'))

        # Track subscriptions
        self._subscriptions[mode].update(instrument_keys)

        logger.info(f"Subscribed to {len(instrument_keys)} instruments in {mode.value} mode")

    async def unsubscribe(
        self,
        instrument_keys: List[str],
        mode: Optional[SubscriptionMode] = None,
    ) -> None:
        """
        Unsubscribe from market data.

        Args:
            instrument_keys: List of instrument keys to unsubscribe
            mode: Subscription mode (if None, unsubscribe from all modes)
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to WebSocket")

        message = {
            "guid": self._generate_guid(),
            "method": "unsub",
            "data": {
                "instrumentKeys": instrument_keys
            }
        }

        if mode:
            message["data"]["mode"] = mode.value

        await self._ws.send(json.dumps(message).encode('utf-8'))

        # Update tracking
        if mode:
            self._subscriptions[mode] -= set(instrument_keys)
        else:
            for m in SubscriptionMode:
                self._subscriptions[m] -= set(instrument_keys)

        logger.info(f"Unsubscribed from {len(instrument_keys)} instruments")

    async def change_mode(
        self,
        instrument_keys: List[str],
        new_mode: SubscriptionMode,
    ) -> None:
        """
        Change subscription mode for instruments.

        Args:
            instrument_keys: List of instrument keys
            new_mode: New subscription mode
        """
        if not self.is_connected:
            raise ConnectionError("Not connected to WebSocket")

        message = {
            "guid": self._generate_guid(),
            "method": "change_mode",
            "data": {
                "mode": new_mode.value,
                "instrumentKeys": instrument_keys
            }
        }

        await self._ws.send(json.dumps(message).encode('utf-8'))

        # Update tracking (remove from old modes, add to new)
        for m in SubscriptionMode:
            if m != new_mode:
                self._subscriptions[m] -= set(instrument_keys)
        self._subscriptions[new_mode].update(instrument_keys)

        logger.info(f"Changed mode to {new_mode.value} for {len(instrument_keys)} instruments")

    async def _resubscribe_all(self) -> None:
        """Resubscribe to all tracked instruments after reconnection"""
        for mode, instruments in self._subscriptions.items():
            if instruments:
                message = {
                    "guid": self._generate_guid(),
                    "method": "sub",
                    "data": {
                        "mode": mode.value,
                        "instrumentKeys": list(instruments)
                    }
                }
                await self._ws.send(json.dumps(message).encode('utf-8'))
                logger.info(f"Resubscribed to {len(instruments)} instruments in {mode.value} mode")

    def get_subscriptions(self) -> Dict[str, List[str]]:
        """Get current subscriptions by mode"""
        return {mode.value: list(instruments) for mode, instruments in self._subscriptions.items()}


# ============================================
# Dashboard WebSocket Broadcaster
# ============================================

class DashboardBroadcaster:
    """
    Broadcasts market updates to connected dashboard clients.

    Sits between Upstox WebSocket and dashboard WebSocket clients.
    Aggregates ticks, manages subscriptions per client.
    """

    def __init__(self):
        self._clients: Set = set()
        self._tick_buffer: Dict[str, TickData] = {}
        self._broadcast_interval = 0.5  # seconds
        self._running = False
        self._broadcast_task: Optional[asyncio.Task] = None

    async def add_client(self, websocket) -> None:
        """Add a dashboard client WebSocket"""
        self._clients.add(websocket)
        logger.info(f"Dashboard client connected. Total: {len(self._clients)}")

    async def remove_client(self, websocket) -> None:
        """Remove a dashboard client WebSocket"""
        self._clients.discard(websocket)
        logger.info(f"Dashboard client disconnected. Total: {len(self._clients)}")

    def update_tick(self, tick: TickData) -> None:
        """Buffer a tick for broadcasting"""
        self._tick_buffer[tick.instrument_key] = tick

    async def start(self) -> None:
        """Start the broadcast loop"""
        self._running = True
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())

    async def stop(self) -> None:
        """Stop the broadcast loop"""
        self._running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass

    async def _broadcast_loop(self) -> None:
        """Periodically broadcast buffered ticks to all clients"""
        while self._running:
            await asyncio.sleep(self._broadcast_interval)

            if not self._tick_buffer or not self._clients:
                continue

            # Prepare message
            updates = []
            for tick in self._tick_buffer.values():
                updates.append({
                    "type": "price_update",
                    "symbol": tick.symbol,
                    "instrument_key": tick.instrument_key,
                    "ltp": tick.ltp,
                    "change": tick.change,
                    "change_pct": tick.change_pct,
                    "volume": tick.volume,
                    "oi": tick.oi,
                    "bid": tick.bid_price,
                    "ask": tick.ask_price,
                    "timestamp": tick.timestamp.isoformat() if tick.timestamp else None,
                })

            # Clear buffer
            self._tick_buffer.clear()

            # Broadcast to all clients
            message = json.dumps({"updates": updates})

            dead_clients = set()
            for client in self._clients:
                try:
                    await client.send(message)
                except Exception:
                    dead_clients.add(client)

            # Remove dead clients
            self._clients -= dead_clients


# ============================================
# Factory & Convenience Functions
# ============================================

_upstox_client: Optional[UpstoxWebSocketClient] = None
_broadcaster: Optional[DashboardBroadcaster] = None


async def init_market_feed(access_token: str) -> UpstoxWebSocketClient:
    """
    Initialize global market feed client.

    Args:
        access_token: Upstox API access token

    Returns:
        Configured WebSocket client
    """
    global _upstox_client, _broadcaster

    _broadcaster = DashboardBroadcaster()

    _upstox_client = UpstoxWebSocketClient(
        access_token=access_token,
        on_tick=lambda tick: _broadcaster.update_tick(tick),
    )

    await _upstox_client.connect()
    await _broadcaster.start()

    return _upstox_client


def get_market_feed() -> Optional[UpstoxWebSocketClient]:
    """Get global market feed client"""
    return _upstox_client


def get_broadcaster() -> Optional[DashboardBroadcaster]:
    """Get global dashboard broadcaster"""
    return _broadcaster


# ============================================
# Module Exports
# ============================================

EXPORTS = {
    "UpstoxWebSocketClient": UpstoxWebSocketClient,
    "DashboardBroadcaster": DashboardBroadcaster,
    "TickData": TickData,
    "MarketInfo": MarketInfo,
    "SubscriptionMode": SubscriptionMode,
    "init_market_feed": init_market_feed,
    "get_market_feed": get_market_feed,
    "get_broadcaster": get_broadcaster,
}


# ============================================
# CLI Test
# ============================================

if __name__ == "__main__":
    import os

    async def main():
        token = os.environ.get("UPSTOX_ACCESS_TOKEN")
        if not token:
            print("Set UPSTOX_ACCESS_TOKEN environment variable")
            return

        client = UpstoxWebSocketClient(access_token=token)

        @client.on_tick
        def handle_tick(tick: TickData):
            print(f"{tick.symbol}: ₹{tick.ltp:.2f} ({tick.change_pct:+.2f}%)")

        @client.on_market_status
        def handle_status(info: MarketInfo):
            print(f"Market Status: {info.segment_status}")

        @client.on_connect
        def handle_connect():
            print("Connected!")

        await client.connect()

        # Subscribe to some stocks
        await client.subscribe(
            ["NSE_EQ|INE002A01018", "NSE_EQ|INE009A01021"],
            mode=SubscriptionMode.FULL,
            symbol_map={
                "NSE_EQ|INE002A01018": "RELIANCE",
                "NSE_EQ|INE009A01021": "INFY"
            }
        )

        # Keep running for 60 seconds
        await asyncio.sleep(60)
        await client.disconnect()

    asyncio.run(main())
