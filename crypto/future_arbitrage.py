import datetime
from django.core.cache import cache

from crypto.business_functions import (
    calculate_future_apr,
    calculate_spread_rate,
    find_transaction_prices,
    calculate_future_real_apr,
)


def calculate_future_arbitrage():
    spot = cache.get("spot")
    future = cache.get("future")

    now = datetime.datetime.now()

    arbitrages = []

    for contract in future.values():
        contract_symbol = contract["symbol"]

        if contract["type"] != "future":
            continue

        for contract_exchange, contract_values in contract["exchanges"].items():
            base = contract_values["base"]
            quote = contract_values["quote"]
            spot_symbol = f"{base}/{quote}"
            future_fee = 0.0005

            try:
                spot_values = spot[spot_symbol]["exchanges"][contract_exchange]
                spot_fee = spot_values["taker"]
            except:
                continue

            expiry = contract_values["expiry"]
            expiry_date = datetime.datetime.utcfromtimestamp(expiry / 1000)
            days_to_maturity = round(abs(expiry_date - now).total_seconds() / 86400, 2)

            spot_price, contract_price = find_transaction_prices(
                spot_values, contract_values
            )

            spread_rate = calculate_spread_rate(spot_price, contract_price)
            apr = calculate_future_apr(spot_price, contract_price, days_to_maturity)
            real_apr = calculate_future_real_apr(
                spot_price, contract_price, days_to_maturity, spot_fee, future_fee
            )

            arbitrage = {
                "long": spot_values,
                "short": contract_values,
                "spread": spread_rate,
                "days_to_maturity": days_to_maturity,
                "apr": apr,
                "real_apr": real_apr,
            }
            arbitrages.append(arbitrage)

    return arbitrages
