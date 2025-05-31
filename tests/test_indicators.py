import numpy as np

from app.indicators import bollinger_bands, rsi, atr, adx


def test_bollinger_shape():
    data = np.arange(100, dtype=float)
    lower, mid, upper = bollinger_bands(data)
    assert lower.shape == data.shape
    assert mid.shape == data.shape
    assert upper.shape == data.shape


def test_rsi_range():
    data = np.random.rand(100) * 100
    val = rsi(data)
    assert np.nanmin(val) >= 0
    assert np.nanmax(val) <= 100


def test_atr_positive():
    high = np.random.rand(100) * 100 + 100
    low = high - np.random.rand(100) * 5
    close = (high + low) / 2
    out = atr(high, low, close)
    assert np.all(np.nan_to_num(out) >= 0)


def test_adx_nan_start():
    high = np.linspace(1, 2, 100)
    low = high - 0.5
    close = (high + low) / 2
    out = adx(high, low, close)
    assert np.isnan(out[:28]).all()  # 2*14 window
