import logging
from time import sleep
from datetime import datetime, timedelta
from django.utils.timezone import now
import os
import traceback
from django.contrib.auth import get_user_model
from django.core.cache import cache
from octochain.celery import app

import ccxt

from hedge_bot.models import (
    HedgeBot,
    HedgeBotTx,
    ExchangeApi,
    Exchange,
    HedgeBotBlacklist,
)
from crypto.business_functions import (
    calculate_avg_price,
    calculate_spread_rate,
    determine_price_str,
    calculate_spot_fifo_average_cost,
    calculate_hedge_fifo_average_cost,
)
from hedge_bot.bot.hedge_bot import HedgeBotClass


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

User = get_user_model()


@app.task
def run_hedge_bot(bot_id):
    bot = HedgeBotClass(bot_id)
    bot.run()


class HedgeBotOpenClass:
    """Bot class for opening positions"""

    def __init__(self):
        self.user = User.objects.get(username="berke")

        self.setup_logger()
        self.spot_apis, self.hedge_apis, self.fees = self.setup_exchange_api()

        logger.info(f"Open bot initialized for {self.user}")
        logger.debug(
            f"\n Spot APIs: {self.spot_apis} \n Hedge APIs: {self.hedge_apis} \n Fees: {self.fees}"
        )

        self.min_profit_rate = 0.008
        self.max_profit_rate = 0.05
        self.desired_budget_levels = [
            {"budget": 100, "profit_rate": 0.0085},
        ]
        self.min_volume = 100000

    def setup_logger(self):
        filepath = f"logs/{self.user}/HedgeBot"
        if not os.path.exists(filepath):
            os.makedirs(filepath)

        logFile = f"{filepath}/open.log"
        f_handler = logging.handlers.RotatingFileHandler(
            logFile, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        f_format = logging.Formatter(
            "%(asctime)s :: %(levelname)s :: %(lineno)d :: %(message)s",
            datefmt="%d-%m-%Y %H:%M:%S",
        )
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)

    def setup_exchange_api(self):
        spot_apis = {}
        hedge_apis = {}
        fees = {"spot": {}, "hedge": {}}
        exchange_objects = Exchange.objects.filter()

        for exchange_object in exchange_objects:
            exchange = exchange_object.name
            exchange_id = exchange_object.exchange_id
            exchange_api = ExchangeApi.objects.get(
                user=self.user, exchange=exchange_object
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

            if exchange_id == "bitmart":
                params["uid"] = group

            if exchange_object.spot:
                params["options"]["defaultType"] = "spot"
                exchange_class = getattr(ccxt, exchange_id)
                exchange_class = exchange_class(params)
                markets = exchange_class.load_markets()

                spot_apis[exchange_id] = exchange_class
                fees["spot"][exchange_id] = exchange_object.spot_fee

            if exchange_object.future:
                params["options"]["defaultType"] = "swap"
                exchange_class = getattr(ccxt, exchange_id)
                exchange_class = exchange_class(params)
                markets = exchange_class.load_markets()

                hedge_apis[exchange_id] = exchange_class
                fees["hedge"][exchange_id] = exchange_object.future_fee

        return spot_apis, hedge_apis, fees

    def find_all_hedge_positions(self):
        spot = cache.get("spot")
        swap = cache.get("swap")

        arbitrages = []

        for coin in spot.values():
            coin_symbol = coin["symbol"]
            coin_exchanges = coin["exchanges"]

            if coin["quote"] != "USDT":
                continue

            for from_exchange, from_exchange_values in coin_exchanges.items():
                if from_exchange not in self.spot_apis.keys():
                    continue

                if from_exchange_values["quoteVolume"] < self.min_volume:
                    continue

                hedge_symbol = f"{coin_symbol}:USDT"
                if not hedge_symbol in swap.keys():
                    continue

                hedge_coin = swap[hedge_symbol]
                hedge_coin_exchanges = hedge_coin["exchanges"]

                for (
                    hedge_exchange,
                    hedge_exchange_values,
                ) in hedge_coin_exchanges.items():
                    if hedge_exchange not in self.hedge_apis.keys():
                        continue

                    if hedge_exchange_values["quoteVolume"] < self.min_volume:
                        continue

                    try:
                        buy_price = from_exchange_values["ask"]
                        sell_price = (
                            hedge_exchange_values["bid"]
                            or hedge_exchange_values["last"]
                        )
                        profit_rate = (sell_price / buy_price) - 1
                    except:
                        continue

                    if self.min_profit_rate < profit_rate < self.max_profit_rate:
                        arbitrage = {
                            "from": from_exchange_values,
                            "hedge": hedge_exchange_values,
                            "profit_rate": profit_rate,
                        }
                        arbitrages.append(arbitrage)

        logger.debug(f"Arbitrages: {arbitrages}")
        logger.info(f"Arbitrages: {len(arbitrages)}")

        return arbitrages

    def is_blacklisted(self, tick, spot_exchange, hedge_exchange):
        try:
            blacklist = HedgeBotBlacklist.objects.get(
                tick=tick,
                spot_exchange=Exchange.objects.get(exchange_id=spot_exchange),
                hedge_exchange=Exchange.objects.get(exchange_id=hedge_exchange),
            )

            if blacklist.until_date > now():
                return True
        except:
            return False

        return False

    def add_temporary_blacklist(self, tick, spot_exchange, hedge_exchange):
        blacklist, created = HedgeBotBlacklist.objects.get_or_create(
            user=self.user,
            tick=tick,
            spot_exchange=Exchange.objects.get(exchange_id=spot_exchange),
            hedge_exchange=Exchange.objects.get(exchange_id=hedge_exchange),
        )
        blacklist.until_date = now() + timedelta(minutes=180)
        blacklist.save()

        logger.info(f"{tick} added to blacklist for 3 hours")

        return True

    def calculate_historic_spread(
        self, spot_symbol, hedge_symbol, spot_exchange, hedge_exchange
    ):
        interval = "1m"
        limit = 360
        if spot_exchange == "bitmart":
            interval = "5m"
            limit = 100

        spot_candles = self.spot_apis[spot_exchange].fetch_ohlcv(
            spot_symbol, interval, limit=limit
        )
        swap_candles = self.hedge_apis[hedge_exchange].fetch_ohlcv(
            hedge_symbol, interval, limit=limit
        )

        differences = []
        for i in range(len(spot_candles)):
            spot_candle = spot_candles[i]
            swap_candle = swap_candles[i]

            if spot_candle[0] == swap_candle[0]:
                spread = (swap_candle[3] / spot_candle[3]) - 1
                differences.append(spread)

        return sum(differences) / len(differences)

    def calculate_hedge_positions(self, arbitrages):
        for arbitrage in arbitrages:
            tick = arbitrage["from"]["base"]
            spot_symbol = arbitrage["from"]["symbol"]
            hedge_symbol = arbitrage["hedge"]["symbol"]
            from_exchange_values = arbitrage["from"]
            hedge_exchange_values = arbitrage["hedge"]

            spot_exchange = from_exchange_values["exchange"]
            hedge_exchange = hedge_exchange_values["exchange"]

            if self.is_blacklisted(tick, spot_exchange, hedge_exchange):
                logger.info(
                    f"{tick} is blacklisted for {spot_exchange} - {hedge_exchange}"
                )
                continue

            try:
                spot_order_books = self.spot_apis[spot_exchange].fetch_order_book(
                    spot_symbol, limit=20
                )
                spot_asks = spot_order_books["asks"]
                spot_bids = spot_order_books["bids"]
                spot_spread = calculate_spread_rate(spot_bids[0][0], spot_asks[0][0])

                hedge_order_books = self.hedge_apis[hedge_exchange].fetch_order_book(
                    hedge_symbol, limit=20
                )
                hedge_bids = hedge_order_books["bids"]
                hedge_asks = hedge_order_books["asks"]
                hedge_spread = calculate_spread_rate(hedge_bids[0][0], hedge_asks[0][0])

            except Exception as ex:
                print(ex)
                print(arbitrage)
                continue

            found = 0
            budget_levels = []
            for budget_level in self.desired_budget_levels:
                avg_spot_ask, spot_reached = calculate_avg_price(
                    spot_asks, budget_level["budget"]
                )
                avg_hedge_bid, hedge_reached = calculate_avg_price(
                    hedge_bids, budget_level["budget"]
                )

                if spot_reached and hedge_reached:
                    profit_rate = (avg_hedge_bid / avg_spot_ask) - 1
                    total_spread = spot_spread / 3 + hedge_spread / 3
                    net_profit_rate = profit_rate - total_spread

                    logger.info(
                        f"{tick} {round(net_profit_rate * 100, 2)}%/{round(profit_rate * 100, 2)}% Spread: {round(total_spread * 100, 2)}%"
                    )

                    profitable = (
                        budget_level["profit_rate"]
                        < net_profit_rate
                        < self.max_profit_rate
                    )

                    if profitable:
                        found += 1
                else:
                    profit_rate = 0

                budget_levels.append(
                    {
                        "budget": budget_level,
                        "profit_rate": profit_rate,
                        "buy_price": determine_price_str(avg_spot_ask),
                        "sell_price": determine_price_str(avg_hedge_bid),
                    }
                )

            if found > 0:
                try:
                    historic_spread = self.calculate_historic_spread(
                        spot_symbol, hedge_symbol, spot_exchange, hedge_exchange
                    )
                except:
                    logger.error(
                        f"{tick} historic spread calculation error spot: {spot_exchange} hedge: {hedge_exchange}"
                    )
                    continue

                if historic_spread > 0.006:
                    logger.info(
                        f"{tick} {historic_spread} has historically high spread between {spot_exchange} - {hedge_exchange}"
                    )
                    self.add_temporary_blacklist(tick, spot_exchange, hedge_exchange)
                    continue

                self.run_hedge_bot(tick, spot_exchange, hedge_exchange)
                return True

    def run_hedge_bot(self, tick, spot_exchange, hedge_exchange):
        try:
            # TODO: Check if bot is already running maybe add exchanges
            hedge_bot = HedgeBot.objects.get(
                user=self.user,
                tick=tick,
                status=True,
            )

        except:
            hedge_bot = HedgeBot.objects.create(
                user=self.user,
                tick=tick,
                exchanges={
                    "spot": {spot_exchange: True},
                    "hedge": {hedge_exchange: True},
                },
                settings={"a": "a"},
                status=True,
                max_size=1000,
                control_size=100,
                tx_size=25,
                min_open_profit=0.008,
                min_close_profit=0.005,
            )

            logger.info(f"{tick} is opened")
            run_hedge_bot.delay(hedge_bot.id)

    def bot_session(self):
        if HedgeBot.objects.filter(user=self.user, status=True).count() > 19:
            logger.info(f"Too many actie bots for {self.user}")
            return False

        arbitrages = self.find_all_hedge_positions()
        self.calculate_hedge_positions(arbitrages)

    def run(self):
        while True:
            try:
                self.bot_session()
                sleep(3)
            except:
                logger.error(traceback.format_exc())
                sleep(15)
