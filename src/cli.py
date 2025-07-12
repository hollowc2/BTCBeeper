import asyncio
import json
import os
import websockets
import pygame
import time
from textual.app import App, ComposeResult
from textual.widgets import Static, DataTable
from textual.reactive import reactive
from textual import events
from textual.timer import Timer

# Path to your click sound
CLICK_SOUND_PATH = "data/sounds/geiger_click7.wav"

# WebSocket server URL
WS_URL = "ws://localhost:8000/ws"

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

recent_trades = []  # Keep last N trades
trade_timestamps = []  # For TPS calculation
TPS_WINDOW = 10  # seconds

audio_enabled = True
click_sound = None

class PriceWidget(Static):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_price = None
        self.anim_timer: Timer | None = None

    def update_price(self, price: float):
        # Format price large and centered (markup only uses supported tags)
        self.update(f"\n[bold bright_white on black]BTC/USD[/]\n\n[bold bright_yellow on black]${price:,.2f}[/]")

    def animate(self, direction: str):
        # direction: 'up' or 'down'
        if direction == 'up':
            self.add_class('price-up')
        elif direction == 'down':
            self.add_class('price-down')
        if self.anim_timer:
            self.anim_timer.stop()
        self.anim_timer = self.set_timer(0.5, self.reset_animation)

    def reset_animation(self):
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
        self.set_interval(0.5, self.refresh_stats)
        await self.connect_ws()
        self.last_price = None

    async def connect_ws(self):
        async def ws_loop():
            global stats, recent_trades
            try:
                async with websockets.connect(WS_URL) as websocket:
                    while True:
                        message = await websocket.recv()
                        data = json.loads(message)
                        msg_type = data.get("type")
                        payload = data.get("data", {})
                        if msg_type == "btc_trade":
                            min_trade_size = self.get_min_trade_size()
                            if payload["size"] < min_trade_size:
                                continue  # Ignore trades below filter for all stats/audio
                            stats["total_trades"] += 1
                            prev_price = stats["last_price"]
                            stats["last_price"] = payload["price"]
                            stats["volume_today"] += payload["size"]
                            recent_trades.append(payload)
                            trade_timestamps.append(time.time())
                            self.update_tps()
                            stats["avg_trade_size"] = stats["volume_today"] / stats["total_trades"] if stats["total_trades"] else 0.0
                            if not stats["largest_trade"] or payload["size"] > stats["largest_trade"]["size"]:
                                stats["largest_trade"] = payload.copy()
                            await self.play_click()
                            # Animate price if changed
                            if prev_price is not None:
                                if stats["last_price"] > prev_price:
                                    self.price_widget.animate('up')
                                elif stats["last_price"] < prev_price:
                                    self.price_widget.animate('down')
                        elif msg_type == "btc_ticker":
                            stats["last_price"] = payload["price"]
                            stats["price_change_24h"] = payload.get("price_change_24h", stats["price_change_24h"])
                        self.refresh_stats()
            except Exception as e:
                self.stats_widget.update(f"[Connection Error]: {e}")
        self.run_worker(ws_loop, exclusive=True)

    def update_tps(self):
        now = time.time()
        while trade_timestamps and now - trade_timestamps[0] > TPS_WINDOW:
            trade_timestamps.pop(0)
        stats['tps'] = len(trade_timestamps) / TPS_WINDOW
        if stats['tps'] > stats['highest_tps']:
            stats['highest_tps'] = stats['tps']

    async def play_click(self):
        if audio_enabled and click_sound:
            click_sound.play()

    def action_toggle_audio(self):
        global audio_enabled
        audio_enabled = not audio_enabled
        self.refresh_stats()

    def action_filter_down(self):
        if self.filter_index > 0:
            self.filter_index -= 1
            self.refresh_stats()

    def action_filter_up(self):
        if self.filter_index < len(self.FILTER_SIZES) - 1:
            self.filter_index += 1
            self.refresh_stats()

    def get_min_trade_size(self):
        return self.FILTER_SIZES[self.filter_index]

    def refresh_stats(self):
        min_trade_size = self.get_min_trade_size()
        # Update price widget
        self.price_widget.update_price(stats['last_price'])
        # Update stats widget
        lines = [
            f"Total Trades: {stats['total_trades']}",
            f"Volume Today: {stats['volume_today']:.6f} BTC",
            f"24h Change: {stats['price_change_24h']:.2f}%",
            f"Trades/sec (TPS): {stats['tps']:.2f}",
            f"Highest TPS: {stats['highest_tps']:.2f}",
            f"Avg Trade Size: {stats['avg_trade_size']:.6f} BTC",
            f"Min Trade Size: {min_trade_size} BTC (press [ or ] to adjust)",
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
        for trade in reversed(filtered_trades[-10:]):
            self.trades_table.add_row(trade['side'].capitalize(), f"${trade['price']:.2f}", f"{trade['size']:.6f}")
        # Bot detection: 5+ trades of nearly identical size in last 10 filtered trades
        size_counts = {}
        size_to_prices = {}
        for trade in filtered_trades[-10:]:
            rounded_size = round(trade['size'], 4)
            size_counts[rounded_size] = size_counts.get(rounded_size, 0) + 1
            if rounded_size not in size_to_prices:
                size_to_prices[rounded_size] = []
            size_to_prices[rounded_size].append(trade['price'])
        likely_bot = any(count >= 5 for count in size_counts.values())
        if likely_bot:
            repeated_size = max(size_counts, key=lambda k: size_counts[k] if size_counts[k] >= 5 else 0)
            price_list = size_to_prices[repeated_size]
            repeated_price = price_list[-1] if price_list else stats['last_price']
            self.bot_banner.update(f"[bold]⚠️  Possible bot activity: 5+ trades of {repeated_size} BTC @ ${repeated_price:,.2f} in last 10! ⚠️[/bold]")
            self.bot_banner.add_class("active")
            if hasattr(self, 'bot_banner_timer') and self.bot_banner_timer:
                self.bot_banner_timer.stop()
            self.bot_banner_timer = self.set_timer(5, self.hide_bot_banner)
        else:
            self.bot_banner.update("")
            self.bot_banner.remove_class("active")
            if hasattr(self, 'bot_banner_timer') and self.bot_banner_timer:
                self.bot_banner_timer.stop()
                self.bot_banner_timer = None

    def hide_bot_banner(self):
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
