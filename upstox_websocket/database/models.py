"""
Queen Cockpit - Database Models and Setup
SQLite database for signals, trades, positions, and history

Version: 1.0
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
import json
import logging

logger = logging.getLogger("queen.database")


# ============================================
# Enums
# ============================================

class SignalStatus(str, Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class TradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    PARTIAL = "partial"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class Timeframe(str, Enum):
    SCALP = "scalp"
    INTRADAY = "intraday"
    BTST = "btst"
    SWING = "swing"
    POSITIONAL = "positional"
    INVESTMENT = "investment"


class PositionCategory(str, Enum):
    CORE = "core"
    SWING = "swing"
    TACTICAL = "tactical"


# ============================================
# Data Classes
# ============================================

@dataclass
class Signal:
    """Trading signal"""
    id: Optional[int] = None
    symbol: str = ""
    instrument_key: str = ""
    timeframe: str = ""
    direction: str = ""
    action: str = ""
    score: float = 0.0
    entry_price: float = 0.0
    target_price: float = 0.0
    target2_price: Optional[float] = None
    stop_loss: float = 0.0
    risk_pct: float = 0.0
    reward_pct: float = 0.0
    rr_ratio: str = ""
    wyckoff_phase: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    technicals: Optional[Dict] = None
    fo_sentiment: Optional[Dict] = None
    context: Optional[List[Dict]] = None
    confidence: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    triggered_at: Optional[datetime] = None
    status: str = SignalStatus.ACTIVE.value


@dataclass
class Trade:
    """Trade record"""
    id: Optional[int] = None
    symbol: str = ""
    instrument_key: str = ""
    direction: str = ""
    entry_price: float = 0.0
    exit_price: Optional[float] = None
    quantity: int = 0
    entry_time: datetime = field(default_factory=datetime.now)
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    charges: float = 0.0
    net_pnl: float = 0.0
    timeframe: str = ""
    strategy: str = ""
    signal_id: Optional[int] = None
    notes: str = ""
    status: str = TradeStatus.OPEN.value


@dataclass
class Position:
    """Portfolio position"""
    id: Optional[int] = None
    symbol: str = ""
    instrument_key: str = ""
    avg_cost: float = 0.0
    quantity: int = 0
    current_price: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    weight_pct: float = 0.0
    category: str = PositionCategory.TACTICAL.value
    entry_date: datetime = field(default_factory=datetime.now)
    trail_sl: Optional[float] = None
    target: Optional[float] = None
    notes: str = ""
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class WatchlistItem:
    """Watchlist entry"""
    id: Optional[int] = None
    symbol: str = ""
    instrument_key: str = ""
    added_at: datetime = field(default_factory=datetime.now)
    notes: str = ""
    alerts: Optional[Dict] = None


# ============================================
# Database Manager
# ============================================

class QueenDatabase:
    """
    SQLite database manager for Queen Cockpit.

    Usage:
        db = QueenDatabase("queen.db")
        db.init()

        # Add signal
        signal = Signal(symbol="RELIANCE", ...)
        signal_id = db.add_signal(signal)

        # Get active signals
        signals = db.get_active_signals(timeframe="scalp")
    """

    # Schema version for migrations
    SCHEMA_VERSION = 1

    def __init__(self, db_path: str = "queen.db"):
        """Initialize database connection"""
        self.db_path = Path(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection (create if needed)"""
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
            )
            self._conn.row_factory = sqlite3.Row
            # Enable foreign keys
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def close(self):
        """Close database connection"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def init(self):
        """Initialize database schema"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Signals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                instrument_key TEXT,
                timeframe TEXT NOT NULL,
                direction TEXT NOT NULL,
                action TEXT,
                score REAL DEFAULT 0,
                entry_price REAL,
                target_price REAL,
                target2_price REAL,
                stop_loss REAL,
                risk_pct REAL,
                reward_pct REAL,
                rr_ratio TEXT,
                wyckoff_phase TEXT,
                tags TEXT,
                technicals TEXT,
                fo_sentiment TEXT,
                context TEXT,
                confidence REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                triggered_at TIMESTAMP,
                status TEXT DEFAULT 'active',
                UNIQUE(symbol, timeframe, created_at)
            )
        """)

        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                instrument_key TEXT,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                quantity INTEGER NOT NULL,
                entry_time TIMESTAMP NOT NULL,
                exit_time TIMESTAMP,
                pnl REAL DEFAULT 0,
                pnl_pct REAL DEFAULT 0,
                charges REAL DEFAULT 0,
                net_pnl REAL DEFAULT 0,
                timeframe TEXT,
                strategy TEXT,
                signal_id INTEGER,
                notes TEXT,
                status TEXT DEFAULT 'open',
                FOREIGN KEY (signal_id) REFERENCES signals(id)
            )
        """)

        # Positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                instrument_key TEXT,
                avg_cost REAL NOT NULL,
                quantity INTEGER NOT NULL,
                current_price REAL,
                pnl REAL DEFAULT 0,
                pnl_pct REAL DEFAULT 0,
                weight_pct REAL DEFAULT 0,
                category TEXT DEFAULT 'tactical',
                entry_date TIMESTAMP,
                trail_sl REAL,
                target REAL,
                notes TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Watchlist table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                instrument_key TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                alerts TEXT
            )
        """)

        # Trade history stats (aggregated)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL UNIQUE,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                max_win REAL DEFAULT 0,
                max_loss REAL DEFAULT 0,
                avg_win REAL DEFAULT 0,
                avg_loss REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                profit_factor REAL DEFAULT 0
            )
        """)

        # Settings/config table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_timeframe ON signals(timeframe)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol)")

        # Set schema version
        cursor.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("schema_version", str(self.SCHEMA_VERSION))
        )

        conn.commit()
        logger.info(f"Database initialized: {self.db_path}")

    # ==================== Signals ====================

    def add_signal(self, signal: Signal) -> int:
        """Add a new signal"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO signals (
                symbol, instrument_key, timeframe, direction, action, score,
                entry_price, target_price, target2_price, stop_loss,
                risk_pct, reward_pct, rr_ratio, wyckoff_phase,
                tags, technicals, fo_sentiment, context, confidence,
                created_at, expires_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal.symbol, signal.instrument_key, signal.timeframe,
            signal.direction, signal.action, signal.score,
            signal.entry_price, signal.target_price, signal.target2_price,
            signal.stop_loss, signal.risk_pct, signal.reward_pct,
            signal.rr_ratio, signal.wyckoff_phase,
            json.dumps(signal.tags) if signal.tags else None,
            json.dumps(signal.technicals) if signal.technicals else None,
            json.dumps(signal.fo_sentiment) if signal.fo_sentiment else None,
            json.dumps(signal.context) if signal.context else None,
            signal.confidence, signal.created_at, signal.expires_at, signal.status
        ))

        conn.commit()
        return cursor.lastrowid

    def get_signal(self, signal_id: int) -> Optional[Signal]:
        """Get signal by ID"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM signals WHERE id = ?", (signal_id,))
        row = cursor.fetchone()

        if row:
            return self._row_to_signal(row)
        return None

    def get_active_signals(
        self,
        timeframe: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Signal]:
        """Get active signals with optional filters"""
        conn = self._get_conn()
        cursor = conn.cursor()

        query = "SELECT * FROM signals WHERE status = 'active'"
        params = []

        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        query += " ORDER BY score DESC, created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)

        return [self._row_to_signal(row) for row in cursor.fetchall()]

    def update_signal_status(
        self,
        signal_id: int,
        status: SignalStatus,
        triggered_at: Optional[datetime] = None
    ) -> None:
        """Update signal status"""
        conn = self._get_conn()
        cursor = conn.cursor()

        if triggered_at:
            cursor.execute(
                "UPDATE signals SET status = ?, triggered_at = ? WHERE id = ?",
                (status.value, triggered_at, signal_id)
            )
        else:
            cursor.execute(
                "UPDATE signals SET status = ? WHERE id = ?",
                (status.value, signal_id)
            )

        conn.commit()

    def expire_old_signals(self) -> int:
        """Mark expired signals as expired"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE signals
            SET status = 'expired'
            WHERE status = 'active'
            AND expires_at IS NOT NULL
            AND expires_at < ?
        """, (datetime.now(),))

        count = cursor.rowcount
        conn.commit()

        if count:
            logger.info(f"Expired {count} signals")

        return count

    def _row_to_signal(self, row: sqlite3.Row) -> Signal:
        """Convert database row to Signal object"""
        return Signal(
            id=row["id"],
            symbol=row["symbol"],
            instrument_key=row["instrument_key"],
            timeframe=row["timeframe"],
            direction=row["direction"],
            action=row["action"],
            score=row["score"] or 0,
            entry_price=row["entry_price"] or 0,
            target_price=row["target_price"] or 0,
            target2_price=row["target2_price"],
            stop_loss=row["stop_loss"] or 0,
            risk_pct=row["risk_pct"] or 0,
            reward_pct=row["reward_pct"] or 0,
            rr_ratio=row["rr_ratio"] or "",
            wyckoff_phase=row["wyckoff_phase"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            technicals=json.loads(row["technicals"]) if row["technicals"] else None,
            fo_sentiment=json.loads(row["fo_sentiment"]) if row["fo_sentiment"] else None,
            context=json.loads(row["context"]) if row["context"] else None,
            confidence=row["confidence"] or 0,
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            triggered_at=row["triggered_at"],
            status=row["status"],
        )

    # ==================== Trades ====================

    def add_trade(self, trade: Trade) -> int:
        """Add a new trade"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO trades (
                symbol, instrument_key, direction, entry_price, exit_price,
                quantity, entry_time, exit_time, pnl, pnl_pct, charges, net_pnl,
                timeframe, strategy, signal_id, notes, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.symbol, trade.instrument_key, trade.direction,
            trade.entry_price, trade.exit_price, trade.quantity,
            trade.entry_time, trade.exit_time, trade.pnl, trade.pnl_pct,
            trade.charges, trade.net_pnl, trade.timeframe, trade.strategy,
            trade.signal_id, trade.notes, trade.status
        ))

        conn.commit()
        return cursor.lastrowid

    def close_trade(
        self,
        trade_id: int,
        exit_price: float,
        exit_time: Optional[datetime] = None,
        charges: float = 0
    ) -> None:
        """Close an open trade"""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Get current trade
        cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        row = cursor.fetchone()

        if not row:
            raise ValueError(f"Trade {trade_id} not found")

        # Calculate P&L
        entry_price = row["entry_price"]
        quantity = row["quantity"]
        direction = row["direction"]

        if direction == Direction.LONG.value:
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity

        pnl_pct = (pnl / (entry_price * quantity)) * 100 if entry_price else 0
        net_pnl = pnl - charges

        exit_time = exit_time or datetime.now()

        cursor.execute("""
            UPDATE trades SET
                exit_price = ?,
                exit_time = ?,
                pnl = ?,
                pnl_pct = ?,
                charges = ?,
                net_pnl = ?,
                status = 'closed'
            WHERE id = ?
        """, (exit_price, exit_time, pnl, pnl_pct, charges, net_pnl, trade_id))

        conn.commit()
        logger.info(f"Closed trade {trade_id}: P&L = ₹{pnl:.2f} ({pnl_pct:+.2f}%)")

    def get_open_trades(self, symbol: Optional[str] = None) -> List[Trade]:
        """Get open trades"""
        conn = self._get_conn()
        cursor = conn.cursor()

        if symbol:
            cursor.execute(
                "SELECT * FROM trades WHERE status = 'open' AND symbol = ? ORDER BY entry_time DESC",
                (symbol,)
            )
        else:
            cursor.execute(
                "SELECT * FROM trades WHERE status = 'open' ORDER BY entry_time DESC"
            )

        return [self._row_to_trade(row) for row in cursor.fetchall()]

    def get_trade_history(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Trade]:
        """Get trade history"""
        conn = self._get_conn()
        cursor = conn.cursor()

        query = "SELECT * FROM trades WHERE status = 'closed'"
        params = []

        if start_date:
            query += " AND exit_time >= ?"
            params.append(start_date)

        if end_date:
            query += " AND exit_time <= ?"
            params.append(end_date)

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        query += " ORDER BY exit_time DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)

        return [self._row_to_trade(row) for row in cursor.fetchall()]

    def _row_to_trade(self, row: sqlite3.Row) -> Trade:
        """Convert database row to Trade object"""
        return Trade(
            id=row["id"],
            symbol=row["symbol"],
            instrument_key=row["instrument_key"],
            direction=row["direction"],
            entry_price=row["entry_price"],
            exit_price=row["exit_price"],
            quantity=row["quantity"],
            entry_time=row["entry_time"],
            exit_time=row["exit_time"],
            pnl=row["pnl"] or 0,
            pnl_pct=row["pnl_pct"] or 0,
            charges=row["charges"] or 0,
            net_pnl=row["net_pnl"] or 0,
            timeframe=row["timeframe"],
            strategy=row["strategy"],
            signal_id=row["signal_id"],
            notes=row["notes"] or "",
            status=row["status"],
        )

    # ==================== Positions ====================

    def add_or_update_position(self, position: Position) -> int:
        """Add or update a position"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO positions (
                symbol, instrument_key, avg_cost, quantity, current_price,
                pnl, pnl_pct, weight_pct, category, entry_date, trail_sl, target, notes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                avg_cost = excluded.avg_cost,
                quantity = excluded.quantity,
                current_price = excluded.current_price,
                pnl = excluded.pnl,
                pnl_pct = excluded.pnl_pct,
                weight_pct = excluded.weight_pct,
                category = excluded.category,
                trail_sl = excluded.trail_sl,
                target = excluded.target,
                notes = excluded.notes,
                updated_at = excluded.updated_at
        """, (
            position.symbol, position.instrument_key, position.avg_cost,
            position.quantity, position.current_price, position.pnl, position.pnl_pct,
            position.weight_pct, position.category, position.entry_date,
            position.trail_sl, position.target, position.notes, datetime.now()
        ))

        conn.commit()
        return cursor.lastrowid

    def get_positions(self, category: Optional[str] = None) -> List[Position]:
        """Get all positions or by category"""
        conn = self._get_conn()
        cursor = conn.cursor()

        if category:
            cursor.execute(
                "SELECT * FROM positions WHERE category = ? ORDER BY pnl_pct DESC",
                (category,)
            )
        else:
            cursor.execute("SELECT * FROM positions ORDER BY weight_pct DESC")

        return [self._row_to_position(row) for row in cursor.fetchall()]

    def update_position_prices(self, prices: Dict[str, float]) -> None:
        """Batch update position current prices and P&L"""
        conn = self._get_conn()
        cursor = conn.cursor()

        for symbol, price in prices.items():
            cursor.execute("""
                UPDATE positions SET
                    current_price = ?,
                    pnl = (? - avg_cost) * quantity,
                    pnl_pct = ((? - avg_cost) / avg_cost) * 100,
                    updated_at = ?
                WHERE symbol = ?
            """, (price, price, price, datetime.now(), symbol))

        conn.commit()

    def remove_position(self, symbol: str) -> None:
        """Remove a position"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
        conn.commit()

    def _row_to_position(self, row: sqlite3.Row) -> Position:
        """Convert database row to Position object"""
        return Position(
            id=row["id"],
            symbol=row["symbol"],
            instrument_key=row["instrument_key"],
            avg_cost=row["avg_cost"],
            quantity=row["quantity"],
            current_price=row["current_price"] or 0,
            pnl=row["pnl"] or 0,
            pnl_pct=row["pnl_pct"] or 0,
            weight_pct=row["weight_pct"] or 0,
            category=row["category"],
            entry_date=row["entry_date"],
            trail_sl=row["trail_sl"],
            target=row["target"],
            notes=row["notes"] or "",
            updated_at=row["updated_at"],
        )

    # ==================== Watchlist ====================

    def add_to_watchlist(self, item: WatchlistItem) -> int:
        """Add item to watchlist"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO watchlist (symbol, instrument_key, added_at, notes, alerts)
            VALUES (?, ?, ?, ?, ?)
        """, (
            item.symbol, item.instrument_key, item.added_at,
            item.notes, json.dumps(item.alerts) if item.alerts else None
        ))

        conn.commit()
        return cursor.lastrowid

    def get_watchlist(self) -> List[WatchlistItem]:
        """Get full watchlist"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM watchlist ORDER BY added_at DESC")

        items = []
        for row in cursor.fetchall():
            items.append(WatchlistItem(
                id=row["id"],
                symbol=row["symbol"],
                instrument_key=row["instrument_key"],
                added_at=row["added_at"],
                notes=row["notes"] or "",
                alerts=json.loads(row["alerts"]) if row["alerts"] else None,
            ))

        return items

    def remove_from_watchlist(self, symbol: str) -> None:
        """Remove from watchlist"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE symbol = ?", (symbol,))
        conn.commit()

    # ==================== Stats ====================

    def get_trade_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Calculate trade statistics"""
        conn = self._get_conn()
        cursor = conn.cursor()

        query = "SELECT * FROM trades WHERE status = 'closed'"
        params = []

        if start_date:
            query += " AND exit_time >= ?"
            params.append(start_date)

        if end_date:
            query += " AND exit_time <= ?"
            params.append(end_date)

        cursor.execute(query, params)
        trades = cursor.fetchall()

        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "total_pnl": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "max_win": 0,
                "max_loss": 0,
            }

        wins = [t["pnl"] for t in trades if t["pnl"] > 0]
        losses = [t["pnl"] for t in trades if t["pnl"] < 0]

        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0

        return {
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "total_pnl": sum(t["pnl"] for t in trades),
            "net_pnl": sum(t["net_pnl"] for t in trades),
            "win_rate": (len(wins) / len(trades) * 100) if trades else 0,
            "avg_win": (total_wins / len(wins)) if wins else 0,
            "avg_loss": (total_losses / len(losses)) if losses else 0,
            "profit_factor": (total_wins / total_losses) if total_losses else 0,
            "max_win": max(wins) if wins else 0,
            "max_loss": min(losses) if losses else 0,
        }

    # ==================== Settings ====================

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting value"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()

        if row:
            try:
                return json.loads(row["value"])
            except (json.JSONDecodeError, TypeError):
                return row["value"]

        return default

    def set_setting(self, key: str, value: Any) -> None:
        """Set a setting value"""
        conn = self._get_conn()
        cursor = conn.cursor()

        value_str = json.dumps(value) if not isinstance(value, str) else value

        cursor.execute("""
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
        """, (key, value_str, datetime.now()))

        conn.commit()


# ============================================
# Global Instance
# ============================================

_db: Optional[QueenDatabase] = None


def get_db() -> QueenDatabase:
    """Get global database instance"""
    global _db
    if _db is None:
        _db = QueenDatabase()
        _db.init()
    return _db


def init_db(db_path: str = "queen.db") -> QueenDatabase:
    """Initialize global database"""
    global _db
    _db = QueenDatabase(db_path)
    _db.init()
    return _db


# ============================================
# Module Exports
# ============================================

EXPORTS = {
    "QueenDatabase": QueenDatabase,
    "Signal": Signal,
    "Trade": Trade,
    "Position": Position,
    "WatchlistItem": WatchlistItem,
    "SignalStatus": SignalStatus,
    "TradeStatus": TradeStatus,
    "Direction": Direction,
    "Timeframe": Timeframe,
    "PositionCategory": PositionCategory,
    "get_db": get_db,
    "init_db": init_db,
}


# ============================================
# CLI Test
# ============================================

if __name__ == "__main__":
    # Test database
    db = QueenDatabase(":memory:")  # In-memory for testing
    db.init()

    # Add a signal
    signal = Signal(
        symbol="RELIANCE",
        instrument_key="NSE_EQ|INE002A01018",
        timeframe="scalp",
        direction="long",
        action="SCALP_LONG",
        score=8.5,
        entry_price=2845,
        target_price=2875,
        stop_loss=2830,
        risk_pct=0.5,
        reward_pct=1.0,
        rr_ratio="1:2",
        wyckoff_phase="accumulation",
        tags=["FVG", "Order Block"],
        confidence=80,
    )

    signal_id = db.add_signal(signal)
    print(f"Added signal: {signal_id}")

    # Get active signals
    signals = db.get_active_signals(timeframe="scalp")
    print(f"Active signals: {len(signals)}")

    # Add a trade
    trade = Trade(
        symbol="RELIANCE",
        direction="long",
        entry_price=2845,
        quantity=10,
        timeframe="scalp",
        signal_id=signal_id,
    )

    trade_id = db.add_trade(trade)
    print(f"Added trade: {trade_id}")

    # Close trade
    db.close_trade(trade_id, exit_price=2875, charges=50)

    # Get stats
    stats = db.get_trade_stats()
    print(f"Trade stats: {stats}")

    # Add position
    position = Position(
        symbol="HDFCBANK",
        avg_cost=1650,
        quantity=20,
        current_price=1720,
        category="core",
    )
    position.pnl = (position.current_price - position.avg_cost) * position.quantity
    position.pnl_pct = ((position.current_price - position.avg_cost) / position.avg_cost) * 100

    db.add_or_update_position(position)

    positions = db.get_positions()
    print(f"Positions: {len(positions)}")
    for p in positions:
        print(f"  {p.symbol}: ₹{p.current_price:.2f} ({p.pnl_pct:+.2f}%)")

    db.close()
    print("Database test complete!")
