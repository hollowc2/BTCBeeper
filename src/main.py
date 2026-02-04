#!/usr/bin/env python3
import os

import pygame

from . import cli as cli_module


def main() -> None:
    pygame.mixer.init()

    if os.path.exists(cli_module.CLICK_SOUND_PATH):
        cli_module.click_sound = pygame.mixer.Sound(cli_module.CLICK_SOUND_PATH)
    else:
        cli_module.logger.warning("Buy sound not found: %s", cli_module.CLICK_SOUND_PATH)

    if os.path.exists(cli_module.SELL_SOUND_PATH):
        cli_module.click_sound_sell = pygame.mixer.Sound(cli_module.SELL_SOUND_PATH)
    else:
        cli_module.logger.warning("Sell sound not found: %s", cli_module.SELL_SOUND_PATH)

    cli_module.BTCBeeperApp().run()


if __name__ == "__main__":
    main()
