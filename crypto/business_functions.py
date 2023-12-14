def calculate_future_apr(long_price, short_price, days):
    profit = short_price - long_price
    profit_rate = profit / long_price
    return profit_rate / days * 365


def calculate_spread_rate(first_price, second_price):
    return abs(second_price / first_price) - 1


def find_transaction_prices(spot_values, contract_values):
    if spot_values["ask"] == None:
        spot_price = spot_values["last"]
    else:
        spot_price = spot_values["ask"]

    if contract_values["bid"] == None:
        contract_price = contract_values["last"]
    else:
        contract_price = contract_values["bid"]

    return spot_price, contract_price
