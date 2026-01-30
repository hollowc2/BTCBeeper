"""Tests for BTCBeeper CLI application (cli.py).

Covers:
- Message processing and parsing
- Trade handling logic
- TPS calculation
- Filter controls
- Bot detection
- Statistics tracking
- Edge cases and boundary conditions
"""

import json
import time
from unittest.mock import MagicMock, patch

import pytest


class TestProcessMessage:
    """Test _process_message method for JSON parsing and message routing."""

    def test_valid_json_match_message(self, btc_app, sample_trade_match):
        """Verify match messages are routed to _handle_trade."""
        btc_app._handle_trade = MagicMock()
        btc_app._process_message(json.dumps(sample_trade_match))
        btc_app._handle_trade.assert_called_once_with(sample_trade_match)

    def test_valid_json_last_match_message(self, btc_app, sample_trade_match):
        """Verify last_match messages are also routed to _handle_trade."""
        sample_trade_match["type"] = "last_match"
        btc_app._handle_trade = MagicMock()
        btc_app._process_message(json.dumps(sample_trade_match))
        btc_app._handle_trade.assert_called_once()

    def test_ticker_message_updates_price(self, btc_app, sample_ticker_message):
        """Verify ticker messages update last_price in stats."""
        btc_app._process_message(json.dumps(sample_ticker_message))
        assert btc_app.stats["last_price"] == 50500.00

    def test_ticker_message_zero_price_ignored(self, btc_app):
        """Verify ticker messages with zero price are ignored."""
        btc_app.stats["last_price"] = 50000.0
        ticker = {"type": "ticker", "product_id": "BTC-USD", "price": "0"}
        btc_app._process_message(json.dumps(ticker))
        assert btc_app.stats["last_price"] == 50000.0

    def test_error_message_updates_widget(self, btc_app, sample_error_message):
        """Verify error messages update the stats widget."""
        btc_app._process_message(json.dumps(sample_error_message))
        btc_app.stats_widget.update.assert_called()
        call_args = btc_app.stats_widget.update.call_args[0][0]
        assert "[Error]:" in call_args
        assert "Test error message" in call_args

    def test_invalid_json_tracked_as_parse_error(self, btc_app):
        """Verify malformed JSON doesn't crash and is tracked."""
        btc_app._handle_trade = MagicMock()
        btc_app._process_message("{invalid json")
        btc_app._handle_trade.assert_not_called()
        assert btc_app.stats["parse_errors"] == 1

    def test_empty_message_tracked_as_parse_error(self, btc_app):
        """Verify empty message doesn't crash and is tracked."""
        btc_app._handle_trade = MagicMock()
        btc_app._process_message("")
        btc_app._handle_trade.assert_not_called()
        assert btc_app.stats["parse_errors"] == 1

    def test_wrong_product_id_ignored(self, btc_app, sample_trade_match):
        """Verify messages for other products are ignored."""
        sample_trade_match["product_id"] = "ETH-USD"
        btc_app._handle_trade = MagicMock()
        btc_app._process_message(json.dumps(sample_trade_match))
        btc_app._handle_trade.assert_not_called()

    def test_heartbeat_message_ignored(self, btc_app):
        """Verify heartbeat messages are silently ignored."""
        heartbeat = {"type": "heartbeat", "sequence": 123, "last_trade_id": 456}
        btc_app._handle_trade = MagicMock()
        btc_app._process_message(json.dumps(heartbeat))
        btc_app._handle_trade.assert_not_called()

    def test_subscriptions_message_ignored(self, btc_app):
        """Verify subscriptions confirmation is silently ignored."""
        subscriptions = {"type": "subscriptions", "channels": []}
        btc_app._handle_trade = MagicMock()
        btc_app._process_message(json.dumps(subscriptions))
        btc_app._handle_trade.assert_not_called()

    def test_null_product_id_allowed(self, btc_app, sample_trade_match):
        """Verify messages without product_id are processed (for error messages)."""
        del sample_trade_match["product_id"]
        btc_app._handle_trade = MagicMock()
        btc_app._process_message(json.dumps(sample_trade_match))
        btc_app._handle_trade.assert_called_once()


