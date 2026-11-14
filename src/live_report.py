from datetime import datetime, timezone
from decimal import Decimal

from src.analysis_snapshot import build_snapshot


def fmt(value):
    if value is None:
        return "WARMUP"

    if isinstance(value, Decimal):
        return f"{value:.8f}"

    return str(value)


def generate_report():
    print("=" * 75)
    print("IRZIAN SESSION INTELLIGENCE")
    print("LIVE MARKET ANALYSIS REPORT")
    print("Generated UTC:", datetime.now(timezone.utc).isoformat())
    print("=" * 75)

    snapshot = build_snapshot()

    for symbol, intervals in snapshot.items():
        print(f"\n### {symbol}")

        for interval, item in intervals.items():
            indicators = item["indicators"]

            print(f"\n[{interval}] STATUS: {item['status']}")
            print("Candle UTC:", datetime.fromtimestamp(
                item["candle_time"] / 1000,
                timezone.utc
            ).isoformat())

            print("Close:", fmt(item["close"]))
            print("Volume:", fmt(item["volume"]))
            print("EMA20:", fmt(indicators["ema20"]))
            print("EMA50:", fmt(indicators["ema50"]))
            print("EMA200:", fmt(indicators["ema200"]))
            print("RSI14:", fmt(indicators["rsi14"]))
            print("MACD:", fmt(indicators["macd"]))
            print("MACD Signal:", fmt(indicators["macd_signal"]))
            print("MACD Histogram:", fmt(indicators["macd_histogram"]))
            print("VWAP:", fmt(indicators["vwap"]))
            print("ATR14:", fmt(indicators["atr14"]))
            print("History:", item["history_count"])
            structure = item["market_structure"]

            print("Market Structure:")
            print("  Current Price:", fmt(structure["current_price"]))
            print("  ATR:", fmt(structure["atr"]))

            print("  Supports:")
            for level in structure["supports"]:
                print(
                    "   - Price:", fmt(level["price"]),
                    "| Distance:", fmt(level["distance"]),
                    "| ATR Distance:", fmt(level["distance_atr"])
                )

            print("  Resistances:")
            for level in structure["resistances"]:
                print(
                    "   - Price:", fmt(level["price"]),
                    "| Distance:", fmt(level["distance"]),
                    "| ATR Distance:", fmt(level["distance_atr"])
                )


    print("\n" + "=" * 75)
    print("REPORT COMPLETED")
    print("MODE: READ ONLY — NO TRADE EXECUTION")
    print("=" * 75)


if __name__ == "__main__":
    try:
        generate_report()
    except Exception as error:
        print("\nREPORT FAILED")
        print(type(error).__name__ + ":", error)
        raise SystemExit(1)
