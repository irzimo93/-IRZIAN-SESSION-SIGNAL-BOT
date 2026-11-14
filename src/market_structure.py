from decimal import Decimal


def find_swings(candles, left=3, right=3):
    if not isinstance(left, int) or isinstance(left, bool) or left < 1:
        raise ValueError("left must be a positive integer")

    if not isinstance(right, int) or isinstance(right, bool) or right < 1:
        raise ValueError("right must be a positive integer")

    if len(candles) < left + right + 1:
        return {"swing_highs": [], "swing_lows": []}

    swing_highs = []
    swing_lows = []

    for index in range(left, len(candles) - right):
        current = candles[index]

        previous = candles[index-left:index]
        following = candles[index+1:index+right+1]

        if all(current.high > item.high for item in previous + following):
            swing_highs.append({
                "index": index,
                "time": current.open_time,
                "price": current.high,
            })

        if all(current.low < item.low for item in previous + following):
            swing_lows.append({
                "index": index,
                "time": current.open_time,
                "price": current.low,
            })

    return {
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
    }


def cluster_levels(levels, tolerance):
    tolerance = Decimal(str(tolerance))

    if not tolerance.is_finite() or tolerance < 0:
        raise ValueError("tolerance must be finite and non-negative")

    ordered = sorted(
        (Decimal(str(level)) for level in levels),
    )

    if not ordered:
        return []

    clusters = [[ordered[0]]]

    for price in ordered[1:]:
        current = clusters[-1]
        center = sum(current) / Decimal(len(current))

        if abs(price - center) <= tolerance:
            current.append(price)
        else:
            clusters.append([price])

    return [
        {
            "price": sum(group) / Decimal(len(group)),
            "touches": len(group),
            "low": min(group),
            "high": max(group),
        }
        for group in clusters
    ]


def build_market_structure(candles, atr, left=3, right=3):
    if not candles:
        raise ValueError("Candles cannot be empty")

    atr = Decimal(str(atr))

    if not atr.is_finite() or atr <= 0:
        raise ValueError("ATR must be finite and positive")

    swings = find_swings(candles, left, right)

    tolerance = atr * Decimal("0.5")

    supports = cluster_levels(
        [item["price"] for item in swings["swing_lows"]],
        tolerance,
    )

    resistances = cluster_levels(
        [item["price"] for item in swings["swing_highs"]],
        tolerance,
    )

    current_price = candles[-1].close

    for level in supports + resistances:
        level["distance"] = abs(current_price - level["price"])
        level["distance_atr"] = level["distance"] / atr

    supports.sort(key=lambda item: item["price"], reverse=True)
    resistances.sort(key=lambda item: item["price"])

    return {
        "current_price": current_price,
        "atr": atr,
        "swing_highs": swings["swing_highs"],
        "swing_lows": swings["swing_lows"],
        "supports": supports,
        "resistances": resistances,
    }
