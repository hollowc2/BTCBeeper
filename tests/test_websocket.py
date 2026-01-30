import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import websockets


def create_mock_websocket(messages=None, send_capture=None):
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
    @pytest.mark.asyncio
    async def test_sends_subscription_message(self, btc_app):
        messages_sent = []
        connection_count = [0]

        def mock_connect(*args, **kwargs):
            connection_count[0] += 1
            if connection_count[0] > 1:
                raise websockets.exceptions.WebSocketException("Test complete")
            mock_ws = create_mock_websocket(send_capture=messages_sent)
            return AsyncContextManagerMock(mock_ws)

        with patch('websockets.connect', side_effect=mock_connect):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()

        assert len(messages_sent) >= 1
        sub_msg = json.loads(messages_sent[0])
        assert sub_msg["type"] == "subscribe"
        assert "BTC-USD" in sub_msg["product_ids"]
        assert "matches" in sub_msg["channels"]
        assert "ticker" in sub_msg["channels"]
        assert "heartbeat" in sub_msg["channels"]

    @pytest.mark.asyncio
    async def test_processes_incoming_messages(self, btc_app):
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

        assert btc_app.stats["total_trades"] >= 1

    @pytest.mark.asyncio
    async def test_reconnection_on_disconnect(self, btc_app):
        connection_attempts = [0]

        def failing_connect(*args, **kwargs):
            connection_attempts[0] += 1
            raise websockets.exceptions.WebSocketException("Connection failed")

        with patch('websockets.connect', side_effect=failing_connect):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()

        from cli import MAX_RECONNECT_ATTEMPTS
        assert connection_attempts[0] == MAX_RECONNECT_ATTEMPTS

    @pytest.mark.asyncio
    async def test_reconnection_resets_on_success(self, btc_app):
        # Counter resets to 0 on successful connect, then increments on close.
        # 3 successful connects (each resets), then 4 failures to reach max attempts = 7 total.
        connection_attempts = [0]

        def connect_sequence(*args, **kwargs):
            connection_attempts[0] += 1
            if connection_attempts[0] <= 3:
                mock_ws = create_mock_websocket(messages=[])
                return AsyncContextManagerMock(mock_ws)
            else:
                raise websockets.exceptions.WebSocketException("Connection failed")

        with patch('websockets.connect', side_effect=connect_sequence):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()

        assert connection_attempts[0] == 7

    @pytest.mark.asyncio
    async def test_connection_error_updates_widget(self, btc_app):
        def failing_connect(*args, **kwargs):
            raise ConnectionError("Network unreachable")

        with patch('websockets.connect', side_effect=failing_connect):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()

        calls = btc_app.stats_widget.update.call_args_list
        assert any("[Connection Error]" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_max_reconnect_reached_shows_failure(self, btc_app):
        def failing_connect(*args, **kwargs):
            raise OSError("Connection failed")

        with patch('websockets.connect', side_effect=failing_connect):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()

        calls = btc_app.stats_widget.update.call_args_list
        assert any("[Connection Failed]" in str(call) for call in calls)


class TestWebSocketMessageTypes:
    @pytest.mark.asyncio
    async def test_handles_oserror(self, btc_app):
        def failing_connect(*args, **kwargs):
            raise OSError("System error")
        with patch('websockets.connect', side_effect=failing_connect):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()

    @pytest.mark.asyncio
    async def test_handles_connection_error(self, btc_app):
        def failing_connect(*args, **kwargs):
            raise ConnectionError("Connection refused")
        with patch('websockets.connect', side_effect=failing_connect):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()


class TestSubscriptionMessage:
    @pytest.mark.asyncio
    async def test_subscription_message_matches_coinbase_api(self, btc_app):
        messages_sent = []
        connection_count = [0]

        def mock_connect(*args, **kwargs):
            connection_count[0] += 1
            if connection_count[0] > 1:
                raise websockets.exceptions.WebSocketException("Test complete")
            mock_ws = create_mock_websocket(send_capture=messages_sent)
            return AsyncContextManagerMock(mock_ws)

        with patch('websockets.connect', side_effect=mock_connect):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                await btc_app._ws_loop()

        assert len(messages_sent) >= 1
        sub_msg = json.loads(messages_sent[0])
        assert sub_msg["type"] == "subscribe"
        assert isinstance(sub_msg["product_ids"], list)
        assert isinstance(sub_msg["channels"], list)
        assert len(sub_msg["product_ids"]) > 0
        assert len(sub_msg["channels"]) > 0
        assert "BTC-USD" in sub_msg["product_ids"]
        assert "matches" in sub_msg["channels"]