class TestHandleTrade:
    """Test _handle_trade method for trade processing logic."""

    def test_trade_updates_statistics(self, btc_app):
        """Verify trade correctly updates all statistics."""
        trade_data = {
            "type": "match",
            "price": "50000.00",
            "size": "0.5",
            "side": "buy",
            "product_id": "BTC-USD"
        }
        btc_app._handle_trade(trade_data)

        assert btc_app.stats["total_trades"] == 1
        assert btc_app.stats["last_price"] == 50000.0
        assert btc_app.stats["volume_today"] == 0.5
        assert btc_app.stats["avg_trade_size"] == 0.5
        assert btc_app.stats["largest_trade"]["size"] == 0.5

    def test_multiple_trades_accumulate(self, btc_app):
        """Verify multiple trades correctly accumulate statistics."""
        trades = [
            {"price": "50000.00", "size": "0.5", "side": "buy"},
            {"price": "50100.00", "size": "0.3", "side": "sell"},
            {"price": "50050.00", "size": "0.7", "side": "buy"},
        ]
        for t in trades:
            btc_app._handle_trade(t)

        assert btc_app.stats["total_trades"] == 3
        assert btc_app.stats["volume_today"] == pytest.approx(1.5, rel=1e-6)
        assert btc_app.stats["avg_trade_size"] == pytest.approx(0.5, rel=1e-6)
        assert btc_app.stats["largest_trade"]["size"] == 0.7
        assert btc_app.stats["last_price"] == 50050.0

    def test_trade_below_filter_ignored(self, btc_app):
        """Verify trades smaller than filter are ignored."""
        btc_app.filter_index = 3  # 0.1 BTC min
        trade_data = {"price": "50000.00", "size": "0.05", "side": "buy"}
        btc_app._handle_trade(trade_data)

        assert btc_app.stats["total_trades"] == 0
        assert btc_app.stats["volume_today"] == 0.0

    def test_trade_at_filter_boundary_included(self, btc_app):
        """Verify trades exactly at filter threshold are included."""
        btc_app.filter_index = 2  # 0.01 BTC min
        trade_data = {"price": "50000.00", "size": "0.01", "side": "buy"}
        btc_app._handle_trade(trade_data)

        assert btc_app.stats["total_trades"] == 1

    def test_trade_adds_to_recent_trades(self, btc_app):
        """Verify trades are added to recent_trades list."""
        trade_data = {"price": "50000.00", "size": "0.5", "side": "buy"}
        btc_app._handle_trade(trade_data)

        assert len(btc_app.recent_trades) == 1
        assert btc_app.recent_trades[0]["price"] == 50000.0
        assert btc_app.recent_trades[0]["size"] == 0.5
        assert btc_app.recent_trades[0]["side"] == "buy"

    def test_recent_trades_capped_at_max(self, btc_app):
        """Verify recent_trades list doesn't exceed MAX_RECENT_TRADES."""
        from cli import MAX_RECENT_TRADES

        # Add more than max trades
        for i in range(MAX_RECENT_TRADES + 50):
            btc_app._handle_trade({
                "price": str(50000 + i),
                "size": "0.5",
                "side": "buy"
            })

        assert len(btc_app.recent_trades) == MAX_RECENT_TRADES
        # First trades should have been removed
        assert btc_app.recent_trades[0]["price"] == 50050.0

    def test_largest_trade_tracked(self, btc_app):
        """Verify largest trade is correctly tracked and updated."""
        trades = [
            {"price": "50000.00", "size": "0.5", "side": "buy"},
            {"price": "50100.00", "size": "2.0", "side": "sell"},  # Largest
            {"price": "50050.00", "size": "0.3", "side": "buy"},
        ]
        for t in trades:
            btc_app._handle_trade(t)

        largest = btc_app.stats["largest_trade"]
        assert largest["size"] == 2.0
        assert largest["side"] == "sell"
        assert largest["price"] == 50100.0

    def test_price_up_animation_triggered(self, btc_app):
        """Verify price increase triggers 'up' animation."""
        btc_app.stats["last_price"] = 50000.0
        btc_app._handle_trade({"price": "50100.00", "size": "0.5", "side": "buy"})
        btc_app.price_widget.animate.assert_called_with("up")

    def test_price_down_animation_triggered(self, btc_app):
        """Verify price decrease triggers 'down' animation."""
        btc_app.stats["last_price"] = 50000.0
        btc_app._handle_trade({"price": "49900.00", "size": "0.5", "side": "sell"})
        btc_app.price_widget.animate.assert_called_with("down")

    def test_no_animation_when_price_unchanged(self, btc_app):
        """Verify no animation when price stays the same."""
        btc_app.stats["last_price"] = 50000.0
        btc_app._handle_trade({"price": "50000.00", "size": "0.5", "side": "buy"})
        btc_app.price_widget.animate.assert_not_called()

    def test_no_animation_on_first_trade(self, btc_app):
        """Verify no animation when there's no previous price."""
        btc_app.stats["last_price"] = 0
        btc_app._handle_trade({"price": "50000.00", "size": "0.5", "side": "buy"})
        btc_app.price_widget.animate.assert_not_called()

    def test_missing_side_defaults_to_unknown(self, btc_app):
        """Verify missing side field defaults to 'unknown'."""
        trade_data = {"price": "50000.00", "size": "0.5"}
        btc_app._handle_trade(trade_data)
        assert btc_app.recent_trades[0]["side"] == "unknown"

    def test_zero_size_trade_filtered(self, btc_app):
        """Verify zero-size trades are filtered out."""
        trade_data = {"price": "50000.00", "size": "0", "side": "buy"}
        btc_app._handle_trade(trade_data)
        assert btc_app.stats["total_trades"] == 0

    def test_click_played_on_trade(self, btc_app):
        """Verify click sound is played when audio is enabled."""
        with patch.object(btc_app, '_play_click') as mock_click:
            btc_app._handle_trade({"price": "50000.00", "size": "0.5", "side": "buy"})
            mock_click.assert_called_once()


