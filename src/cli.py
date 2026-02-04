import asyncio
import json
import logging
import os
import time

import pygame
import websockets

logging.basicConfig(
    filename="btcbeeper.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.timer import Timer
from textual.widgets import DataTable, Static

CLICK_SOUND_PATH = os.getenv("BTCBEEPER_SOUND_PATH", "data/sounds/geiger_click7.wav")
COINBASE_WS_URL = os.getenv("COINBASE_WS_URL", "wss://ws-feed.exchange.coinbase.com")

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

class HeatmapWidget(Static):
    """Widget for displaying a trade-size distribution heatmap."""

    LABELS = ["< 0.0001", "0.0001\u20130.001", "0.001\u20130.01", "0.01\u20130.1", "0.1\u20131.0", "\u2265 1.0"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.counts: list[int] = [0] * 6

    def update_heatmap(self, counts: list[int]) -> None:
        """Render the 6-bucket size distribution as colored bars."""
        self.counts = counts
        max_count = max(counts) or 1
        lines = []
        for label, count in zip(self.LABELS, counts):
            if count == 0:
                lines.append(f"[dim]{label:>12}[/]  [dim]{count:>4}[/]")
            else:
                ratio = count / max_count
                bar_width = int(ratio * 28)
                bar = "\u2588" * bar_width
                if ratio < 0.25:
                    color = "dark_cyan"
                elif ratio < 0.5:
                    color = "cyan"
                elif ratio < 0.75:
                    color = "bright_cyan"
                else:
                    color = "bright_green"
                lines.append(f"[dim]{label:>12}[/]  [dim]{count:>4}[/]  [{color}]{bar}[/]")
        self.update("\n".join(lines))

class BTCBeeperApp(App):
    CSS = """
    BTCBeeperApp {
        background: #1e1e2e;
    }

    #price {
        height: 5;
        content-align: center middle;
        text-align: center;
        border-bottom: solid $surface;
    }

    .price-up {
        color: #00e676;
        transition: color 200ms;
    }

    .price-down {
        color: #ff5252;
        transition: color 200ms;
    }

    #middle-row {
        height: 1fr;
        border-bottom: solid $surface;
    }

    #stats {
        width: 1fr;
        padding: 1;
        border-right: solid $surface;
    }

    #trades {
        width: 1fr;
        padding: 0 1;
    }

    #heatmap {
        height: 8;
        padding: 1;
        border-bottom: solid $surface;
    }

    #bot-banner {
        dock: bottom;
        height: 2;
        text-align: center;
        content-align: center middle;
        visibility: hidden;
    }

    #bot-banner.active {
        visibility: visible;
        background: #e65100;
        color: white;
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
            "parse_errors": 0,
            "invalid_trades": 0,
            "session_start": time.time(),
            "session_high": 0.0,
            "session_low": float("inf"),
            "volume_usd": 0.0,
        }
        self.recent_trades: list[dict] = []
        self.trade_timestamps: list[float] = []
        self._expanded_trade: dict | None = None
        self._detail_row_keys: list = []
        self._expansion_active: bool = False
        self._trade_row_map: dict = {}

    def compose(self) -> ComposeResult:
        self.price_widget = PriceWidget(id="price")
        yield self.price_widget
        with Horizontal(id="middle-row"):
            self.stats_widget = Static(id="stats")
            yield self.stats_widget
            self.trades_table = DataTable(id="trades", cursor_type="row")
            self.trades_table.add_columns("Side", "Price", "Size (BTC)")
            yield self.trades_table
        self.heatmap_widget = HeatmapWidget(id="heatmap")
        yield self.heatmap_widget
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
                    logger.info("Connected to %s", COINBASE_WS_URL)
                    async for message in ws:
                        self._process_message(message)
            except (websockets.exceptions.WebSocketException, ConnectionError, OSError) as e:
                reconnect_attempts += 1
                logger.warning("Connection error: %s (attempt %d/%d)", e, reconnect_attempts, MAX_RECONNECT_ATTEMPTS)
                self.stats_widget.update(f"[Connection Error]: {e}. Reconnecting... ({reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS})")
                if reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
                    await asyncio.sleep(RECONNECT_DELAY)
                else:
                    logger.error("Max reconnection attempts reached, giving up")
                    self.stats_widget.update("[Connection Failed]: Max reconnection attempts reached.")

    def _process_message(self, message: str) -> None:
        try:
            data = json.loads(message)
        except json.JSONDecodeError as e:
            self.stats["parse_errors"] += 1
            logger.debug("JSON parse error: %s", e)
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
        # Validate required fields exist before processing
        if "price" not in data or "size" not in data:
            self.stats["invalid_trades"] += 1
            logger.debug("Invalid trade: missing price or size field")
            return

        try:
            trade_size = float(data["size"])
            trade_price = float(data["price"])
        except (ValueError, TypeError) as e:
            self.stats["invalid_trades"] += 1
            logger.debug("Invalid trade: %s", e)
            return

        if trade_size < self.get_min_trade_size():
            return

        trade = {
            "price": trade_price,
            "size": trade_size,
            "side": data.get("side", "unknown"),
            "trade_id": str(data.get("trade_id", "")),
            "maker_order_id": data.get("maker_order_id", ""),
            "taker_order_id": data.get("taker_order_id", ""),
            "time": data.get("time", ""),
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

        if trade_price > self.stats["session_high"]:
            self.stats["session_high"] = trade_price
        if trade_price < self.stats["session_low"]:
            self.stats["session_low"] = trade_price
        self.stats["volume_usd"] += trade_size * trade_price

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

        # Session counters — .get() keeps tests with partial stats dicts safe
        elapsed = int(time.time() - s.get("session_start", time.time()))
        uptime = f"{elapsed // 3600:02d}:{(elapsed % 3600) // 60:02d}:{elapsed % 60:02d}"
        session_high = s.get("session_high", 0.0)
        session_low = s.get("session_low", 0.0)
        volume_usd = s.get("volume_usd", 0.0)

        lines = [
            f"Uptime:           {uptime}",
            f"Session High:     ${session_high:,.2f}",
            f"Session Low:      ${session_low:,.2f}" if session_low != float("inf") else "Session Low:      N/A",
            f"Total Trades: {s['total_trades']}",
            f"Volume Today: {s['volume_today']:.6f} BTC (${volume_usd:,.2f} USD)",
            f"Trades/sec (TPS): {s['tps']:.2f}",
            f"Highest TPS: {s['highest_tps']:.2f}",
            f"Avg Trade Size: {s['avg_trade_size']:.6f} BTC",
            f"Min Trade Size: {min_size} BTC (press '[' or ']' to adjust)",
        ]
        if s["largest_trade"]:
            lt = s["largest_trade"]
            lines.append(f"Largest Trade: {lt['side'].capitalize()} {lt['size']:.6f} BTC @ ${lt['price']:.2f}")
        lines.append(f"Audio: {'ON' if self.audio_enabled else 'OFF'} (press 'a' to toggle)")
        lines.append(f"Errors:           {s.get('parse_errors', 0)} parse, {s.get('invalid_trades', 0)} invalid")
        self.stats_widget.update("\n".join(lines))

        filtered = [t for t in self.recent_trades[-100:] if t["size"] >= min_size]
        self._update_trades_table(filtered[-TRADES_TABLE_SIZE:])
        self._check_bot_activity(filtered[-TRADES_TABLE_SIZE:])
        self.heatmap_widget.update_heatmap(self._compute_heatmap_buckets())

    def _update_trades_table(self, trades: list[dict]) -> None:
        if self._expansion_active:
            return
        self.trades_table.clear()
        self._trade_row_map.clear()
        for i, t in enumerate(reversed(trades)):
            rk = self.trades_table.add_row(
                t["side"].capitalize(), f"${t['price']:.2f}", f"{t['size']:.6f}",
                key=str(i)
            )
            self._trade_row_map[rk] = t

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

    def _compute_heatmap_buckets(self) -> list[int]:
        """Classify recent trades into 6 size buckets based on FILTER_SIZES boundaries."""
        buckets = [0] * 6
        boundaries = self.FILTER_SIZES  # [0.0001, 0.001, 0.01, 0.1, 1]
        for t in self.recent_trades:
            size = t["size"]
            if size < boundaries[0]:
                buckets[0] += 1
            elif size < boundaries[1]:
                buckets[1] += 1
            elif size < boundaries[2]:
                buckets[2] += 1
            elif size < boundaries[3]:
                buckets[3] += 1
            elif size < boundaries[4]:
                buckets[4] += 1
            else:
                buckets[5] += 1
        return buckets

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection for inline trade detail expansion."""
        if event.row_key in self._detail_row_keys:
            return

        if self._expansion_active:
            for dk in self._detail_row_keys:
                self.trades_table.remove_row(dk)
            self._detail_row_keys.clear()
            if event.row_key not in self._trade_row_map:
                self._expanded_trade = None
                self._expansion_active = False
                return
            if self._trade_row_map.get(event.row_key) is self._expanded_trade:
                # Toggle off — same row clicked again
                self._expanded_trade = None
                self._expansion_active = False
                return
            # Different row selected — fall through to expand it

        trade = self._trade_row_map.get(event.row_key)
        if trade is None:
            return

        self._expanded_trade = trade
        self._expansion_active = True
        self._rebuild_table_with_detail()

    def _rebuild_table_with_detail(self) -> None:
        """Rebuild trades table with detail rows spliced after the expanded trade."""
        min_size = self.get_min_trade_size()
        filtered = [t for t in self.recent_trades[-100:] if t["size"] >= min_size]
        trades = filtered[-TRADES_TABLE_SIZE:]

        self.trades_table.clear()
        self._trade_row_map.clear()
        self._detail_row_keys.clear()

        for i, t in enumerate(reversed(trades)):
            rk = self.trades_table.add_row(
                t["side"].capitalize(), f"${t['price']:.2f}", f"{t['size']:.6f}",
                key=str(i)
            )
            self._trade_row_map[rk] = t
            if t is self._expanded_trade:
                d = self._expanded_trade
                detail_data = [
                    ("", "", f"  Trade ID:  {d.get('trade_id', 'N/A')}"),
                    ("", "", f"  Time:      {d.get('time', 'N/A')}"),
                    ("", "", f"  Maker ID:  {d.get('maker_order_id', 'N/A')}"),
                    ("", "", f"  Taker ID:  {d.get('taker_order_id', 'N/A')}"),
                ]
                for j, row in enumerate(detail_data):
                    dk = self.trades_table.add_row(*row, key=f"detail-{i}-{j}")
                    self._detail_row_keys.append(dk)
