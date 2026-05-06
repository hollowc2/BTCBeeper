# BTCBeeper

<div style="display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 24px; margin: 16px 0 28px 0;">
  <div style="flex: 1 1 320px; max-width: 640px; text-align: left; font-size: 1.08em; line-height: 1.5;">
    Live BTC/USD trades from Coinbase, stats in the terminal, a click for every trade.
  </div>
  <div style="flex: 0 0 auto; text-align: right;">
    <img src="data/images/icon.png" alt="BTCBeeper" style="width: 260px; max-width: 42vw; height: auto;"/>
  </div>
</div>

<p align="center">
  <img src="data/images/btcbeeper.jpg" alt="BTCBeeper terminal screenshot" width="100%"/>
</p>

<p align="center">
  <img src="data/images/btcbeeper.gif" alt="BTCBeeper demo animation" width="100%"/>
</p>

## Install

```bash
git clone <repository-url>
cd BTCBeeper
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python -m src.main
```

## Panels

**SESSION** — Uptime, session high/low, price range, and VWAP (colored green/red vs current price).

**TRADES** — Trade count, buy/sell volume split, total USD volume, average size, and largest trade.

**ACTIVITY** — Trades/sec, size filter, order flow imbalance (% buy vs sell), and error counts.

**Heatmap** — Trade size distribution across all incoming trades.

**Trades table** — Last 16 filtered trades. Click a row to expand order IDs and timestamp.

## Controls

| Key | Action |
|-----|--------|
| `a` | Toggle audio |
| `[` / `]` | Adjust min trade size filter |
| `q` | Quit |

## Sounds

There are 10 click variations in `data/sounds/`. Defaults are `geiger_click7.wav` for buys and `geiger_click4.wav` for sells.

Override the sound path with:

```bash
BTCBEEPER_SOUND_PATH=data/sounds/geiger_click1.wav python -m src.main
```

To regenerate the sound set:

```bash
pip install numpy scipy
python src/click_generator.py
```

## License

MIT. Not financial advice.
