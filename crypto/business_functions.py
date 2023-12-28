import requests
from decimal import Decimal


def telegram_bot_sendtext(bot_message):
    bot_token = "5687151976:AAF94-ghuVdi3yBxDYwYzPC_MOHrM7D40pg"
    bot_chatID = "-1002000333988"
    send_text = (
        "https://api.telegram.org/bot"
        + bot_token
        + "/sendMessage?chat_id="
        + bot_chatID
        + "&parse_mode=Markdown&text="
        + bot_message
    )

    response = requests.get(send_text)

    return response.json()


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
    try:
        return abs(second_price / first_price) - 1
    except:
        return 0


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


def calculate_spot_fifo_average_cost(transactions):
    buy_transactions = [t for t in transactions if t["side"] == "open"]
    sell_transactions = [t for t in transactions if t["side"] == "close"]

    for sell_transaction in sell_transactions:
        sell_quantity = sell_transaction["spot_quantity"]

        for buy_transaction in buy_transactions[:]:
            buy_quantity = buy_transaction["spot_quantity"]

            if buy_quantity > sell_quantity:
                buy_transaction["spot_quantity"] -= sell_quantity
                sell_quantity = 0
                break

            elif buy_quantity == sell_quantity:
                buy_transactions.remove(buy_transaction)
                sell_quantity = 0
                break

            else:
                buy_transactions.remove(buy_transaction)
                sell_quantity -= buy_quantity

        if sell_quantity > 0:
            sell_transaction["spot_quantity"] = sell_quantity

    total_quantity = sum([t["spot_quantity"] for t in buy_transactions])
    total_price = sum(
        [t["spot_cost_price"] * t["spot_quantity"] for t in buy_transactions]
    )
    average_cost = total_price / total_quantity
    return average_cost


def calculate_hedge_fifo_average_cost(transactions):
    buy_transactions = [t for t in transactions if t["side"] == "open"]
    sell_transactions = [t for t in transactions if t["side"] == "close"]

    for sell_transaction in sell_transactions:
        sell_quantity = sell_transaction["hedge_quantity"]

        for buy_transaction in buy_transactions[:]:
            buy_quantity = buy_transaction["hedge_quantity"]

            if buy_quantity > sell_quantity:
                buy_transaction["hedge_quantity"] -= sell_quantity
                sell_quantity = 0
                break

            elif buy_quantity == sell_quantity:
                buy_transactions.remove(buy_transaction)
                sell_quantity = 0
                break

            else:
                buy_transactions.remove(buy_transaction)
                sell_quantity -= buy_quantity

        if sell_quantity > 0:
            sell_transaction["hedge_quantity"] = sell_quantity

    total_quantity = sum([t["hedge_quantity"] for t in buy_transactions])
    total_price = sum(
        [t["hedge_cost_price"] * t["hedge_quantity"] for t in buy_transactions]
    )
    average_cost = total_price / total_quantity
    return average_cost
