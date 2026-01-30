import asyncio
import json
import time

import pygame
import websockets
from textual.app import App, ComposeResult
from textual.timer import Timer
from textual.widgets import DataTable, Static

CLICK_SOUND_PATH = "data/sounds/geiger_click7.wav"
COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"

TPS_WINDOW = 10
MAX_RECENT_TRADES = 1000
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5
BOT_DETECTION_THRESHOLD = 5
BOT_BANNER_DURATION = 5
TRADES_TABLE_SIZE = 10
STATS_REFRESH_INTERVAL = 0.5
ANIMATION_DURATION = 0.5

click_sound = None

class PriceWidget(Static):
    """Widget for displaying BTC/USD price with animation effects."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.anim_timer: Timer | None = None

    def update_price(self, price: float) -> None:
        self.update(f"\n[bold bright_white on black]BTC/USD[/]\n\n[bold bright_yellow on black]${price:,.2f}[/]")

    def animate(self, direction: str) -> None:
        self.add_class(f"price-{direction}")
        if self.anim_timer:
            self.anim_timer.stop()
        self.anim_timer = self.set_timer(ANIMATION_DURATION, self._reset_animation)

    def _reset_animation(self) -> None:
        self.remove_class("price-up")
        self.remove_class("price-down")

class BTCBeeperApp(App):
    CSS = """
    #price { align: center middle; height: 6; content-align: center middle; text-align: center; padding: 1 0; }
    .price-up { background: green; color: black; transition: background 200ms, color 200ms; }
    .price-down { background: red; color: white; transition: background 200ms, color 200ms; }
    #stats { padding: 0 1; }
    #trades { padding: 0 1; }
    #bot-banner { dock: bottom; height: 2; background: yellow; color: black; text-align: center; content-align: center middle; padding: 0 1; visibility: hidden; }
    #bot-banner.active { visibility: visible; background: orange; color: black; }
    """
    FILTER_SIZES = [0.0001, 0.001, 0.01, 0.1, 1]
    BINDINGS = [
        ("a", "toggle_audio", "Toggle Audio"),
        ("[", "filter_down", "Decrease Min Trade Size"),
        ("]", "filter_up", "Increase Min Trade Size"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot_banner_timer: Timer | None = None
        self.filter_index = 0
        self.audio_enabled = True
        self.stats = {
            "total_trades": 0,
            "last_price": 0.0,
            "volume_today": 0.0,
            "avg_trade_size": 0.0,
            "largest_trade": None,
            "tps": 0.0,
            "highest_tps": 0.0,
        }
        self.recent_trades: list[dict] = []
        self.trade_timestamps: list[float] = []

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
        self.set_interval(STATS_REFRESH_INTERVAL, self.refresh_stats)
        self._start_websocket()

    def _start_websocket(self) -> None:
        self.run_worker(self._ws_loop, exclusive=True)

    async def _ws_loop(self) -> None:
        reconnect_attempts = 0
        subscribe_msg = json.dumps({
            "type": "subscribe",
            "product_ids": ["BTC-USD"],
            "channels": ["matches", "ticker", "heartbeat"],
        })

        while reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
            try:
                async with websockets.connect(COINBASE_WS_URL) as ws:
                    await ws.send(subscribe_msg)
                    reconnect_attempts = 0
                    async for message in ws:
                        self._process_message(message)
            except (websockets.exceptions.WebSocketException, ConnectionError, OSError) as e:
                reconnect_attempts += 1
                self.stats_widget.update(f"[Connection Error]: {e}. Reconnecting... ({reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})")
                if reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
                    await asyncio.sleep(RECONNECT_DELAY)
                else:
                    self.stats_widget.update("[Connection Failed]: Max reconnection attempts reached.")

    def _process_message(self, message: str) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        if data.get("product_id") not in ["BTC-USD", None]:
            return

        msg_type = data.get("type", "")

        if msg_type in ["match", "last_match"]:
            self._handle_trade(data)
        elif msg_type == "ticker":
            price = float(data.get("price", 0))
            if price > 0:
                self.stats["last_price"] = price
                self.refresh_stats()
        elif msg_type == "error":
            self.stats_widget.update(f"[Error]: {data.get('message', 'Unknown error')}")

    def _handle_trade(self, data: dict) -> None:
        trade_size = float(data.get("size", 0))
        if trade_size < self.get_min_trade_size():
            return

        trade = {
            "price": float(data["price"]),
            "size": trade_size,
            "side": data.get("side", "unknown"),
        }

        prev_price = self.stats["last_price"]
        self.stats["total_trades"] += 1
        self.stats["last_price"] = trade["price"]
        self.stats["volume_today"] += trade["size"]

        self.recent_trades.append(trade)
        if len(self.recent_trades) > MAX_RECENT_TRADES:
            self.recent_trades.pop(0)

        self.trade_timestamps.append(time.time())
        self._update_tps()
        self.stats["avg_trade_size"] = self.stats["volume_today"] / self.stats["total_trades"]

        largest = self.stats["largest_trade"]
        if not largest or trade["size"] > largest["size"]:
            self.stats["largest_trade"] = trade.copy()

        self._play_click()

        if prev_price:
            if trade["price"] > prev_price:
                self.price_widget.animate("up")
            elif trade["price"] < prev_price:
                self.price_widget.animate("down")

        self.refresh_stats()

    def _update_tps(self) -> None:
        now = time.time()
        while self.trade_timestamps and now - self.trade_timestamps[0] > TPS_WINDOW:
            self.trade_timestamps.pop(0)
        self.stats["tps"] = len(self.trade_timestamps) / TPS_WINDOW
        self.stats["highest_tps"] = max(self.stats["highest_tps"], self.stats["tps"])

    def _play_click(self) -> None:
        if self.audio_enabled and click_sound:
            click_sound.play()

    def action_toggle_audio(self) -> None:
        self.audio_enabled = not self.audio_enabled
        self.refresh_stats()

    def action_filter_down(self) -> None:
        if self.filter_index > 0:
            self.filter_index -= 1
            self.refresh_stats()

    def action_filter_up(self) -> None:
        if self.filter_index < len(self.FILTER_SIZES) - 1:
            self.filter_index += 1
            self.refresh_stats()

    def get_min_trade_size(self) -> float:
        return self.FILTER_SIZES[self.filter_index]

    def refresh_stats(self) -> None:
        s = self.stats
        min_size = self.get_min_trade_size()

        self.price_widget.update_price(s["last_price"])

        lines = [
            f"Total Trades: {s['total_trades']}",
            f"Volume Today: {s['volume_today']:.6f} BTC",
            f"Trades/sec (TPS): {s['tps']:.2f}",
            f"Highest TPS: {s['highest_tps']:.2f}",
            f"Avg Trade Size: {s['avg_trade_size']:.6f} BTC",
            f"Min Trade Size: {min_size} BTC (press '[' or ']' to adjust)",
        ]
        if s["largest_trade"]:
            lt = s["largest_trade"]
            lines.append(f"Largest Trade: {lt['side'].capitalize()} {lt['size']:.6f} BTC @ ${lt['price']:.2f}")
        lines.append(f"Audio: {'ON' if self.audio_enabled else 'OFF'} (press 'a' to toggle)")
        self.stats_widget.update("\n".join(lines))

        filtered = [t for t in self.recent_trades[-100:] if t["size"] >= min_size]
        self._update_trades_table(filtered[-TRADES_TABLE_SIZE:])
        self._check_bot_activity(filtered[-TRADES_TABLE_SIZE:])

    def _update_trades_table(self, trades: list[dict]) -> None:
        self.trades_table.clear()
        for t in reversed(trades):
            self.trades_table.add_row(t["side"].capitalize(), f"${t['price']:.2f}", f"{t['size']:.6f}")

    def _check_bot_activity(self, trades: list[dict]) -> None:
        size_counts: dict[float, int] = {}
        size_prices: dict[float, float] = {}
        for t in trades:
            sz = round(t["size"], 4)
            size_counts[sz] = size_counts.get(sz, 0) + 1
            size_prices[sz] = t["price"]

        bot_sizes = [sz for sz, cnt in size_counts.items() if cnt >= BOT_DETECTION_THRESHOLD]
        if bot_sizes:
            sz = max(bot_sizes, key=lambda x: size_counts[x])
            self.bot_banner.update(f"[bold]Possible bot: {size_counts[sz]}+ trades of {sz} BTC @ ${size_prices[sz]:,.2f}[/bold]")
            self.bot_banner.add_class("active")
            if self.bot_banner_timer:
                self.bot_banner_timer.stop()
            self.bot_banner_timer = self.set_timer(BOT_BANNER_DURATION, self._hide_bot_banner)
        else:
            self._hide_bot_banner()

    def _hide_bot_banner(self) -> None:
        self.bot_banner.update("")
        self.bot_banner.remove_class("active")
        if self.bot_banner_timer:
            self.bot_banner_timer.stop()
            self.bot_banner_timer = None
