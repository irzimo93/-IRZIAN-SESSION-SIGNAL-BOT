import requests
from datetime import datetime, timezone

BASE = "https://fapi.binance.com"
SYMBOLS = ["ADAUSDT", "TRXUSDT", "PUMPUSDT", "DOGEUSDT", "GRAMUSDT"]

def main():
    print("IRZIAN SESSION INTELLIGENCE")
    print("Checking Binance Futures...\n")

    try:
        response = requests.get(
            f"{BASE}/fapi/v1/exchangeInfo",
            timeout=20
        )
        response.raise_for_status()
        markets = {
            item["symbol"]: item
            for item in response.json()["symbols"]
        }

        for symbol in SYMBOLS:
            market = markets.get(symbol)

            if (market and market["status"] == "TRADING"
                and market["contractType"] == "PERPETUAL"
                and market["quoteAsset"] == "USDT"):

                print(f"[OK] {symbol}")

                r = requests.get(
                    f"{BASE}/fapi/v1/klines",
                    params={"symbol": symbol, "interval": "15m", "limit": 1},
                    timeout=20
                )
                r.raise_for_status()
                print("     Last close:", r.json()[-1][4])
            else:
                print(f"[UNAVAILABLE] {symbol}")

        print("\nCheck completed.")
        print("UTC:", datetime.now(timezone.utc).isoformat())

    except requests.RequestException as error:
        print("[CONNECTION ERROR]", error)

if __name__ == "__main__":
    main()
