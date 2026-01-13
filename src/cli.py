import asyncio
import json
import os
import websockets
import pygame
import time
from textual.app import App, ComposeResult
from textual.widgets import Static, DataTable
from textual.timer import Timer

# Path to your click sound
CLICK_SOUND_PATH = "data/sounds/geiger_click7.wav"

# Coinbase WebSocket URL
COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"

# Constants
TPS_WINDOW = 10  # seconds - window for TPS calculation
MAX_RECENT_TRADES = 1000  # Maximum number of recent trades to keep in memory
MAX_RECONNECT_ATTEMPTS = 5  # Maximum WebSocket reconnection attempts
RECONNECT_DELAY = 5  # seconds - delay between reconnection attempts
BOT_DETECTION_THRESHOLD = 5  # Number of identical trades to trigger bot detection
BOT_BANNER_DURATION = 5  # seconds - how long to show bot banner
TRADES_TABLE_SIZE = 10  # Number of trades to display in table
STATS_REFRESH_INTERVAL = 0.5  # seconds - how often to refresh stats display
ANIMATION_DURATION = 0.5  # seconds - price animation duration

# Store latest stats
stats = {
    "total_trades": 0,
    "last_price": 0.0,
    "volume_today": 0.0,
    "price_change_24h": 0.0,
    "avg_trade_size": 0.0,
    "largest_trade": None,
    "tps": 0.0,
    "highest_tps": 0.0,
}

recent_trades: list[dict] = []  # Keep last N trades (limited to MAX_RECENT_TRADES)
trade_timestamps: list[float] = []  # For TPS calculation
audio_enabled = True
click_sound = None