class TestUpdateTPS:
    """Test _update_tps method for trades-per-second calculation."""

    def test_tps_calculation_basic(self, btc_app, frozen_time):
        """Verify basic TPS calculation."""
        from cli import TPS_WINDOW

        with patch('time.time', return_value=frozen_time):
            # Add 5 trades
            for _ in range(5):
                btc_app.trade_timestamps.append(frozen_time)

            btc_app._update_tps()

            expected_tps = 5 / TPS_WINDOW
            assert btc_app.stats["tps"] == pytest.approx(expected_tps, rel=1e-6)

    def test_old_timestamps_removed(self, btc_app, frozen_time):
        """Verify timestamps older than TPS_WINDOW are removed."""
        from cli import TPS_WINDOW

        # Add old timestamps (outside window)
        btc_app.trade_timestamps = [
            frozen_time - TPS_WINDOW - 5,
            frozen_time - TPS_WINDOW - 3,
            frozen_time - TPS_WINDOW - 1,
        ]
        # Add recent timestamps (inside window)
        btc_app.trade_timestamps.extend([
            frozen_time - 5,
            frozen_time - 3,
        ])

        with patch('time.time', return_value=frozen_time):
            btc_app._update_tps()

        # Only recent timestamps should remain
        assert len(btc_app.trade_timestamps) == 2
        expected_tps = 2 / TPS_WINDOW
        assert btc_app.stats["tps"] == pytest.approx(expected_tps, rel=1e-6)

    def test_empty_timestamps_zero_tps(self, btc_app, frozen_time):
        """Verify TPS is 0 when no timestamps exist."""
        btc_app.trade_timestamps = []

        with patch('time.time', return_value=frozen_time):
            btc_app._update_tps()

        assert btc_app.stats["tps"] == 0.0

    def test_highest_tps_tracked(self, btc_app, frozen_time):
        """Verify highest TPS is correctly tracked across updates."""
        from cli import TPS_WINDOW

        with patch('time.time', return_value=frozen_time):
            # First batch: 5 trades
            btc_app.trade_timestamps = [frozen_time - i for i in range(5)]
            btc_app._update_tps()
            first_tps = btc_app.stats["tps"]

            # Second batch: 10 trades (higher)
            btc_app.trade_timestamps = [frozen_time - i * 0.5 for i in range(10)]
            btc_app._update_tps()

            # Third batch: 3 trades (lower)
            btc_app.trade_timestamps = [frozen_time - i for i in range(3)]
            btc_app._update_tps()

        # Highest should be from second batch
        expected_highest = 10 / TPS_WINDOW
        assert btc_app.stats["highest_tps"] == pytest.approx(expected_highest, rel=1e-6)

    def test_timestamps_exactly_at_boundary(self, btc_app, frozen_time):
        """Verify timestamp exactly at window boundary is included.

        The check is `> TPS_WINDOW`, so exactly 10 seconds old is NOT > 10,
        meaning the timestamp should be kept.
        """
        from cli import TPS_WINDOW

        # Timestamp exactly at the boundary (10 seconds old)
        btc_app.trade_timestamps = [frozen_time - TPS_WINDOW]

        with patch('time.time', return_value=frozen_time):
            btc_app._update_tps()

        # Should be INCLUDED (> comparison means exactly 10s is kept)
        assert len(btc_app.trade_timestamps) == 1
        expected_tps = 1 / TPS_WINDOW
        assert btc_app.stats["tps"] == pytest.approx(expected_tps, rel=1e-6)

    def test_timestamps_just_outside_boundary(self, btc_app, frozen_time):
        """Verify timestamp just outside window boundary is excluded."""
        from cli import TPS_WINDOW

        # Timestamp just over the boundary (10.001 seconds old)
        btc_app.trade_timestamps = [frozen_time - TPS_WINDOW - 0.001]

        with patch('time.time', return_value=frozen_time):
            btc_app._update_tps()

        # Should be excluded (> TPS_WINDOW)
        assert len(btc_app.trade_timestamps) == 0
        assert btc_app.stats["tps"] == 0.0


class TestFilterControls:
    """Test filter control methods."""

    def test_get_min_trade_size_default(self, btc_app):
        """Verify default filter is first (smallest) size."""
        assert btc_app.filter_index == 0
        assert btc_app.get_min_trade_size() == 0.0001

    def test_get_min_trade_size_all_levels(self, btc_app):
        """Verify all filter levels return correct values."""
        expected = [0.0001, 0.001, 0.01, 0.1, 1]
        for i, expected_size in enumerate(expected):
            btc_app.filter_index = i
            assert btc_app.get_min_trade_size() == expected_size

    def test_filter_up_increments(self, btc_app):
        """Verify filter_up action increases filter index."""
        initial = btc_app.filter_index
        btc_app.action_filter_up()
        assert btc_app.filter_index == initial + 1

    def test_filter_down_decrements(self, btc_app):
        """Verify filter_down action decreases filter index."""
        btc_app.filter_index = 2
        btc_app.action_filter_down()
        assert btc_app.filter_index == 1

    def test_filter_up_at_max_stays_at_max(self, btc_app):
        """Verify filter can't exceed maximum."""
        btc_app.filter_index = len(btc_app.FILTER_SIZES) - 1
        btc_app.action_filter_up()
        assert btc_app.filter_index == len(btc_app.FILTER_SIZES) - 1

    def test_filter_down_at_min_stays_at_min(self, btc_app):
        """Verify filter can't go below zero."""
        btc_app.filter_index = 0
        btc_app.action_filter_down()
        assert btc_app.filter_index == 0

    def test_filter_change_triggers_refresh(self, btc_app):
        """Verify filter changes trigger stats refresh."""
        with patch.object(btc_app, 'refresh_stats') as mock_refresh:
            btc_app.action_filter_up()
            mock_refresh.assert_called_once()


