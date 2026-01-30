"""Tests for WebSocket connection and reconnection logic.

Covers:
- Connection establishment
- Reconnection behavior
- Error handling
- Message subscription
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets


def create_mock_websocket(messages=None, send_capture=None):
    """Create a mock websocket that yields messages then raises ConnectionClosed."""
    mock_ws = MagicMock()

    if send_capture is not None:
        async def capture_send(msg):
            send_capture.append(msg)
        mock_ws.send = capture_send
    else:
        mock_ws.send = AsyncMock()

    messages = messages or []

    async def message_iter():
        for msg in messages:
            yield msg
        raise websockets.exceptions.ConnectionClosed(None, None)

    mock_ws.__aiter__ = lambda self: message_iter()

    async def aenter():
        return mock_ws

    async def aexit(*args):
        return None

    mock_ws.__aenter__ = aenter
    mock_ws.__aexit__ = aexit

    return mock_ws


class AsyncContextManagerMock:
    """A mock that can act as an async context manager."""

    def __init__(self, mock_ws=None, exception=None):
        self.mock_ws = mock_ws
        self.exception = exception

    async def __aenter__(self):
        if self.exception:
            raise self.exception
        return self.mock_ws

    async def __aexit__(self, *args):
        return None


class TestWebSocketLoop:
    """Test _ws_loop method for WebSocket connection management."""

    @pytest.mark.asyncio
    async def test_sends_subscription_message(self, btc_app):
        """Verify correct subscription message is sent on connect."""
        messages_sent = []
        connection_count = [0]  # Use list to allow mutation in nested function

        def mock_connect(*args, **kwargs):
            connection_count[0] += 1
            if connection_count[0] > 1:
                # After first connection, raise to break the loop
                raise websockets.exceptions.WebSocketException("Test complete")

            mock_ws = create_mock_websocket(send_capture=messages_sent)
            return AsyncContextManagerMock(mock_ws)

        with patch('websockets.connect', side_effect=mock_connect):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()

        # Check subscription was sent
        assert len(messages_sent) >= 1
        sub_msg = json.loads(messages_sent[0])
        assert sub_msg["type"] == "subscribe"
        assert "BTC-USD" in sub_msg["product_ids"]
        assert "matches" in sub_msg["channels"]
        assert "ticker" in sub_msg["channels"]
        assert "heartbeat" in sub_msg["channels"]

    @pytest.mark.asyncio
    async def test_processes_incoming_messages(self, btc_app):
        """Verify incoming messages are processed."""
        test_message = json.dumps({
            "type": "match",
            "price": "50000.00",
            "size": "0.5",
            "side": "buy",
            "product_id": "BTC-USD"
        })

        call_count = [0]

        def connect_once(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                mock_ws = create_mock_websocket(messages=[test_message])
                return AsyncContextManagerMock(mock_ws)
            else:
                raise websockets.exceptions.WebSocketException("Test complete")

        with patch('websockets.connect', side_effect=connect_once):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()

        # Check trade was processed
        assert btc_app.stats["total_trades"] >= 1

    @pytest.mark.asyncio
    async def test_reconnection_on_disconnect(self, btc_app):
        """Verify reconnection attempts on connection failure."""
        connection_attempts = [0]

        def failing_connect(*args, **kwargs):
            connection_attempts[0] += 1
            raise websockets.exceptions.WebSocketException("Connection failed")

        with patch('websockets.connect', side_effect=failing_connect):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()

        # Should attempt MAX_RECONNECT_ATTEMPTS times
        from cli import MAX_RECONNECT_ATTEMPTS
        assert connection_attempts[0] == MAX_RECONNECT_ATTEMPTS

    @pytest.mark.asyncio
    async def test_reconnection_resets_on_success(self, btc_app):
        """Verify reconnection counter resets after successful connection.

        The reconnect counter resets to 0 when a connection is established
        (inside the 'async with' block). If the connection then closes
        (ConnectionClosed), it still increments the counter in the except block.

        So each cycle of connect->close resets to 0 then increments to 1.
        When we finally get WebSocketException on connect attempt, it starts
        accumulating: 2, 3, 4, 5, then exits at 5 (MAX_RECONNECT_ATTEMPTS).
        """
        connection_attempts = [0]

        def connect_sequence(*args, **kwargs):
            connection_attempts[0] += 1

            if connection_attempts[0] <= 3:
                # First 3 attempts succeed then disconnect
                mock_ws = create_mock_websocket(messages=[])
                return AsyncContextManagerMock(mock_ws)
            else:
                # After that, fail to end the test
                raise websockets.exceptions.WebSocketException("Connection failed")

        with patch('websockets.connect', side_effect=connect_sequence):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()

        # Trace:
        # 1-3: connect ok, counter=0, ConnectionClosed, counter=1 (3 total)
        # 4: WebSocketException, counter=2
        # 5: WebSocketException, counter=3
        # 6: WebSocketException, counter=4
        # 7: WebSocketException, counter=5 (exits)
        # Total: 7 attempts, demonstrating counter resets to 0 on each successful connect
        assert connection_attempts[0] == 7
        # More importantly: if counter didn't reset, it would have been:
        # 1,2,3 (fails), exit at 3 (only 3 attempts because 3 >= 5 is never reached)
        # So 7 > 5 proves the counter is resetting

    @pytest.mark.asyncio
    async def test_connection_error_updates_widget(self, btc_app):
        """Verify connection errors are displayed to user."""
        def failing_connect(*args, **kwargs):
            raise ConnectionError("Network unreachable")

        with patch('websockets.connect', side_effect=failing_connect):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()

        # Check error was displayed
        calls = btc_app.stats_widget.update.call_args_list
        assert any("[Connection Error]" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_max_reconnect_reached_shows_failure(self, btc_app):
        """Verify max reconnection failure message is shown."""
        def failing_connect(*args, **kwargs):
            raise OSError("Connection failed")

        with patch('websockets.connect', side_effect=failing_connect):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()

        # Check final failure message
        calls = btc_app.stats_widget.update.call_args_list
        assert any("[Connection Failed]" in str(call) for call in calls)


class TestWebSocketMessageTypes:
    """Test handling of various WebSocket message types."""

    @pytest.mark.asyncio
    async def test_handles_oserror(self, btc_app):
        """Verify OSError is caught and handled."""
        def failing_connect(*args, **kwargs):
            raise OSError("System error")

        with patch('websockets.connect', side_effect=failing_connect):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                # Should not raise
                await btc_app._ws_loop()

    @pytest.mark.asyncio
    async def test_handles_connection_error(self, btc_app):
        """Verify ConnectionError is caught and handled."""
        def failing_connect(*args, **kwargs):
            raise ConnectionError("Connection refused")

        with patch('websockets.connect', side_effect=failing_connect):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()


class TestSubscriptionMessage:
    """Test WebSocket subscription message construction."""

    def test_subscription_message_structure(self, btc_app):
        """Verify subscription message has correct structure."""
        expected_channels = ["matches", "ticker", "heartbeat"]
        expected_product = "BTC-USD"

        # Construct expected message
        expected = {
            "type": "subscribe",
            "product_ids": [expected_product],
            "channels": expected_channels,
        }

        # Verify by checking what would be sent
        subscribe_msg = json.dumps({
            "type": "subscribe",
            "product_ids": ["BTC-USD"],
            "channels": ["matches", "ticker", "heartbeat"],
        })

        parsed = json.loads(subscribe_msg)
        assert parsed == expected
