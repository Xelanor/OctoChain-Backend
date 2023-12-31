import logging
from django.core.cache import cache
import traceback

import ccxt

from octochain.celery import app
from crypto.setup_functions import *
from crypto.spot_arbitrage import spot_arbitrage_opportunuties

logger = logging.getLogger()
c_handler = logging.StreamHandler()
logger.setLevel(logging.INFO)

c_format = logging.Formatter(
    "%(asctime)s :: %(levelname)s :: %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S",
)
c_handler.setFormatter(c_format)
logger.addHandler(c_handler)


exchanges = {
    "binance": {"types": {"spot": None, "swap": None, "future": None}},
    "okx": {"types": {"spot": None, "swap": None, "future": None}},
    "gate": {"types": {"spot": None, "swap": None, "future": None}},
    "mexc": {"types": {"spot": None, "swap": None, "future": None}},
    "bitmart": {"types": {"spot": None, "swap": None, "future": None}},
    "kucoin": {"types": {"spot": None}},
}


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(120, fetch_exchange_markets.s())
    sender.add_periodic_task(20, fetch_exchange_prices.s())
    sender.add_periodic_task(15, create_data.s())
    # sender.add_periodic_task(20, spot_arbitrage_opportunuties.s())


@app.task
def fetch_exchange_markets():
    try:
        for exchange in exchanges:
            fetch_exchange_market.delay(exchange)

    except:
        logger.error(traceback.format_exc())


@app.task
def fetch_exchange_market(exchange_id):
    params = {}
    try:
        if exchange_id == "mexc":
            params = {
                "apiKey": "mx0vgl90enlAWT1EYK",
                "secret": "ee94684c03c041038d6a87bf0c9e4669",
            }

        elif exchange_id == "binance":
            params = {
                "apiKey": "OHpPR9P1pGPcn2fcO0tD1YXsR5ZamEwxAfZi7sKhtCnRREhhwNEvRcaxXNaqXGE7",
                "secret": "qfFWipJZeugIlB21VSuvjLGFGxQT0zQtxePG6HaMLhLavzBV4mDW9l7N1VkmhLlZ",
            }

        elif exchange_id == "bitmart":
            params = {
                "apiKey": "208bb2453bd813ac52807733333d8acf59f32084",
                "secret": "73c5474076a429919810c029be8d7052f5f84884c23e76a32650b97b35540742",
                "password": "bot",
            }

        elif exchange_id == "kucoin":
            params = {
                "apiKey": "659109a03bc2270001a9a8eb",
                "secret": "f680fa71-57ce-4fcf-a03e-f45ea2681640",
                "password": "hedgebot",
            }

        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class(params)
        markets = exchange.load_markets()
        currencies = exchange.currencies
        markets_by_id = exchange.markets_by_id

        cache.set(f"{exchange_id}_markets", markets, 60 * 60)
        cache.set(f"{exchange_id}_currencies", currencies, 60 * 60)
        cache.set(f"{exchange_id}_markets_by_id", markets_by_id, 60 * 60)
        logger.info(f"{exchange_id} markets set!")
    except:
        logger.error(traceback.format_exc())


@app.task
def fetch_exchange_prices():
    try:
        for exchange_id, values in exchanges.items():
            fetch_exchange_price.delay(exchange_id, values)

    except:
        logger.error(traceback.format_exc())


@app.task
def fetch_exchange_price(exchange_id, values):
    try:
        exchange_class = getattr(ccxt, exchange_id)
        markets = cache.get(f"{exchange_id}_markets")

        if not markets:
            raise "No market details"

        for _type in values["types"]:
            exchange = exchange_class(
                {
                    "options": {
                        "defaultType": _type,
                    },
                }
            )
            exchange.markets = markets

            if exchange.has[_type] == True:  # ! TODO: Check this if necessary
                if _type == "future" and exchange_id == "gate":
                    extra_params = {"settle": "usdt"}
                    prices = exchange.fetch_tickers(params=extra_params)
                else:
                    prices = exchange.fetch_tickers()

            else:
                prices = {}

            cache.set(f"{exchange_id}_{_type}_prices", prices, 300)
            logger.debug(f"{exchange_id} {_type} prices set!")
    except:
        logger.error(traceback.format_exc())


@app.task
def create_data():
    try:
        spot = {}
        swap = {}
        future = {}

        market_names = cache.keys("*prices")
        for market in market_names:
            exchange_id = market.split("_")[0]
            _type = market.split("_")[1]

            markets = cache.get(f"{exchange_id}_markets")
            currencies = cache.get(f"{exchange_id}_currencies")
            prices = cache.get(f"{exchange_id}_{_type}_prices")

            if _type == "spot":
                create_empty_exchange_dict(prices, spot, exchange_id)
                insert_exchange_market_details(markets, spot, exchange_id)
                insert_exchange_currency_details(currencies, spot, exchange_id)
                insert_exchange_price_details(prices, spot, exchange_id)
                define_best_exchanges_for_tickers(spot)
                insert_common_details(spot)

            if _type == "swap":
                create_empty_exchange_dict(prices, swap, exchange_id)
                insert_exchange_market_details(markets, swap, exchange_id)
                insert_exchange_price_details(prices, swap, exchange_id)
                define_best_exchanges_for_tickers(swap)
                insert_common_details(swap)

            if _type == "future":
                create_empty_exchange_dict(prices, future, exchange_id)
                insert_exchange_market_details(markets, future, exchange_id)
                insert_exchange_price_details(prices, future, exchange_id)
                define_best_exchanges_for_tickers(future)
                insert_common_details(future)

        spot = {
            key: value
            for key, value in spot.items()
            if value.get("type") == "spot" and len(value.get("exchanges")) > 0
        }
        swap = {
            key: value
            for key, value in swap.items()
            if value.get("type") == "swap" and len(value.get("exchanges")) > 0
        }
        future = {
            key: value
            for key, value in future.items()
            if value.get("type") == "future" and len(value.get("exchanges")) > 0
        }

        cache.set("spot", spot, 300)
        cache.set("swap", swap, 300)
        cache.set("future", future, 300)

    except:
        logger.error(traceback.format_exc())

    # cache.set("binance", binance.fetch_tickers(), 6000)