class TestAudioToggle:
    """Test audio toggle functionality."""

    def test_audio_enabled_by_default(self, btc_app):
        """Verify audio is enabled by default."""
        assert btc_app.audio_enabled is True

    def test_toggle_audio_disables(self, btc_app):
        """Verify toggle disables audio when enabled."""
        btc_app.action_toggle_audio()
        assert btc_app.audio_enabled is False

    def test_toggle_audio_enables(self, btc_app):
        """Verify toggle enables audio when disabled."""
        btc_app.audio_enabled = False
        btc_app.action_toggle_audio()
        assert btc_app.audio_enabled is True

    def test_toggle_triggers_refresh(self, btc_app):
        """Verify toggle triggers stats refresh."""
        with patch.object(btc_app, 'refresh_stats') as mock_refresh:
            btc_app.action_toggle_audio()
            mock_refresh.assert_called_once()


class TestBotDetection:
    """Test _check_bot_activity method for detecting automated trading."""

    def test_no_bot_detected_varied_sizes(self, btc_app):
        """Verify no bot detected with varied trade sizes."""
        trades = [
            {"price": 50000.0, "size": 0.1, "side": "buy"},
            {"price": 50000.0, "size": 0.2, "side": "buy"},
            {"price": 50000.0, "size": 0.3, "side": "buy"},
            {"price": 50000.0, "size": 0.4, "side": "buy"},
        ]
        btc_app._check_bot_activity(trades)
        btc_app.bot_banner.add_class.assert_not_called()

    def test_bot_detected_repeated_sizes(self, btc_app):
        """Verify bot detected when same size repeated 5+ times."""
        trades = [
            {"price": 50000.0, "size": 0.1234, "side": "buy"},
            {"price": 50000.0, "size": 0.1234, "side": "buy"},
            {"price": 50000.0, "size": 0.1234, "side": "buy"},
            {"price": 50000.0, "size": 0.1234, "side": "buy"},
            {"price": 50000.0, "size": 0.1234, "side": "buy"},
        ]
        btc_app._check_bot_activity(trades)
        btc_app.bot_banner.add_class.assert_called_with("active")
        btc_app.bot_banner.update.assert_called()
        call_args = btc_app.bot_banner.update.call_args[0][0]
        assert "Possible bot" in call_args
        assert "0.1234" in call_args

    def test_bot_detection_threshold_exact(self, btc_app):
        """Verify 4 identical trades doesn't trigger bot detection."""
        trades = [
            {"price": 50000.0, "size": 0.1234, "side": "buy"},
            {"price": 50000.0, "size": 0.1234, "side": "buy"},
            {"price": 50000.0, "size": 0.1234, "side": "buy"},
            {"price": 50000.0, "size": 0.1234, "side": "buy"},
        ]
        btc_app._check_bot_activity(trades)
        btc_app.bot_banner.add_class.assert_not_called()

    def test_bot_detection_multiple_bots_shows_highest(self, btc_app):
        """Verify when multiple sizes qualify, the most frequent is shown."""
        trades = [
            # 5 trades of size 0.1
            *[{"price": 50000.0, "size": 0.1, "side": "buy"} for _ in range(5)],
            # 7 trades of size 0.2 (more frequent)
            *[{"price": 50000.0, "size": 0.2, "side": "sell"} for _ in range(7)],
        ]
        btc_app._check_bot_activity(trades)
        call_args = btc_app.bot_banner.update.call_args[0][0]
        assert "0.2" in call_args

    def test_bot_detection_rounding(self, btc_app):
        """Verify sizes are rounded to 4 decimals for comparison.

        Python's round() uses banker's rounding (round half to even):
        - 0.12345 rounds to 0.1234 (5 rounds down to even)
        - 0.12346 rounds to 0.1235
        - 0.12347 rounds to 0.1235
        """
        # All these values round to 0.1235 with 4 decimal places
        trades = [
            {"price": 50000.0, "size": 0.12346, "side": "buy"},
            {"price": 50000.0, "size": 0.12347, "side": "buy"},
            {"price": 50000.0, "size": 0.12348, "side": "buy"},
            {"price": 50000.0, "size": 0.12351, "side": "buy"},
            {"price": 50000.0, "size": 0.12354, "side": "buy"},
        ]
        btc_app._check_bot_activity(trades)
        # All round to 0.1235, so bot should be detected
        btc_app.bot_banner.add_class.assert_called_with("active")

    def test_empty_trades_no_crash(self, btc_app):
        """Verify empty trades list doesn't crash."""
        btc_app._check_bot_activity([])
        # Should hide banner (no bot)
        btc_app.bot_banner.update.assert_called_with("")

    def test_banner_hidden_when_no_bot(self, btc_app):
        """Verify banner is hidden when no bot detected."""
        btc_app._check_bot_activity([])
        btc_app.bot_banner.remove_class.assert_called_with("active")


