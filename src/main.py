#!/usr/bin/env python3
"""BTCBeeper - Live BTC Audio & Visual Tape."""

import os

import pygame

from . import cli as cli_module


def main() -> None:
    """Main entry point for BTCBeeper application."""
    print("\033[2J\033[H", end="", flush=True)
    print("Starting BTC CLI Visualizer (Textual)...")
    print("Press Ctrl+C to exit. Press 'a' to toggle audio.")

    pygame.mixer.init()

    if os.path.exists(cli_module.CLICK_SOUND_PATH):
        cli_module.click_sound = pygame.mixer.Sound(cli_module.CLICK_SOUND_PATH)
    else:
        print(f"Warning: click sound file not found at {cli_module.CLICK_SOUND_PATH}!")

    cli_module.BTCBeeperApp().run()


if __name__ == "__main__":
    main()
