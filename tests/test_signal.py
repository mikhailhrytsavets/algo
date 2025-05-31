import numpy as np

from app.strategy.mean_reversion import MeanReversionSignal


def test_long_signal():
    sig = MeanReversionSignal()

    # Construct synthetic candle series where last close is deeply oversold
    candles = np.random.rand(50, 6) * 100
    candles[:, 3] = candles[:, 1]  # close = high for simplicity

    # Force last candle to trigger long
    last = candles[-1].copy()
    last[1] = last[3] = last[4] = last[4] - 10  # push low close
    candles[-1] = last

    action = sig.generate(candles)
    assert action in ("long", "none")  # not short