class TestRefreshStats:
    """Test refresh_stats method for UI update logic."""

    def test_refresh_updates_price_widget(self, btc_app):
        """Verify refresh_stats updates price widget."""
        btc_app.stats["last_price"] = 50000.0
        btc_app.refresh_stats()
        btc_app.price_widget.update_price.assert_called_with(50000.0)

    def test_refresh_updates_stats_widget(self, btc_app):
        """Verify refresh_stats updates stats widget with all info."""
        btc_app.stats = {
            "total_trades": 100,
            "last_price": 50000.0,
            "volume_today": 50.5,
            "avg_trade_size": 0.505,
            "largest_trade": {"side": "buy", "size": 5.0, "price": 49000.0},
            "tps": 2.5,
            "highest_tps": 5.0,
        }
        btc_app.refresh_stats()

        call_args = btc_app.stats_widget.update.call_args[0][0]
        assert "Total Trades: 100" in call_args
        assert "Volume Today: 50.500000 BTC" in call_args
        assert "Trades/sec (TPS): 2.50" in call_args
        assert "Highest TPS: 5.00" in call_args
        assert "Avg Trade Size: 0.505000 BTC" in call_args
        assert "Largest Trade:" in call_args
        assert "Audio:" in call_args

    def test_refresh_filters_trades_table(self, btc_app):
        """Verify trades table is filtered by current min size."""
        btc_app.filter_index = 2  # 0.01 BTC
        btc_app.recent_trades = [
            {"price": 50000.0, "size": 0.005, "side": "buy"},  # Filtered
            {"price": 50000.0, "size": 0.02, "side": "sell"},  # Included
            {"price": 50000.0, "size": 0.01, "side": "buy"},   # Included
        ]
        btc_app.refresh_stats()

        # trades_table.add_row should be called for filtered trades
        assert btc_app.trades_table.add_row.call_count == 2


class TestPlayClick:
    """Test _play_click method for audio playback."""

    def test_click_played_when_enabled(self, btc_app):
        """Verify click sound plays when audio enabled and sound loaded."""
        import cli as cli_module
        mock_sound = MagicMock()
        cli_module.click_sound = mock_sound
        btc_app.audio_enabled = True

        btc_app._play_click()

        mock_sound.play.assert_called_once()

    def test_click_not_played_when_disabled(self, btc_app):
        """Verify click sound doesn't play when audio disabled."""
        import cli as cli_module
        mock_sound = MagicMock()
        cli_module.click_sound = mock_sound
        btc_app.audio_enabled = False

        btc_app._play_click()

        mock_sound.play.assert_not_called()

    def test_no_crash_when_sound_not_loaded(self, btc_app):
        """Verify no crash when click_sound is None."""
        import cli as cli_module
        cli_module.click_sound = None
        btc_app.audio_enabled = True

        # Should not raise
        btc_app._play_click()


class TestPriceWidget:
    """Test PriceWidget class functionality."""

    def test_update_price_formats_correctly(self, mock_pygame):
        """Verify price is formatted with commas and 2 decimal places."""
        from cli import PriceWidget
        widget = PriceWidget()
        widget.update = MagicMock()

        widget.update_price(50000.5)

        call_args = widget.update.call_args[0][0]
        assert "$50,000.50" in call_args

    def test_update_price_large_value(self, mock_pygame):
        """Verify large price values are formatted correctly."""
        from cli import PriceWidget
        widget = PriceWidget()
        widget.update = MagicMock()

        widget.update_price(1234567.89)

        call_args = widget.update.call_args[0][0]
        assert "$1,234,567.89" in call_args


class TestConstants:
    """Test configuration constants are correctly defined."""

    def test_tps_window_positive(self):
        """Verify TPS_WINDOW is a positive integer."""
        from cli import TPS_WINDOW
        assert TPS_WINDOW > 0
        assert isinstance(TPS_WINDOW, int)

    def test_max_recent_trades_positive(self):
        """Verify MAX_RECENT_TRADES is a positive integer."""
        from cli import MAX_RECENT_TRADES
        assert MAX_RECENT_TRADES > 0
        assert isinstance(MAX_RECENT_TRADES, int)

    def test_filter_sizes_ascending(self):
        """Verify FILTER_SIZES are in ascending order."""
        from cli import BTCBeeperApp
        sizes = BTCBeeperApp.FILTER_SIZES
        assert sizes == sorted(sizes)
        assert all(s > 0 for s in sizes)

    def test_bot_detection_threshold_reasonable(self):
        """Verify BOT_DETECTION_THRESHOLD is reasonable."""
        from cli import BOT_DETECTION_THRESHOLD
        assert BOT_DETECTION_THRESHOLD >= 3  # At least 3 to avoid false positives
        assert BOT_DETECTION_THRESHOLD <= 20  # Not so high it never triggers


