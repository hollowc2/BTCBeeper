#!/usr/bin/env python3
import os

import pygame

from . import cli as cli_module


def main() -> None:
    click_sound = None
    click_sound_sell = None

    try:
        pygame.mixer.init()
    except pygame.error as e:
        cli_module.logger.warning("Audio init failed: %s", e)
    else:
        if os.path.exists(cli_module.CLICK_SOUND_PATH):
            click_sound = pygame.mixer.Sound(cli_module.CLICK_SOUND_PATH)
        else:
            cli_module.logger.warning("Buy sound not found: %s", cli_module.CLICK_SOUND_PATH)

        if os.path.exists(cli_module.SELL_SOUND_PATH):
            click_sound_sell = pygame.mixer.Sound(cli_module.SELL_SOUND_PATH)
        else:
            cli_module.logger.warning("Sell sound not found: %s", cli_module.SELL_SOUND_PATH)

    cli_module.BTCBeeperApp(click_sound=click_sound, click_sound_sell=click_sound_sell).run()


if __name__ == "__main__":
    main()
