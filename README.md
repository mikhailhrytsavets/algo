# Bybit Mean-Reversion Algobot

Minimal, dependency-light crypto algobot for Bybit USDT-Perp contracts (Unified Margin).

## Quick start (Linux / macOS / WSL)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy config & edit keys
cp settings.toml.example settings.toml
vim settings.toml

# Run tests
pytest tests

# Launch bot (default: testnet)
python main.py
```

### Production checklist

* Switch `testnet = false` in `settings.toml`.
* Set real API keys with trade permissions.
* Monitor Telegram notifications.