class TestEdgeCasesAndBoundary:
    """Test edge cases and boundary conditions."""

    def test_negative_price_handled(self, btc_app):
        """Verify negative prices don't crash (even if nonsensical)."""
        trade_data = {"price": "-100.00", "size": "0.5", "side": "buy"}
        btc_app._handle_trade(trade_data)
        assert btc_app.stats["last_price"] == -100.0

    def test_very_large_price(self, btc_app):
        """Verify extremely large prices are handled."""
        trade_data = {"price": "999999999.99", "size": "0.001", "side": "buy"}
        btc_app._handle_trade(trade_data)
        assert btc_app.stats["last_price"] == 999999999.99

    def test_very_small_trade_size(self, btc_app):
        """Verify extremely small trade sizes work."""
        btc_app.filter_index = 0  # Smallest filter: 0.0001
        trade_data = {"price": "50000.00", "size": "0.0001", "side": "buy"}
        btc_app._handle_trade(trade_data)
        assert btc_app.stats["total_trades"] == 1

    def test_very_large_trade_size(self, btc_app):
        """Verify large trade sizes are handled."""
        trade_data = {"price": "50000.00", "size": "1000.0", "side": "buy"}
        btc_app._handle_trade(trade_data)
        assert btc_app.stats["volume_today"] == 1000.0
        assert btc_app.stats["largest_trade"]["size"] == 1000.0

    def test_floating_point_precision(self, btc_app):
        """Verify floating point arithmetic is reasonably precise."""
        trades = [
            {"price": "50000.00", "size": "0.1", "side": "buy"},
            {"price": "50000.00", "size": "0.2", "side": "buy"},
            {"price": "50000.00", "size": "0.3", "side": "buy"},
        ]
        for t in trades:
            btc_app._handle_trade(t)
        # 0.1 + 0.2 + 0.3 should equal 0.6
        assert btc_app.stats["volume_today"] == pytest.approx(0.6, rel=1e-9)

    def test_rapid_filter_changes(self, btc_app):
        """Verify rapid filter changes don't cause issues."""
        for _ in range(100):
            btc_app.action_filter_up()
            btc_app.action_filter_down()
        assert btc_app.filter_index == 0

    def test_trade_with_unicode_side(self, btc_app):
        """Verify trades with unexpected side values are handled."""
        trade_data = {"price": "50000.00", "size": "0.5", "side": "買い"}
        btc_app._handle_trade(trade_data)
        assert btc_app.recent_trades[0]["side"] == "買い"

    def test_scientific_notation_price(self, btc_app):
        """Verify scientific notation prices are parsed."""
        trade_data = {"price": "5e4", "size": "0.5", "side": "buy"}
        btc_app._handle_trade(trade_data)
        assert btc_app.stats["last_price"] == 50000.0

    def test_largest_trade_with_same_size(self, btc_app):
        """Verify largest trade keeps first occurrence when sizes equal."""
        trades = [
            {"price": "50000.00", "size": "1.0", "side": "buy"},
            {"price": "51000.00", "size": "1.0", "side": "sell"},
        ]
        for t in trades:
            btc_app._handle_trade(t)
        # First trade with size 1.0 should be kept
        assert btc_app.stats["largest_trade"]["price"] == 50000.0


class TestInvalidInputHandling:
    """Test handling of invalid and malformed inputs."""

    def test_missing_price_field(self, btc_app):
        """Verify missing price field is handled gracefully (trade ignored and tracked)."""
        trade_data = {"size": "0.5", "side": "buy"}
        btc_app._handle_trade(trade_data)
        # Trade should be silently ignored - no crash, no stats update
        assert btc_app.stats["total_trades"] == 0
        assert btc_app.stats["invalid_trades"] == 1

    def test_missing_size_field(self, btc_app):
        """Verify missing size field is handled gracefully (trade ignored and tracked)."""
        trade_data = {"price": "50000.00", "side": "buy"}
        btc_app._handle_trade(trade_data)
        assert btc_app.stats["total_trades"] == 0
        assert btc_app.stats["invalid_trades"] == 1

    def test_non_numeric_price(self, btc_app):
        """Verify non-numeric price is handled gracefully (trade ignored and tracked)."""
        trade_data = {"price": "invalid", "size": "0.5", "side": "buy"}
        btc_app._handle_trade(trade_data)
        # Trade should be silently ignored - no crash, no stats update
        assert btc_app.stats["total_trades"] == 0
        assert btc_app.stats["invalid_trades"] == 1

    def test_non_numeric_size(self, btc_app):
        """Verify non-numeric size is handled gracefully (trade ignored and tracked)."""
        trade_data = {"price": "50000.00", "size": "big", "side": "buy"}
        btc_app._handle_trade(trade_data)
        # Trade should be silently ignored - no crash, no stats update
        assert btc_app.stats["total_trades"] == 0
        assert btc_app.stats["invalid_trades"] == 1

    def test_null_values_in_message(self, btc_app):
        """Verify null values in JSON are handled gracefully and tracked."""
        message = '{"type": "match", "price": null, "size": "0.5", "product_id": "BTC-USD"}'
        btc_app._process_message(message)
        # Trade should be silently ignored due to null price
        assert btc_app.stats["total_trades"] == 0
        assert btc_app.stats["invalid_trades"] == 1

    def test_deeply_nested_json(self, btc_app):
        """Verify deeply nested JSON doesn't cause issues."""
        message = json.dumps({
            "type": "match",
            "price": "50000.00",
            "size": "0.5",
            "side": "buy",
            "product_id": "BTC-USD",
            "extra": {"nested": {"deep": {"value": 123}}}
        })
        btc_app._process_message(message)
        assert btc_app.stats["total_trades"] == 1

    def test_message_with_extra_fields(self, btc_app):
        """Verify extra fields in messages are ignored."""
        message = json.dumps({
            "type": "match",
            "price": "50000.00",
            "size": "0.5",
            "side": "buy",
            "product_id": "BTC-USD",
            "unknown_field": "should be ignored",
            "another_unknown": 12345
        })
        btc_app._process_message(message)
        assert btc_app.stats["total_trades"] == 1

    def test_empty_string_price(self, btc_app):
        """Verify empty string price is handled gracefully (trade ignored)."""
        trade_data = {"price": "", "size": "0.5", "side": "buy"}
        btc_app._handle_trade(trade_data)
        # Trade should be silently ignored - no crash, no stats update
        assert btc_app.stats["total_trades"] == 0
        assert btc_app.stats["invalid_trades"] == 1

    def test_whitespace_only_json(self, btc_app):
        """Verify whitespace-only message is handled."""
        btc_app._handle_trade = MagicMock()
        btc_app._process_message("   ")
        btc_app._handle_trade.assert_not_called()


