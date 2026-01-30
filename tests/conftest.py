"""Pytest configuration and shared fixtures for BTCBeeper tests."""

import time
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_pygame():
    """Mock pygame mixer to avoid audio initialization."""
    with patch("pygame.mixer.init"), patch("pygame.mixer.Sound"):
        yield


@pytest.fixture
def btc_app(mock_pygame):
    """Create a BTCBeeperApp instance for testing without running the full app."""
    # Import here to ensure pygame mock is in place
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    from cli import BTCBeeperApp

    app = BTCBeeperApp()
    # Mock widgets that would normally be created by compose()
    app.price_widget = MagicMock()
    app.stats_widget = MagicMock()
    app.trades_table = MagicMock()
    app.bot_banner = MagicMock()
    # Mock set_timer to avoid requiring an event loop
    app.set_timer = MagicMock(return_value=MagicMock())
    return app


@pytest.fixture
def sample_trade_match():
    """Sample trade match message from Coinbase WebSocket."""
    return {
        "type": "match",
        "trade_id": 12345,
        "maker_order_id": "abc123",
        "taker_order_id": "def456",
        "side": "buy",
        "size": "0.5",
        "price": "50000.00",
        "product_id": "BTC-USD",
        "sequence": 1,
        "time": "2024-01-15T12:00:00.000000Z"
    }


@pytest.fixture
def sample_ticker_message():
    """Sample ticker message from Coinbase WebSocket."""
    return {
        "type": "ticker",
        "product_id": "BTC-USD",
        "price": "50500.00",
        "open_24h": "49000.00",
        "volume_24h": "1234.56789",
        "low_24h": "48500.00",
        "high_24h": "51000.00",
        "volume_30d": "123456.789",
        "best_bid": "50499.00",
        "best_ask": "50501.00"
    }


@pytest.fixture
def sample_error_message():
    """Sample error message from Coinbase WebSocket."""
    return {
        "type": "error",
        "message": "Test error message",
        "reason": "test"
    }


@pytest.fixture
def frozen_time():
    """Fixture to provide a controlled time for testing."""
    return 1705320000.0  # Fixed timestamp for reproducible tests


@pytest.fixture
def click_params():
    """Sample click parameters for sound generation tests."""
    return {
        "filename": "test_click.wav",
        "duration": 0.004,
        "frequency": 2000,
        "sine_amp": 0.3,
        "noise_amp": 0.2,
        "decay": 10,
        "double": False
    }
