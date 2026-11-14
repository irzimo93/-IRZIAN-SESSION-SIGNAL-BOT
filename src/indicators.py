from decimal import Decimal

ZERO = Decimal("0")
ONE = Decimal("1")


def ema_series(values, period):
    if period < 1:
        raise ValueError("Period must be positive")

    result = [None] * len(values)

    if len(values) < period:
        return result

    seed = sum(values[:period]) / Decimal(period)
    result[period - 1] = seed

    multiplier = Decimal("2") / Decimal(period + 1)
    previous = seed

    for index in range(period, len(values)):
        previous = (
            values[index] * multiplier
            + previous * (ONE - multiplier)
        )
        result[index] = previous

    return result


def wilder_series(values, period):
    result = [None] * len(values)

    if period < 1:
        raise ValueError("Period must be positive")

    if len(values) < period:
        return result

    previous = sum(values[:period]) / Decimal(period)
    result[period - 1] = previous

    for index in range(period, len(values)):
        previous = (
            previous * Decimal(period - 1) + values[index]
        ) / Decimal(period)

        result[index] = previous

    return result


def calculate_indicators(candles):
    if not candles:
        raise ValueError("Candles cannot be empty")

    closes = [c.close for c in candles]
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    volumes = [c.volume for c in candles]

    if any(not value.is_finite() for series in
           (closes, highs, lows, volumes) for value in series):
        raise ValueError("Non-finite input")

    # EMA
    ema20 = ema_series(closes, 20)
    ema50 = ema_series(closes, 50)
    ema200 = ema_series(closes, 200)

    # RSI 14 - Wilder smoothing
    changes = [closes[i] - closes[i - 1]
               for i in range(1, len(closes))]

    gains = [max(change, ZERO) for change in changes]
    losses = [max(-change, ZERO) for change in changes]

    avg_gains = wilder_series(gains, 14)
    avg_losses = wilder_series(losses, 14)

    rsi = [None] * len(candles)

    for i in range(14, len(candles)):
        gain = avg_gains[i - 1]
        loss = avg_losses[i - 1]

        if loss == ZERO:
            rsi[i] = Decimal("50") if gain == ZERO else Decimal("100")
        else:
            rs = gain / loss
            rsi[i] = Decimal("100") - (
                Decimal("100") / (ONE + rs)
            )

    # MACD 12 / 26 / 9
    fast = ema_series(closes, 12)
    slow = ema_series(closes, 26)

    macd = [None] * len(candles)
    macd_values = []
    macd_indexes = []

    for i in range(len(candles)):
        if fast[i] is not None and slow[i] is not None:
            value = fast[i] - slow[i]
            macd[i] = value
            macd_values.append(value)
            macd_indexes.append(i)

    signal_values = ema_series(macd_values, 9)
    signal = [None] * len(candles)
    histogram = [None] * len(candles)

    for index, original_index in enumerate(macd_indexes):
        if signal_values[index] is not None:
            signal[original_index] = signal_values[index]
            histogram[original_index] = (
                macd[original_index] - signal_values[index]
            )

    # VWAP - cumulative over supplied candles
    cumulative_value = ZERO
    cumulative_volume = ZERO
    vwap = [None] * len(candles)

    for i, candle in enumerate(candles):
        typical_price = (
            candle.high + candle.low + candle.close
        ) / Decimal("3")

        cumulative_value += typical_price * candle.volume
        cumulative_volume += candle.volume

        if cumulative_volume > ZERO:
            vwap[i] = cumulative_value / cumulative_volume

    # ATR 14 - Wilder smoothing
    true_ranges = []

    for i in range(len(candles)):
        if i == 0:
            true_range = highs[i] - lows[i]
        else:
            true_range = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )

        true_ranges.append(true_range)

    atr = wilder_series(true_ranges, 14)

    def latest(series):
        return next(
            (value for value in reversed(series) if value is not None),
            None
        )

    return {
        "ema20": latest(ema20),
        "ema50": latest(ema50),
        "ema200": latest(ema200),
        "rsi14": latest(rsi),
        "macd": latest(macd),
        "macd_signal": latest(signal),
        "macd_histogram": latest(histogram),
        "vwap": latest(vwap),
        "atr14": latest(atr),
    }
