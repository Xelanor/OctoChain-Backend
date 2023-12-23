import datetime
from django.core.cache import cache
import ccxt

from crypto.business_functions import (
    calculate_spread_rate,
    calculate_avg_price,
    determine_price_str,
    telegram_bot_sendtext,
)
from octochain.celery import app

exchanges = {
    "binance": {"types": {"spot": None, "swap": None, "future": None}},
    "okx": {"types": {"spot": None, "swap": None, "future": None}},
    "gate": {"types": {"spot": None, "swap": None, "future": None}},
    "mexc": {"types": {"spot": None, "swap": None, "future": None}},
    "bitmart": {"types": {"spot": None, "swap": None, "future": None}},
}


def initialize_exchange_functions():
    exchange_functions = {}

    for exchange_id, values in exchanges.items():
        exchange_class = getattr(ccxt, exchange_id)
        markets = cache.get(f"{exchange_id}_markets")
        currencies = cache.get(f"{exchange_id}_currencies")
        markets_by_id = cache.get(f"{exchange_id}_markets_by_id")

        exchange_functions[exchange_id] = {}

        if not markets:
            raise "No market details"

        for _type in ["spot", "swap"]:
            exchange = exchange_class(
                {
                    "options": {
                        "defaultType": _type,
                    },
                }
            )
            exchange.markets = markets
            exchange.currencies = currencies
            exchange.markets_by_id = markets_by_id
            exchange_functions[exchange_id][_type] = exchange

    return exchange_functions


def spot_arb_details(symbol, from_exc, to_exc, hedge_symbol, hedge_exc):
    exchange_functions = initialize_exchange_functions()

    from_board = exchange_functions[from_exc]["spot"].fetch_order_book(symbol, limit=20)
    to_board = exchange_functions[to_exc]["spot"].fetch_order_book(symbol, limit=20)
    hedge_board = exchange_functions[hedge_exc]["swap"].fetch_order_book(
        hedge_symbol, limit=20
    )

    details = {
        "from_board": from_board,
        "to_board": to_board,
        "hedge_board": hedge_board,
    }
    return details


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

                if 0.6 < profit_rate < 30:
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


@app.task
def spot_arbitrage_opportunuties():
    arbitrages = calculate_spot_arbitrage()
    exchange_functions = initialize_exchange_functions()

    cache.set("all_arbitrages", arbitrages, 120)

    opportunuties = []
    desired_budget_levels = [
        {"budget": 500, "profit_rate": 0.005},
        {"budget": 1000, "profit_rate": 0.005},
        {"budget": 2000, "profit_rate": 0.004},
    ]
    max_profit_rate = 0.3

    for arbitrage in arbitrages:
        symbol = arbitrage["from"]["symbol"]
        from_exchange_values = arbitrage["from"]
        to_exchange_values = arbitrage["to"]
        hedge_exchange_values = arbitrage["hedge"]

        from_exchange = from_exchange_values["exchange"]
        to_exchange = to_exchange_values["exchange"]

        if not hedge_exchange_values:
            continue

        try:
            from_exc_asks = exchange_functions[from_exchange]["spot"].fetch_order_book(
                symbol, limit=20
            )["asks"]
            to_exc_bids = exchange_functions[to_exchange]["spot"].fetch_order_book(
                symbol, limit=20
            )["bids"]
            hedge_bids = exchange_functions[to_exchange]["swap"].fetch_order_book(
                f"{symbol}:USDT", limit=20
            )["bids"]
        except Exception as ex:
            print(ex)
            continue

        found = 0
        budget_levels = []
        for budget_level in desired_budget_levels:
            avg_ask, ask_reached = calculate_avg_price(
                from_exc_asks, budget_level["budget"]
            )
            avg_bid, bid_reached = calculate_avg_price(
                to_exc_bids, budget_level["budget"]
            )
            avg_hedge_bid, hedge_bid_reached = calculate_avg_price(
                hedge_bids, budget_level["budget"]
            )
            if ask_reached and bid_reached and hedge_bid_reached:
                nominal_profit = (
                    budget_level["budget"] / avg_ask * avg_bid - budget_level["budget"]
                )
                # real_profit = nominal_profit - fee if fee else nominal_profit
                real_profit = nominal_profit

                hedge_real_profit = (
                    budget_level["budget"] / avg_ask * avg_hedge_bid
                ) - budget_level["budget"]

                spot_profitable = (
                    budget_level["profit_rate"]
                    < real_profit / budget_level["budget"]
                    < max_profit_rate
                )
                hedge_profitable = (
                    budget_level["profit_rate"]
                    < hedge_real_profit / budget_level["budget"]
                    < max_profit_rate
                )

                if spot_profitable and hedge_profitable:
                    found += 1
            else:
                real_profit = 0

            budget_levels.append(
                {
                    "budget": budget_level,
                    "profit_rate": real_profit / budget_level["budget"],
                    "profit": real_profit,
                    "buy_price": determine_price_str(avg_ask),
                    "sell_price": determine_price_str(avg_bid),
                    "hedge_price": determine_price_str(avg_hedge_bid),
                }
            )

        if found > 0:
            arb_opportunity = {
                "symbol": symbol,
                "from": from_exchange_values,
                "to": to_exchange_values,
                "hedge": hedge_exchange_values,
                "budget_levels": budget_levels,
            }
            cache.set(
                f"arb_{symbol}-{from_exchange}-{to_exchange}", arb_opportunity, 120
            )
            telegram_bot_sendtext(
                f"Spot Arbitrage found: {symbol}-{from_exchange}-{to_exchange}"
            )
