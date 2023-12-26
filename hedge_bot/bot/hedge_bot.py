import logging
from time import sleep
from datetime import datetime, timedelta
import os
import traceback

import ccxt

from hedge_bot.models import HedgeBot, HedgeBotTx, ExchangeApi, Exchange


logger = logging.getLogger(__name__)


class HedgeBotClass:
    """Base HedgeBot class"""

    def __init__(self, bot_id):
        self.bot_id = bot_id

        self.bot = HedgeBot.objects.get(id=bot_id)
        self.tick = self.bot.tick

        self.setup_logger()
        self.spot_apis, self.hedge_apis, self.fees = self.setup_exchange_api()

        print(self.bot_id, self.tick, self.spot_apis, self.hedge_apis, self.fees)

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
        pass

    def bot_session(self):
        self.balances = self.fetch_account_balances()

    def run(self):
        try:
            while True:
                session_status = self.bot_session()
                sleep(1)

        except:
            logger.error(traceback.format_exc())
