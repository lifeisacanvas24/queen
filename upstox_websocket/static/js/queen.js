/**
 * Queen Cockpit - Dashboard JavaScript
 * Version 3.0
 */

// ============================================
// REAL-TIME CLOCK
// ============================================
function updateTime() {
    const now = new Date();
    const timeEl = document.getElementById('currentTime');
    if (timeEl) {
        timeEl.textContent = now.toLocaleTimeString('en-IN', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    }
}

// Update clock every second
updateTime();
setInterval(updateTime, 1000);

// ============================================
// TAB SWITCHING
// ============================================
document.querySelectorAll('.nav-tab').forEach(tab => {
    tab.addEventListener('click', function(e) {
        e.preventDefault();
        const tabId = this.dataset.tab;
        
        // Safety check - ensure tab content exists
        const tabContent = document.getElementById(tabId);
        if (!tabContent) {
            console.warn('Tab content not found:', tabId);
            return;
        }
        
        // Update active tab
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        this.classList.add('active');
        
        // Show corresponding content
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        tabContent.classList.add('active');
        
        // Update URL hash without scrolling
        history.replaceState(null, null, `#${tabId}`);
    });
});

// ============================================
// SUB-FILTER PILLS
// ============================================
document.querySelectorAll('.filter-pill').forEach(pill => {
    pill.addEventListener('click', function() {
        const parent = this.closest('.tab-content');
        if (!parent) return;
        
        const filter = this.dataset.filter;
        
        // Update active pill
        parent.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
        this.classList.add('active');
        
        // Filter cards
        const cards = parent.querySelectorAll('.signal-card');
        cards.forEach(card => {
            if (filter === 'all' || card.dataset.category === filter) {
                card.style.display = 'block';
                // Animate in
                card.style.opacity = '0';
                card.style.transform = 'translateY(10px)';
                setTimeout(() => {
                    card.style.transition = 'all 0.3s ease';
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                }, 50);
            } else {
                card.style.display = 'none';
            }
        });
    });
});

// ============================================
// INITIALIZE FROM URL HASH
// ============================================
function initFromHash() {
    const hash = window.location.hash.slice(1);
    if (hash) {
        const tab = document.querySelector(`.nav-tab[data-tab="${hash}"]`);
        if (tab) {
            tab.click();
        }
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', initFromHash);

// ============================================
// PORTFOLIO/TIMEFRAME SELECT HANDLERS
// ============================================
const portfolioSelect = document.getElementById('portfolioSelect');
const timeframeSelect = document.getElementById('timeframeSelect');

if (portfolioSelect) {
    portfolioSelect.addEventListener('change', function() {
        // Trigger reload with new portfolio filter
        const url = new URL(window.location);
        url.searchParams.set('portfolio', this.value);
        window.location.href = url.toString();
    });
}

if (timeframeSelect) {
    timeframeSelect.addEventListener('change', function() {
        // Trigger reload with new timeframe
        const url = new URL(window.location);
        url.searchParams.set('timeframe', this.value);
        window.location.href = url.toString();
    });
}

// ============================================
// WEBSOCKET CONNECTION (FOR REAL-TIME UPDATES)
// ============================================
class QueenWebSocket {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
    }
    
    connect() {
        try {
            this.ws = new WebSocket(this.url);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                this.updateConnectionStatus(true);
            };
            
            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.updateConnectionStatus(false);
                this.reconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        } catch (error) {
            console.error('WebSocket connection failed:', error);
        }
    }
    
    reconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Reconnecting... Attempt ${this.reconnectAttempts}`);
            setTimeout(() => this.connect(), this.reconnectDelay);
        }
    }
    
    handleMessage(data) {
        switch (data.type) {
            case 'price_update':
                this.updatePrice(data.symbol, data.price, data.change);
                break;
            case 'new_signal':
                this.addNewSignal(data.signal);
                break;
            case 'signal_update':
                this.updateSignal(data.signal);
                break;
            case 'remove_signal':
                this.removeSignal(data.symbol, data.timeframe);
                break;
        }
    }
    
    updatePrice(symbol, price, change) {
        const cards = document.querySelectorAll(`[data-symbol="${symbol}"]`);
        cards.forEach(card => {
            const priceEl = card.querySelector('.current-price');
            const changeEl = card.querySelector('.price-change');
            
            if (priceEl) {
                priceEl.textContent = `₹${price.toLocaleString('en-IN')}`;
            }
            
            if (changeEl) {
                changeEl.className = `price-change ${change >= 0 ? 'up' : 'down'}`;
                changeEl.innerHTML = `
                    <i class="fas fa-caret-${change >= 0 ? 'up' : 'down'}"></i>
                    ${change >= 0 ? '+' : ''}${change.toFixed(2)}%
                `;
            }
        });
    }
    
    addNewSignal(signal) {
        // This would add a new card to the appropriate grid
        console.log('New signal:', signal);
        // Implementation depends on backend response format
    }
    
    updateSignal(signal) {
        // Update existing signal card
        console.log('Update signal:', signal);
    }
    
    removeSignal(symbol, timeframe) {
        // Remove signal card from grid
        const card = document.querySelector(`[data-symbol="${symbol}"][data-timeframe="${timeframe}"]`);
        if (card) {
            card.style.transition = 'all 0.3s ease';
            card.style.opacity = '0';
            card.style.transform = 'scale(0.95)';
            setTimeout(() => card.remove(), 300);
        }
    }
    
    updateConnectionStatus(connected) {
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.querySelector('.status-badge span:nth-child(2)');
        
        if (statusDot) {
            statusDot.classList.toggle('closed', !connected);
        }
        if (statusText) {
            statusText.textContent = connected ? 'Live' : 'Offline';
        }
    }
}

// Initialize WebSocket if URL is provided
// const queenWS = new QueenWebSocket('ws://localhost:8000/ws');
// queenWS.connect();

// ============================================
// UTILITY FUNCTIONS
// ============================================

// Format price with Indian number system
function formatPrice(price) {
    return price.toLocaleString('en-IN', {
        maximumFractionDigits: 2,
        minimumFractionDigits: 2
    });
}

// Format percentage
function formatPercent(value) {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
}

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Export for use in other modules
window.Queen = {
    formatPrice,
    formatPercent,
    debounce
};
