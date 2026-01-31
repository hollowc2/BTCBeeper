# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BTCBeeper is a real-time Bitcoin trade visualizer with audio feedback. It streams live BTC/USD trades from Coinbase WebSocket API, displays statistics in a terminal-based TUI (Textual framework), and plays Geiger-counter-style audio clicks for each trade.

## Commands

### Run the application
```bash
python -m src.main
```

### Run tests
```bash
python -m pytest
```

### Run a single test
```bash
python -m pytest tests/test_cli.py::TestClassName::test_method_name -v
```

### Generate click sounds (requires numpy/scipy)
```bash
python src/click_generator.py
```

## Architecture

**Entry Point:** `src/main.py` initializes pygame mixer, loads the click sound, and runs `BTCBeeperApp().run()`

**Core Application:** `src/cli.py` contains:
- `PriceWidget`: Custom Textual widget for animated price display (green/red color coding)
- `BTCBeeperApp`: Main application handling WebSocket connection, trade processing, statistics, and UI

**Sound Generator:** `src/click_generator.py` generates WAV files with various frequencies/durations (only needed for customizing sounds)

**Data Flow:**
1. WebSocket connects to `wss://ws-feed.exchange.coinbase.com`
2. Subscribes to `matches`, `ticker`, `heartbeat` channels for BTC-USD
3. Trade messages are filtered by size threshold (5 levels: 0.0001 to 1.0 BTC)
4. Qualifying trades update statistics, play audio, and appear in trades table

**Key Constants in cli.py:**
- `TPS_WINDOW = 10` - seconds for trades-per-second calculation
- `MAX_RECONNECT_ATTEMPTS = 5` - WebSocket retry limit
- `BOT_DETECTION_THRESHOLD = 5` - identical trade sizes to flag bot activity

## Code Style

- Use Conventional Commits: `fix(module): description (impact: effect)` or `feat(module): description (added: functions)`
- Keep commits under 100 characters
- Follow PEP8 with type hints where practical
- Include docstrings for public functions/classes
- Add inline comments for financial domain logic