class PriceWidget(Static):
    """Widget for displaying BTC/USD price with animation effects."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_price: float | None = None
        self.anim_timer: Timer | None = None

    def update_price(self, price: float) -> None:
        """Update the displayed price.
        
        Args:
            price: Current BTC/USD price to display
        """
        # Format price large and centered (markup only uses supported tags)
        self.update(f"\n[bold bright_white on black]BTC/USD[/]\n\n[bold bright_yellow on black]${price:,.2f}[/]")

    def animate(self, direction: str) -> None:
        """Animate price change with color transition.
        
        Args:
            direction: 'up' for price increase (green), 'down' for decrease (red)
        """
        if direction == 'up':
            self.add_class('price-up')
        elif direction == 'down':
            self.add_class('price-down')
        if self.anim_timer:
            self.anim_timer.stop()
        self.anim_timer = self.set_timer(ANIMATION_DURATION, self.reset_animation)

    def reset_animation(self) -> None:
        """Reset price animation classes."""
        self.remove_class('price-up')
        self.remove_class('price-down')

class BTCBeeperApp(App):
    CSS = """
    #price {
        align: center middle;
        height: 6;
        content-align: center middle;
        text-align: center;
        padding: 1 0;
    }
    .price-up {
        background: green;
        color: black;
        transition: background 200ms, color 200ms;
    }
    .price-down {
        background: red;
        color: white;
        transition: background 200ms, color 200ms;
    }
    #stats {
        padding: 0 1;
    }
    #trades {
        padding: 0 1;
    }
    #footer {
        color: $text-muted;
        padding: 0 1;
    }
    #bot-banner {
        dock: bottom;
        height: 2;
        background: yellow;
        color: black;
        text-align: center;
        content-align: center middle;
        padding: 0 1;
        visibility: hidden;
    }
    #bot-banner.active {
        visibility: visible;
        background: orange;
        color: black;
    }
    """
    FILTER_SIZES = [0.0001, 0.001, 0.01, 0.1, 1]
    BINDINGS = [
        ("a", "toggle_audio", "Toggle Audio"),
        ("[", "filter_down", "Decrease Min Trade Size"),
        ("]", "filter_up", "Increase Min Trade Size"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot_banner_timer = None
        self.filter_index = 0  # Start with the smallest filter

    def compose(self) -> ComposeResult:
        self.price_widget = PriceWidget(id="price")
        yield self.price_widget
        self.stats_widget = Static(id="stats")
        yield self.stats_widget
        self.trades_table = DataTable(id="trades")
        self.trades_table.add_columns("Side", "Price", "Size (BTC)")
        yield self.trades_table
        self.bot_banner = Static("", id="bot-banner")
        yield self.bot_banner

    async def on_mount(self) -> None:
        """Initialize the application on mount."""
        self.set_interval(STATS_REFRESH_INTERVAL, self.refresh_stats)
        await self.connect_ws()
        self.last_price: float | None = None

    async def connect_ws(self) -> None:
        async def ws_loop() -> None:
            """Main WebSocket connection loop with reconnection logic."""
            global stats, recent_trades
            reconnect_attempts = 0
            
            while reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
                try:
                    # Subscribe to BTC-USD channels
                    subscribe_message = {
                        "type": "subscribe",
                        "product_ids": ["BTC-USD"],
                        "channels": ["matches", "ticker", "heartbeat"]
                    }
                    
                    async with websockets.connect(COINBASE_WS_URL) as websocket:
                        await websocket.send(json.dumps(subscribe_message))
                        reconnect_attempts = 0  # Reset on successful connection
                        
                        async for message in websocket:
                            try:
                                data = json.loads(message)
                                msg_type = data.get("type", "")
                                
                                # Only process BTC-USD messages
                                if data.get("product_id") not in ["BTC-USD", None]:
                                    continue
                                
                                if msg_type in ["match", "last_match"]:
                                    # Process trade data
                                    min_trade_size = self.get_min_trade_size()
                                    trade_size = float(data.get("size", 0))
                                    
                                    if trade_size < min_trade_size:
                                        continue  # Ignore trades below filter
                                    
                                    trade_data = {
                                        "price": float(data["price"]),
                                        "size": trade_size,
                                        "side": data.get("side", "unknown"),
                                        "timestamp": data.get("time", ""),
                                        "trade_id": str(data.get("trade_id", ""))
                                    }
                                    
                                    stats["total_trades"] += 1
                                    prev_price = stats["last_price"]
                                    stats["last_price"] = trade_data["price"]
                                    stats["volume_today"] += trade_data["size"]
                                    
                                    # Limit recent_trades size to prevent unbounded growth
                                    recent_trades.append(trade_data)
                                    if len(recent_trades) > MAX_RECENT_TRADES:
                                        recent_trades.pop(0)
                                    
                                    trade_timestamps.append(time.time())
                                    self.update_tps()
                                    stats["avg_trade_size"] = stats["volume_today"] / stats["total_trades"] if stats["total_trades"] else 0.0
                                    
                                    if not stats["largest_trade"] or trade_data["size"] > stats["largest_trade"]["size"]:
                                        stats["largest_trade"] = trade_data.copy()
                                    
                                    await self.play_click()
                                    
                                    # Animate price if changed
                                    if prev_price is not None:
                                        if stats["last_price"] > prev_price:
                                            self.price_widget.animate('up')
                                        elif stats["last_price"] < prev_price:
                                            self.price_widget.animate('down')
                                    
                                    self.refresh_stats()
                                    
                                elif msg_type == "ticker":
                                    # Process ticker data
                                    ticker_price = float(data.get("price", 0))
                                    if ticker_price > 0:
                                        stats["last_price"] = ticker_price
                                        
                                        # Calculate 24h price change if we have low_24h
                                        low_24h = data.get("low_24h")
                                        if low_24h and float(low_24h) > 0:
                                            stats["price_change_24h"] = ((ticker_price - float(low_24h)) / float(low_24h)) * 100
                                        
                                        self.refresh_stats()
                                
                                elif msg_type == "error":
                                    # Log errors but continue
                                    error_msg = data.get("message", "Unknown error")
                                    self.stats_widget.update(f"[Error]: {error_msg}")
                                
                            except json.JSONDecodeError:
                                continue  # Skip invalid JSON
                            except (KeyError, ValueError, TypeError) as e:
                                # Log processing errors but continue
                                continue
                                
                except (websockets.exceptions.WebSocketException, ConnectionError, OSError) as e:
                    reconnect_attempts += 1
                    error_msg = f"[Connection Error]: {e}. Reconnecting... ({reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})"
                    self.stats_widget.update(error_msg)
                    if reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
                        await asyncio.sleep(RECONNECT_DELAY)
                    else:
                        self.stats_widget.update("[Connection Failed]: Max reconnection attempts reached. Please restart the application.")
        self.run_worker(ws_loop, exclusive=True)

    def update_tps(self) -> None:
        """Update trades per second (TPS) calculation using rolling window."""
        now = time.time()
        # Remove timestamps outside the window
        while trade_timestamps and now - trade_timestamps[0] > TPS_WINDOW:
            trade_timestamps.pop(0)
        stats['tps'] = len(trade_timestamps) / TPS_WINDOW
        if stats['tps'] > stats['highest_tps']:
            stats['highest_tps'] = stats['tps']

    async def play_click(self) -> None:
        """Play click sound if audio is enabled."""
        if audio_enabled and click_sound:
            click_sound.play()

    def action_toggle_audio(self) -> None:
        """Toggle audio on/off."""
        global audio_enabled
        audio_enabled = not audio_enabled
        self.refresh_stats()

    def action_filter_down(self) -> None:
        """Decrease minimum trade size filter."""
        if self.filter_index > 0:
            self.filter_index -= 1
            self.refresh_stats()

    def action_filter_up(self) -> None:
        """Increase minimum trade size filter."""
        if self.filter_index < len(self.FILTER_SIZES) - 1:
            self.filter_index += 1
            self.refresh_stats()

    def get_min_trade_size(self) -> float:
        """Get the current minimum trade size filter.
        
        Returns:
            Minimum trade size in BTC
        """
        return self.FILTER_SIZES[self.filter_index]

    def refresh_stats(self) -> None:
        """Refresh all displayed statistics and update UI widgets."""
        min_trade_size = self.get_min_trade_size()
        # Update price widget
        self.price_widget.update_price(stats['last_price'])
        # Update stats widget
        lines = [
            f"Total Trades: {stats['total_trades']}",
            f"Volume Today: {stats['volume_today']:.6f} BTC",
            f"Trades/sec (TPS): {stats['tps']:.2f}",
            f"Highest TPS: {stats['highest_tps']:.2f}",
            f"Avg Trade Size: {stats['avg_trade_size']:.6f} BTC",
            f"Min Trade Size: {min_trade_size} BTC (press '[' or ']' to adjust)",
        ]
        if stats['largest_trade']:
            lt = stats['largest_trade']
            lines.append(f"Largest Trade: {lt['side'].capitalize()} {lt['size']:.6f} BTC @ ${lt['price']:.2f}")
        lines.append(f"Audio: {'ON' if audio_enabled else 'OFF'} (press 'a' to toggle)")
        self.stats_widget.update("\n".join(lines))
        # Filter trades for table and bot detection
        filtered_trades = [t for t in recent_trades[-100:] if t['size'] >= min_trade_size]
        # Update trades table
        self.trades_table.clear()
        for trade in reversed(filtered_trades[-TRADES_TABLE_SIZE:]):
            self.trades_table.add_row(trade['side'].capitalize(), f"${trade['price']:.2f}", f"{trade['size']:.6f}")
        # Bot detection: detect patterns of identical trade sizes
        size_counts: dict[float, int] = {}
        size_to_prices: dict[float, list[float]] = {}
        for trade in filtered_trades[-TRADES_TABLE_SIZE:]:
            rounded_size = round(trade['size'], 4)
            size_counts[rounded_size] = size_counts.get(rounded_size, 0) + 1
            if rounded_size not in size_to_prices:
                size_to_prices[rounded_size] = []
            size_to_prices[rounded_size].append(trade['price'])
        likely_bot = any(count >= BOT_DETECTION_THRESHOLD for count in size_counts.values())
        if likely_bot:
            repeated_size = max(size_counts, key=lambda k: size_counts[k] if size_counts[k] >= BOT_DETECTION_THRESHOLD else 0)
            price_list = size_to_prices[repeated_size]
            repeated_price = price_list[-1] if price_list else stats['last_price']
            self.bot_banner.update(f"[bold]⚠️  Possible bot activity: {BOT_DETECTION_THRESHOLD}+ trades of {repeated_size} BTC @ ${repeated_price:,.2f} in last {TRADES_TABLE_SIZE}! ⚠️[/bold]")
            self.bot_banner.add_class("active")
            if hasattr(self, 'bot_banner_timer') and self.bot_banner_timer:
                self.bot_banner_timer.stop()
            self.bot_banner_timer = self.set_timer(BOT_BANNER_DURATION, self.hide_bot_banner)
        else:
            self.bot_banner.update("")
            self.bot_banner.remove_class("active")
            if hasattr(self, 'bot_banner_timer') and self.bot_banner_timer:
                self.bot_banner_timer.stop()
                self.bot_banner_timer = None

    def hide_bot_banner(self) -> None:
        """Hide the bot detection banner."""
        self.bot_banner.update("")
        self.bot_banner.remove_class("active")

if __name__ == "__main__":
    os.system("clear" if os.name == "posix" else "cls")
    print("Starting BTC CLI Visualizer (Textual)...")
    print("Press Ctrl+C to exit. Press 'a' to toggle audio.")
    pygame.mixer.init()
    if os.path.exists(CLICK_SOUND_PATH):
        click_sound = pygame.mixer.Sound(CLICK_SOUND_PATH)
    else:
        click_sound = None
        print("Warning: click sound file not found!")
    BTCBeeperApp().run()
