from decimal import Decimal


def calculate_future_apr(long_price, short_price, days):
    profit = short_price - long_price
    profit_rate = profit / long_price
    return profit_rate / days * 365


def calculate_future_real_apr(long_price, short_price, days, spot_fee, future_fee):
    profit = short_price - long_price
    profit_rate = profit / long_price
    total_fee = spot_fee * 2 + future_fee * 2
    net_profit_rate = profit_rate - total_fee
    return net_profit_rate / days * 365


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


def calculate_weighted_avg(prices, quantities):
    numerator = sum([prices[i] * quantities[i] for i in range(len(prices))])
    denominator = sum([qty for qty in quantities])
    try:
        w_average_price = numerator / denominator
    except ZeroDivisionError:
        w_average_price = 0
    return w_average_price


def calculate_avg_price(depth, capital):
    prices = []
    quantities = []
    cumulative = 0
    reached = False
    for order in depth:
        price = float(order[0])
        qty = float(order[1])
        total = price * qty

        if cumulative + total > capital:
            remaining = capital - cumulative
            calculated_qty = remaining / price

            prices.append(price)
            quantities.append(calculated_qty)
            cumulative = capital
            reached = True
            break
        cumulative += total
        prices.append(price)
        quantities.append(qty)

    average_price = calculate_weighted_avg(prices, quantities)
    return average_price, reached


def determine_price_str(price):
    price = float(f"{Decimal(f'{price:.4g}'):f}")
    decimal_count = Decimal(str(price)).as_tuple().exponent * -1
    order_price = format(price, f".{decimal_count}f")

    return order_price
