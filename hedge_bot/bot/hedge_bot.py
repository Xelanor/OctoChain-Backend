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
            if self.spot_balances[spot_exchange]["USDT"]["available"] < self.tx_size:
                continue

            spot_depth = self.spot_order_books[spot_exchange]
            avg_spot_price, spot_reached = calculate_avg_price(
                spot_depth["asks"], self.control_size
            )
            if not spot_reached:
                continue

            logger.info(f"Spot-{spot_exchange} average price: {avg_spot_price}")

            for hedge_exchange in hedge_exchanges:
                if (
                    self.hedge_balances[hedge_exchange]["USDT"]["available"]
                    < self.tx_size
                ):
                    continue

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
                        "avg_spot_price": avg_spot_price,
                        "hedge": hedge_exchange,
                        "avg_hedge_price": avg_hedge_price,
                        "profit_rate": profit_rate,
                        "side": "open",
                    }

                    return deal
        return None

    def create_open_transaction(self, deal, spot_order, hedge_order):
        if deal["spot"] == "Mexc":
            spot_order = self.spot_apis["Mexc"].fetch_order(
                spot_order["id"], self.spot_ticker
            )

        spot_price = spot_order["average"]
        hedge_price = hedge_order["average"]

        spot_quantity = spot_order["filled"]
        hedge_quantity = hedge_order["filled"]

        spot_exchange_object = Exchange.objects.get(name=deal["spot"])
        hedge_exchange_object = Exchange.objects.get(name=deal["hedge"])
        spot_fee = spot_exchange_object.spot_fee
        hedge_fee = hedge_exchange_object.future_fee

        spot_fee = spot_quantity * spot_price * spot_fee
        hedge_fee = hedge_quantity * hedge_price * hedge_fee

        fee = (spot_fee + hedge_fee) * -1

        tx = HedgeBotTx.objects.create(
            bot=self.bot,
            side="open",
            spot_price=spot_price,
            hedge_price=hedge_price,
            spot_exchange=spot_exchange_object,
            hedge_exchange=hedge_exchange_object,
            spot_quantity=spot_quantity,
            hedge_quantity=hedge_quantity,
            fee=fee,
        )

        return tx

    def execute_open_deal(self, deal):
        spot_exchange = deal["spot"]
        average_spot_price = deal["avg_spot_price"]
        hedge_exchange = deal["hedge"]
        average_hedge_price = deal["avg_hedge_price"]
        profit_rate = deal["profit_rate"]

        tx_amount = self.tx_size / average_spot_price

        spot_api = self.spot_apis[spot_exchange]
        hedge_api = self.hedge_apis[hedge_exchange]

        formatted_amount = hedge_api.amount_to_precision(self.hedge_ticker, tx_amount)

        logger.info(f"Tx amount: {tx_amount} \n Formatted amount: {formatted_amount}")

        ### Some exchanges market buy order requires price argument
        spot_order_type = "market"
        price = None
        if spot_exchange == "Mexc":
            spot_order_type = "limit"
            price = average_spot_price * 1.02

        # Execute Spot Order
        spot_order = spot_api.create_order(
            self.spot_ticker, spot_order_type, "buy", formatted_amount, price
        )

        # Execute Hedge Order
        leverage = 1
        response = hedge_api.set_leverage(leverage, self.hedge_ticker)
        response = hedge_api.set_margin_mode("ISOLATED", self.hedge_ticker)

        hedge_order = hedge_api.create_market_sell_order(
            self.hedge_ticker, formatted_amount
        )

        logger.info(f"Spot order: {spot_order}")
        logger.info(f"Hedge order: {hedge_order}")
        tx = self.create_open_transaction(deal, spot_order, hedge_order)
        logger.info(f"Tx: {tx}")

    def bot_session(self):
        self.fetch_account_balances()
        logger.debug(f"Spot balances: {self.spot_balances}")
        logger.debug(f"Hedge balances: {self.hedge_balances}")
        self.fetch_order_books()
        logger.debug(f"Spot order books: {self.spot_order_books}")
        logger.debug(f"Hedge order books: {self.hedge_order_books}")

        # TODO: Is total size over max size?

        deal = self.find_profitable_open_deal()
        if deal:
            self.execute_open_deal(deal)

    def run(self):
        try:
            while True:
                bot_status = self.check_bot_status()
                if bot_status == "STOP":
                    return False

                self.set_bot_settings()

                session_status = self.bot_session()
                sleep(10)

        except:
            logger.error(traceback.format_exc())