class TestErrorTracking:
    """Test error tracking for observable failure monitoring."""

    def test_parse_errors_tracked(self, btc_app):
        """Verify JSON parse errors are tracked in stats."""
        btc_app._process_message("{invalid json}")
        btc_app._process_message("not json at all")
        btc_app._process_message("")
        assert btc_app.stats["parse_errors"] == 3

    def test_invalid_trades_missing_price_tracked(self, btc_app):
        """Verify trades with missing price are tracked."""
        btc_app._handle_trade({"size": "0.5", "side": "buy"})
        assert btc_app.stats["invalid_trades"] == 1

    def test_invalid_trades_missing_size_tracked(self, btc_app):
        """Verify trades with missing size are tracked."""
        btc_app._handle_trade({"price": "50000", "side": "buy"})
        assert btc_app.stats["invalid_trades"] == 1

    def test_invalid_trades_bad_values_tracked(self, btc_app):
        """Verify trades with non-numeric values are tracked."""
        btc_app._handle_trade({"price": "bad", "size": "0.5", "side": "buy"})
        btc_app._handle_trade({"price": "50000", "size": "bad", "side": "buy"})
        assert btc_app.stats["invalid_trades"] == 2

    def test_valid_trade_does_not_increment_errors(self, btc_app):
        """Verify valid trades don't affect error counters."""
        btc_app._handle_trade({"price": "50000", "size": "0.5", "side": "buy"})
        assert btc_app.stats["invalid_trades"] == 0
        assert btc_app.stats["parse_errors"] == 0
        assert btc_app.stats["total_trades"] == 1

    def test_error_counters_initialized_to_zero(self, btc_app):
        """Verify error counters start at zero."""
        assert btc_app.stats["parse_errors"] == 0
        assert btc_app.stats["invalid_trades"] == 0


class TestOutputVerification:
    """Tests that verify actual output content matches expected values."""

    def test_stats_widget_format_complete(self, btc_app):
        """Verify stats widget contains all required information."""
        btc_app.stats = {
            "total_trades": 42,
            "last_price": 65432.10,
            "volume_today": 123.456789,
            "avg_trade_size": 2.939447,
            "largest_trade": {"side": "sell", "size": 10.5, "price": 65000.0},
            "tps": 3.5,
            "highest_tps": 7.2,
        }
        btc_app.audio_enabled = False
        btc_app.filter_index = 2  # 0.01

        btc_app.refresh_stats()

        call_args = btc_app.stats_widget.update.call_args[0][0]
        # Verify all stats are present with correct formatting
        assert "Total Trades: 42" in call_args
        assert "Volume Today: 123.456789 BTC" in call_args
        assert "Trades/sec (TPS): 3.50" in call_args
        assert "Highest TPS: 7.20" in call_args
        assert "Avg Trade Size: 2.939447 BTC" in call_args
        assert "Min Trade Size: 0.01 BTC" in call_args
        assert "Largest Trade: Sell 10.500000 BTC @ $65000.00" in call_args
        assert "Audio: OFF" in call_args

    def test_trades_table_row_format(self, btc_app):
        """Verify trades table rows are formatted correctly."""
        btc_app.recent_trades = [
            {"price": 50000.0, "size": 0.123456, "side": "buy"},
            {"price": 49999.99, "size": 1.0, "side": "sell"},
        ]
        btc_app.filter_index = 0

        btc_app.refresh_stats()

        # Check add_row was called with correct formatted values
        calls = btc_app.trades_table.add_row.call_args_list
        # Most recent trade first (reversed)
        assert calls[0][0] == ("Sell", "$49999.99", "1.000000")
        assert calls[1][0] == ("Buy", "$50000.00", "0.123456")

    def test_bot_banner_message_format(self, btc_app):
        """Verify bot banner displays correctly formatted message."""
        trades = [{"price": 50000.0, "size": 0.5, "side": "buy"} for _ in range(6)]
        btc_app._check_bot_activity(trades)

        call_args = btc_app.bot_banner.update.call_args[0][0]
        assert "Possible bot" in call_args
        assert "6" in call_args or "6+" in call_args
        assert "0.5" in call_args
        assert "$50,000.00" in call_args

    def test_error_message_format(self, btc_app):
        """Verify error messages are formatted correctly."""
        error_msg = {"type": "error", "message": "Rate limit exceeded"}
        btc_app._process_message(json.dumps(error_msg))

        call_args = btc_app.stats_widget.update.call_args[0][0]
        assert "[Error]:" in call_args
        assert "Rate limit exceeded" in call_args


