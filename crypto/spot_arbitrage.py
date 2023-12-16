import datetime
from django.core.cache import cache

from crypto.business_functions import (
    calculate_spread_rate,
)


def calculate_spot_arbitrage():
    spot = cache.get("spot")
    swap = cache.get("swap")

    from_exchanges = ["Bitmart", "Mxc", "Kucoin"]
    to_exchanges = ["Bitmart", "Mxc", "Kucoin"]

    arbitrages = []

    for coin in spot.values():
        coin_symbol = coin["symbol"]
        coin_exchanges = coin["exchanges"]

        if coin["quote"] != "USDT":
            continue

        for from_exchange, from_exchange_values in coin_exchanges.items():
            # if from_exchange not in from_exchanges:
            #     continue

            for to_exchange, to_exchange_values in coin_exchanges.items():
                if to_exchange == from_exchange:
                    continue

                try:
                    buy_price = from_exchange_values["ask"]
                    sell_price = to_exchange_values["bid"]
                    profit_rate = ((sell_price / buy_price) - 1) * 100
                except:
                    continue

                if 1.2 < profit_rate < 30:
                    try:
                        hedge = swap[f"{coin_symbol}:USDT"]["exchanges"][to_exchange]
                    except:
                        hedge = None

                    arbitrage = {
                        "from": from_exchange_values,
                        "to": to_exchange_values,
                        "profit_rate": profit_rate,
                        "hedge": hedge,
                    }
                    arbitrages.append(arbitrage)

    return arbitrages


def spot_arbitrage_opportunuties():
    arbitrages = calculate_spot_arbitrage()

    desired_budget_levels = [
        {"budget": 500, "profit_rate": 0.02},
        {"budget": 1000, "profit_rate": 0.02},
        {"budget": 2000, "profit_rate": 0.015},
    ]
