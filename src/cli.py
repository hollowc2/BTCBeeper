import asyncio
import json
import os
import websockets
from rich.live import Live
from rich.table import Table
from rich import box
import pygame

# Path to your click sound
CLICK_SOUND_PATH = "data/sounds/geiger_click.wav"

# WebSocket server URL
WS_URL = "ws://localhost:8000/ws"

# Store latest stats
stats = {
    "total_trades": 0,
    "last_price": 0.0,
    "volume_today": 0.0,
    "price_change_24h": 0.0
}

recent_trades = []  # Keep last N trades

def make_table():
    """Create a rich Table for live display."""
    table = Table(title="📈 BTC CLI Visualizer", box=box.SIMPLE_HEAVY)
    table.add_column("Metric", justify="right")
    table.add_column("Value", justify="left")

    table.add_row("Last Price", f"${stats['last_price']:.2f}")
    table.add_row("Total Trades", str(stats['total_trades']))
    table.add_row("Volume Today", f"{stats['volume_today']:.6f} BTC")
    table.add_row("24h Change", f"{stats['price_change_24h']:.2f}%")

    table.add_section()
    table.add_row("[bold]Recent Trades[/bold]", "")
    for trade in reversed(recent_trades[-5:]):
        price = f"${trade['price']:.2f}"
        size = f"{trade['size']:.6f} BTC"
        side = trade["side"]
        table.add_row(f"{side.capitalize()} @ {price}", size)

    return table

async def play_click():
    """Play click sound using pygame."""
    if os.path.exists(CLICK_SOUND_PATH):
        click_sound.play()

async def run_cli():
    global stats, recent_trades
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
                        await play_click()

                    elif msg_type == "btc_ticker":
                        stats["last_price"] = payload["price"]
                        stats["price_change_24h"] = payload.get("price_change_24h", stats["price_change_24h"])

                    live.update(make_table())

                except Exception as e:
                    print(f"[Error]: {e}")
                    break

if __name__ == "__main__":
    print("Starting BTC CLI Visualizer...")
    print("Press Ctrl+C to exit.")

    # Initialize pygame mixer once
    pygame.mixer.init()
    if os.path.exists(CLICK_SOUND_PATH):
        click_sound = pygame.mixer.Sound(CLICK_SOUND_PATH)
    else:
        click_sound = None
        print("Warning: click sound file not found!")

    asyncio.run(run_cli())