class TestPriceWidgetAnimation:
    """Test PriceWidget animation behavior."""

    def test_animation_class_added(self, mock_pygame):
        """Verify animation adds correct CSS class."""
        from cli import PriceWidget
        widget = PriceWidget()
        widget.add_class = MagicMock()
        widget.set_timer = MagicMock(return_value=MagicMock())

        widget.animate("up")
        widget.add_class.assert_called_with("price-up")

        widget.animate("down")
        widget.add_class.assert_called_with("price-down")

    def test_previous_timer_stopped(self, mock_pygame):
        """Verify previous animation timer is stopped before new one."""
        from cli import PriceWidget
        widget = PriceWidget()
        widget.add_class = MagicMock()
        old_timer = MagicMock()
        widget.anim_timer = old_timer
        widget.set_timer = MagicMock(return_value=MagicMock())

        widget.animate("up")

        old_timer.stop.assert_called_once()

    def test_reset_animation_removes_classes(self, mock_pygame):
        """Verify reset removes both animation classes."""
        from cli import PriceWidget
        widget = PriceWidget()
        widget.remove_class = MagicMock()

        widget._reset_animation()

        assert widget.remove_class.call_count == 2
        widget.remove_class.assert_any_call("price-up")
        widget.remove_class.assert_any_call("price-down")


class TestIntegration:
    """Integration tests for message flow through the system."""

    def test_full_trade_flow(self, btc_app, frozen_time):
        """Test complete flow from message to statistics update."""
        with patch('time.time', return_value=frozen_time):
            message = json.dumps({
                "type": "match",
                "price": "50000.00",
                "size": "0.5",
                "side": "buy",
                "product_id": "BTC-USD"
            })

            btc_app._process_message(message)

            # Verify full chain of updates
            assert btc_app.stats["total_trades"] == 1
            assert btc_app.stats["last_price"] == 50000.0
            assert btc_app.stats["volume_today"] == 0.5
            assert len(btc_app.recent_trades) == 1
            assert len(btc_app.trade_timestamps) == 1
            btc_app.price_widget.update_price.assert_called()

    def test_sequential_trades_accumulate(self, btc_app, frozen_time):
        """Test multiple sequential trades accumulate correctly."""
        with patch('time.time', return_value=frozen_time):
            for i in range(10):
                message = json.dumps({
                    "type": "match",
                    "price": str(50000 + i * 10),
                    "size": "0.1",
                    "side": "buy" if i % 2 == 0 else "sell",
                    "product_id": "BTC-USD"
                })
                btc_app._process_message(message)

            assert btc_app.stats["total_trades"] == 10
            assert btc_app.stats["volume_today"] == pytest.approx(1.0, rel=1e-6)
            assert btc_app.stats["last_price"] == 50090.0

    def test_mixed_message_types(self, btc_app):
        """Test handling of mixed message types in sequence."""
        messages = [
            {"type": "ticker", "price": "50000.00", "product_id": "BTC-USD"},
            {"type": "match", "price": "50010.00", "size": "0.5", "side": "buy", "product_id": "BTC-USD"},
            {"type": "heartbeat", "sequence": 1},
            {"type": "match", "price": "50020.00", "size": "0.3", "side": "sell", "product_id": "BTC-USD"},
            {"type": "error", "message": "Test error"},
        ]

        for msg in messages:
            btc_app._process_message(json.dumps(msg))

        # Only matches should be counted as trades
        assert btc_app.stats["total_trades"] == 2
        # Last price should be from the last match
        assert btc_app.stats["last_price"] == 50020.0

    def test_high_volume_trades(self, btc_app, frozen_time):
        """Test system handles high volume of trades without issues."""
        with patch('time.time', return_value=frozen_time):
            for i in range(500):
                trade_data = {
                    "price": str(50000 + (i % 100)),
                    "size": "0.01",
                    "side": "buy" if i % 2 == 0 else "sell"
                }
                btc_app._handle_trade(trade_data)

            assert btc_app.stats["total_trades"] == 500
            assert btc_app.stats["volume_today"] == pytest.approx(5.0, rel=1e-6)
            # Recent trades capped at MAX_RECENT_TRADES
            from cli import MAX_RECENT_TRADES
            assert len(btc_app.recent_trades) == min(500, MAX_RECENT_TRADES)

    def test_price_direction_changes(self, btc_app):
        """Test alternating price directions trigger correct animations."""
        prices = [50000, 50100, 50050, 50200, 49900]
        expected_animations = [None, "up", "down", "up", "down"]

        btc_app.stats["last_price"] = 0  # Start fresh

        for price, expected in zip(prices, expected_animations):
            btc_app.price_widget.animate.reset_mock()
            btc_app._handle_trade({
                "price": str(price),
                "size": "0.5",
                "side": "buy"
            })

            if expected:
                btc_app.price_widget.animate.assert_called_with(expected)
            else:
                btc_app.price_widget.animate.assert_not_called()
