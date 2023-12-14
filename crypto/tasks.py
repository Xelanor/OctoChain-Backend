import logging
from django.core.cache import cache
import traceback

import ccxt

from octochain.celery import app
from crypto.setup_functions import *

logger = logging.getLogger()
c_handler = logging.StreamHandler()
logger.setLevel(logging.INFO)

c_format = logging.Formatter(
    "%(asctime)s :: %(levelname)s :: %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S",
)
c_handler.setFormatter(c_format)
logger.addHandler(c_handler)


def initialize_exchange(exchange_id, values):
    exchange_class = getattr(ccxt, exchange_id)

    for _type in values["types"]:
        exchange = exchange_class(
            {
                "options": {
                    "defaultType": _type,
                },
            }
        )
        markets = exchange.load_markets()
        prices = exchange.fetch_tickers()

        cache.set(f"{exchange_id}_{_type}_markets", markets, 300)
        cache.set(f"{exchange_id}_{_type}_prices", prices, 300)
        logger.info(f"{exchange_id} {_type} market and prices set!")


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(20, fetch_exchanges.s())
    sender.add_periodic_task(15, create_data.s())


@app.task
def fetch_exchanges():
    try:
        exchanges = {
            "binance": {"types": {"spot": None, "swap": None, "future": None}},
            "okx": {"types": {"spot": None, "swap": None, "future": None}},
            "gateio": {"types": {"spot": None, "swap": None, "future": None}},
        }

        for exchange, values in exchanges.items():
            fetch_exchange.delay(exchange, values)

    except:
        logger.error(traceback.format_exc())


@app.task
def fetch_exchange(exchange, values):
    try:
        initialize_exchange(exchange, values)
    except:
        logger.error(traceback.format_exc())


@app.task
def create_data():
    try:
        spot = {}
        swap = {}
        future = {}

        market_names = cache.keys("*markets")
        for market in market_names:
            exchange_id = market.split("_")[0]
            _type = market.split("_")[1]

            markets = cache.get(f"{exchange_id}_{_type}_markets")
            prices = cache.get(f"{exchange_id}_{_type}_prices")

            if _type == "spot":
                create_empty_exchange_dict(prices, spot, exchange_id)
                insert_exchange_market_details(markets, spot, exchange_id)
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

        cache.set("spot", spot, 300)
        cache.set("swap", swap, 300)
        cache.set("future", future, 300)

    except:
        logger.error(traceback.format_exc())

    # cache.set("binance", binance.fetch_tickers(), 6000)
