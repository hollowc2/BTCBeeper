import asyncio
import json
import os
import websockets
from rich.live import Live
from rich.table import Table
from rich import box
import pygame
import time
import threading

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
last_heartbeat = None
connection_status = "disconnected"

order_book = None  # No longer used

# For keypress listening (audio toggle)
def listen_for_keys():
    global audio_enabled
    try:
        import termios, tty, sys, select
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        while True:
            if select.select([sys.stdin], [], [], 0.1)[0]:
                ch = sys.stdin.read(1)
                if ch.lower() == 'a':
                    audio_enabled = not audio_enabled
    except Exception:
        pass
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            pass

def make_table():
    """Create a rich Table for live display."""
    table = Table(title="📈 BTC CLI Visualizer", box=box.SIMPLE_HEAVY)
    table.add_column("Metric", justify="right")
    table.add_column("Value", justify="left")

    table.add_row("Last Price", f"${stats['last_price']:.2f}")
    table.add_row("Total Trades", str(stats['total_trades']))
    table.add_row("Volume Today", f"{stats['volume_today']:.6f} BTC")
    table.add_row("24h Change", f"{stats['price_change_24h']:.2f}%")
    table.add_row("Trades/sec (TPS)", f"{stats['tps']:.2f}")
    table.add_row("Highest TPS", f"{stats['highest_tps']:.2f}")
    table.add_row("Avg Trade Size", f"{stats['avg_trade_size']:.6f} BTC")
    if stats['largest_trade']:
        lt = stats['largest_trade']
        table.add_row("Largest Trade", f"{lt['side'].capitalize()} {lt['size']:.6f} BTC @ ${lt['price']:.2f}")
    table.add_section()
    table.add_row("[bold]Recent Trades (10)[/bold]", "")
    for trade in reversed(recent_trades[-10:]):
        price = f"${trade['price']:.2f}"
        size = f"{trade['size']:.6f} BTC"
        side = trade["side"]
        table.add_row(f"{side.capitalize()} @ {price}", size)
    return table

async def play_click():
    """Play click sound using pygame."""
    if audio_enabled and os.path.exists(CLICK_SOUND_PATH) and click_sound:
        click_sound.play()

def update_tps():
    now = time.time()
    # Remove timestamps outside the window
    while trade_timestamps and now - trade_timestamps[0] > TPS_WINDOW:
        trade_timestamps.pop(0)
    stats['tps'] = len(trade_timestamps) / TPS_WINDOW
    if stats['tps'] > stats['highest_tps']:
        stats['highest_tps'] = stats['tps']

async def run_cli():
    global stats, recent_trades
    try:
        async with websockets.connect(WS_URL) as websocket:
            with Live(make_table(), refresh_per_second=5) as live:
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        msg_type = data.get("type")
                        payload = data.get("data", {})

                        if msg_type == "btc_trade":
                            stats["total_trades"] += 1
                            stats["last_price"] = payload["price"]
                            stats["volume_today"] += payload["size"]
                            recent_trades.append(payload)
                            # TPS
                            trade_timestamps.append(time.time())
                            update_tps()
                            # Avg trade size
                            stats["avg_trade_size"] = stats["volume_today"] / stats["total_trades"] if stats["total_trades"] else 0.0
                            # Largest trade
                            if not stats["largest_trade"] or payload["size"] > stats["largest_trade"]["size"]:
                                stats["largest_trade"] = payload.copy()
                            await play_click()

                        elif msg_type == "btc_ticker":
                            stats["last_price"] = payload["price"]
                            stats["price_change_24h"] = payload.get("price_change_24h", stats["price_change_24h"])
                        # Remove order book and connection/heartbeat logic
                        live.update(make_table())

                    except asyncio.CancelledError:
                        # Clean exit on cancellation
                        break
                    except Exception as e:
                        print(f"[Error]: {e}")
                        break
    except asyncio.CancelledError:
        # Clean exit on cancellation
        pass
    except Exception as e:
        print(f"[Connection Error]: {e}")
        connection_status = "disconnected"

if __name__ == "__main__":
    # Clear the terminal before starting
    os.system("clear" if os.name == "posix" else "cls")
    print("Starting BTC CLI Visualizer...")
    print("Press Ctrl+C to exit. Press 'a' to toggle audio.")

    # Initialize pygame mixer once
    pygame.mixer.init()
    if os.path.exists(CLICK_SOUND_PATH):
        click_sound = pygame.mixer.Sound(CLICK_SOUND_PATH)
    else:
        click_sound = None
        print("Warning: click sound file not found!")

    # Start keypress listener in a thread
    key_thread = threading.Thread(target=listen_for_keys, daemon=True)
    key_thread.start()

    try:
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        print("\nExiting cleanly. Goodbye!")
    finally:
        pygame.mixer.quit()
