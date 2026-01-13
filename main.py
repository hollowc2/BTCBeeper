#!/usr/bin/env python3
"""
BTCBeeper - Live BTC Audio & Visual Tape
Primary entry point for the TUI application.
"""

import os
import sys
import pygame
from pathlib import Path

# Add src directory to path to allow imports
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

# Import after path setup
import cli as cli_module


def clear_screen() -> None:
    """Clear the terminal screen in a cross-platform way."""
    if os.name == "posix":
        # Use ANSI escape sequence instead of os.system
        print("\033[2J\033[H", end="")
    else:
        # Windows
        os.system("cls")


def main() -> None:
    """Main entry point for BTCBeeper application."""
    clear_screen()
    print("Starting BTC CLI Visualizer (Textual)...")
    print("Press Ctrl+C to exit. Press 'a' to toggle audio.")
    
    # Initialize pygame mixer for audio
    pygame.mixer.init()
    
    # Load click sound if available (using path relative to root)
    click_sound_path = cli_module.CLICK_SOUND_PATH
    if os.path.exists(click_sound_path):
        cli_module.click_sound = pygame.mixer.Sound(click_sound_path)
    else:
        cli_module.click_sound = None
        print(f"Warning: click sound file not found at {click_sound_path}!")
    
    # Run the TUI application
    cli_module.BTCBeeperApp().run()


if __name__ == "__main__":
    main()
