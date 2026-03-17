import asyncio
import json
import logging
import os
import time

import pygame
import websockets
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.timer import Timer
from textual.widgets import DataTable, Footer, Static

logging.basicConfig(
    filename=os.getenv("BTCBEEPER_LOG_PATH", "btcbeeper.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

CLICK_SOUND_PATH = os.getenv("BTCBEEPER_SOUND_PATH", "data/sounds/geiger_click7.wav")
SELL_SOUND_PATH = os.getenv("BTCBEEPER_SELL_SOUND_PATH", "data/sounds/geiger_click4.wav")
COINBASE_WS_URL = os.getenv("COINBASE_WS_URL", "wss://ws-feed.exchange.coinbase.com")

TPS_WINDOW = 10
MAX_RECENT_TRADES = 1000
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 2
BOT_DETECTION_THRESHOLD = 5
BOT_BANNER_DURATION = 5
TRADES_TABLE_SIZE = 16
STATS_REFRESH_INTERVAL = 0.5
ANIMATION_DURATION = 0.5

click_sound = None
click_sound_sell = None


class StatusHeader(Static):
    def __init__(self, *args, **kwargs):
        super().__init__("", *args, **kwargs)
        self._feed_status = "--"
        self._audio_status = "ON"

    @property
    def feed_status(self) -> str:
        return self._feed_status

    @feed_status.setter
    def feed_status(self, value: str) -> None:
        self._feed_status = value
        self._refresh_display()

    @property
    def audio_status(self) -> str:
        return self._audio_status

    @audio_status.setter
    def audio_status(self, value: str) -> None:
        self._audio_status = value
        self._refresh_display()

    def on_mount(self) -> None:
        self._refresh_display()

    def _refresh_display(self) -> None:
        self.update(
            f"[bold bright_cyan]\u20bf BTCBeeper[/]"
            f"  [dim]Feed:[/] {self._feed_status}"
            f"  [dim]Audio:[/] {self._audio_status}"
            f"  [dim]BTC-USD[/]"
        )


class SessionWidget(Static):
    def on_mount(self) -> None:
        self.border_title = "SESSION"

    def update_session(self, stats: dict, elapsed_secs: int) -> None:
        uptime = f"{elapsed_secs // 3600:02d}:{(elapsed_secs % 3600) // 60:02d}:{elapsed_secs % 60:02d}"
        session_high = stats.get("session_high", 0.0)
        session_low = stats.get("session_low", float("inf"))
        low_line = (
            f"[dim]Low   [/] [bright_yellow]${session_low:,.2f}[/]"
            if session_low != float("inf")
            else "[dim]Low   [/] [dim]N/A[/]"
        )
        lines = [
            f"[dim]Uptime[/] {uptime}",
            f"[dim]High  [/] [bright_yellow]${session_high:,.2f}[/]",
            low_line,
        ]
        self.update("\n".join(lines))


class TradeStatsWidget(Static):
    def on_mount(self) -> None:
        self.border_title = "TRADES"

    def update_trade_stats(self, stats: dict) -> None:
        volume_usd = stats.get("volume_usd", 0.0)
        lines = [
            f"[dim]Count [/] [bright_white]{stats['total_trades']}[/] trades",
            f"[dim]Volume[/] [bright_cyan]{_fmt_btc(stats['session_volume'])} BTC[/]",
            f"[dim]USD   [/] [bright_yellow]${volume_usd:,.2f}[/]",
            f"[dim]Avg   [/] [bright_cyan]{_fmt_btc(stats['avg_trade_size'])} BTC[/]",
        ]
        if stats["largest_trade"]:
            lt = stats["largest_trade"]
            side_color = "bright_green" if lt["side"] == "buy" else "bright_red"
            lines.append(
                f"[dim]Largest[/] [{side_color}]{lt['side'].capitalize()}[/] "
                f"[bright_cyan]{_fmt_btc(lt['size'])} BTC[/]"
            )
        self.update("\n".join(lines))


class ActivityWidget(Static):
    def on_mount(self) -> None:
        self.border_title = "ACTIVITY"

    def update_activity(self, stats: dict, min_size: float, audio_enabled: bool) -> None:
        lines = [
            f"[dim]TPS   [/] {stats['tps']:.2f}  [dim]peak[/] {stats['highest_tps']:.2f}",
            f"[dim]Filter[/] \u2265 {min_size} BTC",
        ]
        errors_p = stats.get("parse_errors", 0)
        errors_i = stats.get("invalid_trades", 0)
        if errors_p or errors_i:
            lines.append(f"[dim]Errors[/] [bright_red]{errors_p} parse  {errors_i} invalid[/]")
        self.update("\n".join(lines))


class BotBanner(Static):
    pass


class PriceWidget(Static):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.anim_timer: Timer | None = None

    def update_price(self, price: float) -> None:
        self.update(f"\n[bold bright_yellow on black]${price:,.2f}[/]")

    def animate(self, direction: str) -> None:
        self.add_class(f"price-{direction}")
        if self.anim_timer:
            self.anim_timer.stop()
        self.anim_timer = self.set_timer(ANIMATION_DURATION, self._reset_animation)

    def _reset_animation(self) -> None:
        self.remove_class("price-up")
        self.remove_class("price-down")

class HeatmapWidget(Static):
    LABELS = ["< 0.0001", "0.0001\u20130.001", "0.001\u20130.01", "0.01\u20130.1", "0.1\u20131.0", "\u2265 1.0"]

    def update_heatmap(self, counts: list[int]) -> None:
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


def _fmt_btc(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


class BTCBeeperApp(App):
    CSS_PATH = "btcbeeper.tcss"
    FILTER_SIZES = [0.0001, 0.001, 0.01, 0.1, 1]
    BINDINGS = [
        ("q",  "quit",         "Quit"),
        ("a",  "toggle_audio", "Audio on/off"),
        ("[",  "filter_down",  "Filter \u2190"),
        ("]",  "filter_up",    "Filter \u2192"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot_banner_timer: Timer | None = None
        self.filter_index = 0
        self.audio_enabled = True
        self.stats = {
            "total_trades": 0,
            "last_price": 0.0,
            "session_volume": 0.0,
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
        self._trade_row_map: dict = {}
        self._last_msg_time: float = 0.0

    def compose(self) -> ComposeResult:
        self.status_header = StatusHeader(id="status-header")
        yield self.status_header
        self.price_widget = PriceWidget(id="price")
        yield self.price_widget
        with Horizontal(id="main-row"):
            with Vertical(id="left-panel"):
                self.session_widget = SessionWidget()
                yield self.session_widget
                self.trade_stats_widget = TradeStatsWidget()
                yield self.trade_stats_widget
                self.activity_widget = ActivityWidget()
                yield self.activity_widget
            with Vertical(id="right-panel"):
                self.trades_table = DataTable(id="trades-table", cursor_type="row")
                self.trades_table.add_columns("Side", "Price", "Size (BTC)")
                yield self.trades_table
        self.heatmap_widget = HeatmapWidget(id="heatmap")
        yield self.heatmap_widget
        self.bot_banner = BotBanner("", id="bot-banner")
        yield self.bot_banner
        yield Footer()

    async def on_mount(self) -> None:
        self.set_interval(STATS_REFRESH_INTERVAL, self.refresh_stats)
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
                async with websockets.connect(COINBASE_WS_URL, ping_interval=10, ping_timeout=5) as ws:
                    await ws.send(subscribe_msg)
                    reconnect_attempts = 0
                    self._last_msg_time = time.time()
                    logger.info("Connected to %s", COINBASE_WS_URL)
                    async for message in ws:
                        now = time.time()
                        if self._last_msg_time and now - self._last_msg_time > 2:
                            logger.info("Message gap of %.1fs", now - self._last_msg_time)
                        self._last_msg_time = now
                        self._process_message(message)
            except (websockets.exceptions.WebSocketException, ConnectionError, OSError) as e:
                reconnect_attempts += 1
                logger.warning("Connection error: %s (attempt %d/%d)", e, reconnect_attempts, MAX_RECONNECT_ATTEMPTS)
                self.status_header.feed_status = f"[bright_red]ERR {reconnect_attempts}/{MAX_RECONNECT_ATTEMPTS}[/]"
                if reconnect_attempts < MAX_RECONNECT_ATTEMPTS:
                    await asyncio.sleep(RECONNECT_DELAY)
                else:
                    logger.error("Max reconnection attempts reached, giving up")
                    self.status_header.feed_status = "[bright_red]DISCONNECTED[/]"

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
        elif msg_type == "error":
            self.status_header.feed_status = f"[Error]: {data.get('message', 'Unknown error')}"

    def _handle_trade(self, data: dict) -> None:
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

        trade = {
            "price": trade_price,
            "size": trade_size,
            "side": data.get("side", "unknown"),
            "trade_id": data.get("trade_id", ""),
            "maker_order_id": data.get("maker_order_id", ""),
            "taker_order_id": data.get("taker_order_id", ""),
            "time": data.get("time", ""),
        }

        # All trades feed the heatmap via recent_trades
        self.recent_trades.append(trade)
        if len(self.recent_trades) > MAX_RECENT_TRADES:
            self.recent_trades.pop(0)

        # Stats, audio, and price animation are gated by the size filter
        if trade_size >= self.get_min_trade_size():
            prev_price = self.stats["last_price"]
            self.stats["total_trades"] += 1
            self.stats["last_price"] = trade["price"]
            self.stats["session_volume"] += trade["size"]

            self.trade_timestamps.append(time.time())
            self._update_tps()
            self.stats["avg_trade_size"] = self.stats["session_volume"] / self.stats["total_trades"]

            largest = self.stats["largest_trade"]
            if not largest or trade["size"] > largest["size"]:
                self.stats["largest_trade"] = trade.copy()

            if trade_price > self.stats["session_high"]:
                self.stats["session_high"] = trade_price
            if trade_price < self.stats["session_low"]:
                self.stats["session_low"] = trade_price
            self.stats["volume_usd"] += trade_size * trade_price

            self._play_click(trade["side"])

            if prev_price:
                if trade["price"] > prev_price:
                    self.price_widget.animate("up")
                elif trade["price"] < prev_price:
                    self.price_widget.animate("down")

        self.price_widget.update_price(self.stats["last_price"])

    def _update_tps(self) -> None:
        now = time.time()
        while self.trade_timestamps and now - self.trade_timestamps[0] > TPS_WINDOW:
            self.trade_timestamps.pop(0)
        self.stats["tps"] = len(self.trade_timestamps) / TPS_WINDOW
        self.stats["highest_tps"] = max(self.stats["highest_tps"], self.stats["tps"])

    def _play_click(self, side: str = "buy") -> None:
        if not self.audio_enabled:
            return
        sound = click_sound_sell if side == "sell" else click_sound
        if sound:
            sound.play()

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

        elapsed = int(time.time() - s.get("session_start", time.time()))
        self.session_widget.update_session(s, elapsed)
        self.trade_stats_widget.update_trade_stats(s)
        self.activity_widget.update_activity(s, min_size, self.audio_enabled)

        msg_age = time.time() - self._last_msg_time if self._last_msg_time else None
        if msg_age is None:
            conn_status = "[dim]--[/]"
        elif msg_age < 2:
            conn_status = "[bright_green]live[/]"
        else:
            conn_status = f"[bright_yellow]{msg_age:.0f}s ago[/]"

        self.status_header.feed_status = conn_status
        self.status_header.audio_status = "[bright_green]ON[/]" if self.audio_enabled else "[bright_red]OFF[/]"

        filtered = [t for t in self.recent_trades[-100:] if t["size"] >= min_size]
        self._update_trades_table(filtered[-TRADES_TABLE_SIZE:])
        self._check_bot_activity(filtered[-TRADES_TABLE_SIZE:])
        self.heatmap_widget.update_heatmap(self._compute_heatmap_buckets())

    def _update_trades_table(self, trades: list[dict]) -> None:
        if self._expanded_trade:
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
        buckets = [0] * 6
        for t in self.recent_trades:
            size = t["size"]
            if size < self.FILTER_SIZES[0]:
                buckets[0] += 1
            elif size < self.FILTER_SIZES[1]:
                buckets[1] += 1
            elif size < self.FILTER_SIZES[2]:
                buckets[2] += 1
            elif size < self.FILTER_SIZES[3]:
                buckets[3] += 1
            elif size < self.FILTER_SIZES[4]:
                buckets[4] += 1
            else:
                buckets[5] += 1
        return buckets

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key in self._detail_row_keys:
            return

        if self._expanded_trade:
            for dk in self._detail_row_keys:
                self.trades_table.remove_row(dk)
            self._detail_row_keys.clear()
            if event.row_key not in self._trade_row_map:
                self._expanded_trade = None
                return
            if self._trade_row_map.get(event.row_key) is self._expanded_trade:
                # Toggle off — same row clicked again
                self._expanded_trade = None
                return
            # Different row selected — fall through to expand it

        trade = self._trade_row_map.get(event.row_key)
        if trade is None:
            return

        self._expanded_trade = trade
        self._rebuild_table_with_detail()

    def _rebuild_table_with_detail(self) -> None:
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
