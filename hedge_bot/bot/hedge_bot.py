import logging
from time import sleep
from datetime import datetime, timedelta
import os
import traceback

import ccxt

from hedge_bot.models import HedgeBot, HedgeBotTx, ExchangeApi, Exchange
from crypto.business_functions import calculate_avg_price, calculate_spread_rate


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class HedgeBotClass:
    """Base HedgeBot class"""

    def __init__(self, bot_id):
        self.bot_id = bot_id

        self.bot = HedgeBot.objects.get(id=bot_id)
        self.tick = self.bot.tick
        self.spot_ticker = f"{self.tick}/USDT"
        self.hedge_ticker = f"{self.tick}/USDT:USDT"

        self.setup_logger()
        self.spot_apis, self.hedge_apis, self.fees = self.setup_exchange_api()

        logger.debug(
            f"Tick: {self.tick} \n Spot APIs: {self.spot_apis} \n Hedge APIs: {self.hedge_apis}"
        )

    def check_bot_status(self):
        status = None
        self.bot = HedgeBot.objects.get(id=self.bot_id)

        if self.bot.status == False:
            status = "STOP"

        return status

    def set_bot_settings(self):
        self.settings = self.bot.settings
        self.max_size = self.bot.max_size
        self.control_size = self.bot.control_size
        self.tx_size = self.bot.tx_size
        self.min_profit = self.bot.min_profit

    def setup_exchange_api(self):
        spot_apis = {}
        hedge_apis = {}
        fees = {"spot": {}, "hedge": {}}
        bot_exchanges = self.bot.exchanges

        for bot_exchange in bot_exchanges:
            exchange_object = Exchange.objects.get(name=bot_exchange)
            exchange_api = ExchangeApi.objects.get(
                user=self.bot.user, exchange=exchange_object
            )

            public_key = exchange_api.public_key
            private_key = exchange_api.private_key
            group = exchange_api.group

            params = {
                "apiKey": public_key,
                "secret": private_key,
                "password": group,
                "options": {
                    "defaultType": None,
                },
            }

            if self.bot.exchanges[bot_exchange]["spot"]:
                params["options"]["defaultType"] = "spot"
                exchange_class = getattr(ccxt, exchange_object.exchange_id)
                exchange_class = exchange_class(params)
                markets = exchange_class.load_markets()

                spot_apis[bot_exchange] = exchange_class
                fees["spot"][bot_exchange] = exchange_object.spot_fee

            if self.bot.exchanges[bot_exchange]["hedge"]:
                params["options"]["defaultType"] = "swap"
                exchange_class = getattr(ccxt, exchange_object.exchange_id)
                exchange_class = exchange_class(params)
                markets = exchange_class.load_markets()

                hedge_apis[bot_exchange] = exchange_class
                fees["hedge"][bot_exchange] = exchange_object.future_fee

        return spot_apis, hedge_apis, fees

    def setup_logger(self):
        log_ticker_name = self.tick
        filepath = f"logs/{self.bot.user}/HedgeBot"
        if not os.path.exists(filepath):
            os.makedirs(filepath)

        logFile = f"{filepath}/{log_ticker_name}.log"
        f_handler = logging.handlers.RotatingFileHandler(
            logFile, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        f_format = logging.Formatter(
            "%(asctime)s :: %(levelname)s :: %(lineno)d :: %(message)s",
            datefmt="%d-%m-%Y %H:%M:%S",
        )
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)

    def fetch_account_balances(self):
        self.spot_balances = {}
        self.hedge_balances = {}

        for spot_exchange, spot_api in self.spot_apis.items():
            ticks = ["USDT", self.tick]
            balances = {}
            spot_balance = spot_api.fetch_balance()

            for tick in ticks:
                try:
                    balances[tick] = {
                        "available": spot_balance[tick]["free"],
                        "total": spot_balance[tick]["total"],
                    }
                except KeyError:
                    balances[tick] = {"available": 0, "total": 0}

            self.spot_balances[spot_exchange] = balances

        for hedge_exchange, hedge_api in self.hedge_apis.items():
            ticks = ["USDT"]
            balances = {}
            hedge_balance = hedge_api.fetch_balance()

            for tick in ticks:
                try:
                    balances[tick] = {
                        "available": hedge_balance[tick]["free"],
                        "total": hedge_balance[tick]["total"],
                    }
                except KeyError:
                    balances[tick] = {"available": 0, "total": 0}

            self.hedge_balances[hedge_exchange] = balances

    def fetch_order_books(self):
        self.spot_order_books = {}
        self.hedge_order_books = {}

        for spot_exchange, spot_api in self.spot_apis.items():
            spot_order_book = spot_api.fetch_order_book(self.spot_ticker, 20)
            depth = {
                "asks": spot_order_book["asks"],
                "bids": spot_order_book["bids"],
            }

            self.spot_order_books[spot_exchange] = depth

        for hedge_exchange, hedge_api in self.hedge_apis.items():
            hedge_order_book = hedge_api.fetch_order_book(self.hedge_ticker, 20)
            depth = {
                "asks": hedge_order_book["asks"],
                "bids": hedge_order_book["bids"],
            }

            self.hedge_order_books[hedge_exchange] = depth

    def find_profitable_open_deal(self):
        spot_exchanges = self.spot_order_books.keys()
        hedge_exchanges = self.hedge_order_books.keys()

        for spot_exchange in spot_exchanges:
            spot_depth = self.spot_order_books[spot_exchange]
            avg_spot_price, spot_reached = calculate_avg_price(
                spot_depth["asks"], self.control_size
            )
            if not spot_reached:
                continue

            logger.info(f"Spot-{spot_exchange} average price: {avg_spot_price}")

            for hedge_exchange in hedge_exchanges:
                hedge_depth = self.hedge_order_books[hedge_exchange]

                avg_hedge_price, hedge_reached = calculate_avg_price(
                    hedge_depth["bids"], self.control_size
                )
                if not hedge_reached:
                    continue

                logger.info(f"Hedge-{hedge_exchange} average price: {avg_hedge_price}")

                profit_rate = calculate_spread_rate(avg_spot_price, avg_hedge_price)
                logger.info(f"Profit rate: {profit_rate}")

                if profit_rate > self.min_profit:
                    logger.info("Profitable deal found!")
                    logger.info(
                        f"Spot-{spot_exchange} average price: {avg_spot_price} \n Hedge-{hedge_exchange} average price: {avg_hedge_price} \n Profit rate: {round(profit_rate, 2)}"
                    )

                    deal = {
                        "spot": spot_exchange,
                        "hedge": hedge_exchange,
                        "profit_rate": profit_rate,
                        "side": "open",
                    }

    def bot_session(self):
        self.fetch_account_balances()
        logger.debug(f"Spot balances: {self.spot_balances}")
        logger.debug(f"Hedge balances: {self.hedge_balances}")
        self.fetch_order_books()
        logger.debug(f"Spot order books: {self.spot_order_books}")
        logger.debug(f"Hedge order books: {self.hedge_order_books}")

        self.find_profitable_open_deal()

    def run(self):
        try:
            while True:
                bot_status = self.check_bot_status()
                if bot_status == "STOP":
                    return False

                self.set_bot_settings()

                session_status = self.bot_session()
                sleep(1)

        except:
            logger.error(traceback.format_exc())
