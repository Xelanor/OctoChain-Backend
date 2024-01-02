from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.utils.timezone import now
from django.core.cache import cache

from hedge_bot.models import HedgeBot, HedgeBotTx, Exchange, ExchangeApi
from octofolio.models import Asset
from hedge_bot.tasks import run_hedge_bot as run_hedge_bot_task

import ccxt


@api_view(["GET"])
def get_hedge_bots(request):
    spot = cache.get("spot")
    swap = cache.get("swap")

    hedge_bots = []

    hedge_bot_objects = HedgeBot.objects.filter().order_by("-created_at")
    for hedge_bot_object in hedge_bot_objects:
        hedge_bot_id = hedge_bot_object.id
        hedge_bot_tick = hedge_bot_object.tick

        asset = Asset.objects.get(symbol=hedge_bot_tick)
        asset_name = asset.name
        asset_logo = asset.logo

        hedge_bot_exchanges = hedge_bot_object.exchanges
        hedge_bot_settings = hedge_bot_object.settings
        hedge_bot_status = hedge_bot_object.status
        hedge_bot_max_size = hedge_bot_object.max_size
        hedge_bot_control_size = hedge_bot_object.control_size
        hedge_bot_tx_size = hedge_bot_object.tx_size
        hedge_bot_min_open_profit = hedge_bot_object.min_open_profit
        hedge_bot_min_close_profit = hedge_bot_object.min_close_profit
        hedge_bot_created_at = hedge_bot_object.created_at

        hedge_bot = {
            "id": hedge_bot_id,
            "tick": hedge_bot_tick,
            "name": asset_name,
            "logo": asset_logo,
            "exchanges": hedge_bot_exchanges,
            "settings": hedge_bot_settings,
            "status": hedge_bot_status,
            "max_size": hedge_bot_max_size,
            "control_size": hedge_bot_control_size,
            "tx_size": hedge_bot_tx_size,
            "min_open_profit": hedge_bot_min_open_profit,
            "min_close_profit": hedge_bot_min_close_profit,
            "created_at": hedge_bot_created_at,
            "open_spot": 0,
            "open_hedge": 0,
            "total_profit": 0,
            "transactions": [],
        }

        hedge_bot_tx_objects = HedgeBotTx.objects.filter(bot=hedge_bot_object).order_by(
            "-created_at"
        )

        for hedge_bot_tx_object in hedge_bot_tx_objects:
            hedge_bot_tx_id = hedge_bot_tx_object.id
            hedge_bot_tx_side = hedge_bot_tx_object.side
            hedge_bot_tx_spot_cost_price = hedge_bot_tx_object.spot_cost_price
            hedge_bot_tx_hedge_cost_price = hedge_bot_tx_object.hedge_cost_price
            hedge_bot_tx_spot_price = hedge_bot_tx_object.spot_price
            hedge_bot_tx_hedge_price = hedge_bot_tx_object.hedge_price
            hedge_bot_tx_spot_exchange = hedge_bot_tx_object.spot_exchange.name
            hedge_bot_tx_hedge_exchange = hedge_bot_tx_object.hedge_exchange.name
            hedge_bot_tx_spot_quantity = hedge_bot_tx_object.spot_quantity
            hedge_bot_tx_hedge_quantity = hedge_bot_tx_object.hedge_quantity
            hedge_bot_tx_fee = hedge_bot_tx_object.fee
            hedge_bot_tx_created_at = hedge_bot_tx_object.created_at

            hedge_bot_tx = {
                "id": hedge_bot_tx_id,
                "side": hedge_bot_tx_side,
                "spot_cost_price": hedge_bot_tx_spot_cost_price,
                "hedge_cost_price": hedge_bot_tx_hedge_cost_price,
                "spot_price": hedge_bot_tx_spot_price,
                "hedge_price": hedge_bot_tx_hedge_price,
                "spot_total": hedge_bot_tx_spot_quantity * hedge_bot_tx_spot_cost_price,
                "hedge_total": hedge_bot_tx_hedge_quantity
                * hedge_bot_tx_hedge_cost_price,
                "spot_exchange": hedge_bot_tx_spot_exchange,
                "hedge_exchange": hedge_bot_tx_hedge_exchange,
                "spot_quantity": hedge_bot_tx_spot_quantity,
                "hedge_quantity": hedge_bot_tx_hedge_quantity,
                "fee": hedge_bot_tx_fee,
                "created_at": hedge_bot_tx_created_at.strftime("%s"),
            }

            if hedge_bot_tx_side == "close":
                spot_profit = (
                    hedge_bot_tx_spot_price - hedge_bot_tx_spot_cost_price
                ) * hedge_bot_tx_spot_quantity
                hedge_profit = (
                    hedge_bot_tx_hedge_cost_price - hedge_bot_tx_hedge_price
                ) * hedge_bot_tx_hedge_quantity
                tx_profit = spot_profit + hedge_profit
                profit_rate = tx_profit / (
                    hedge_bot_tx_spot_quantity * hedge_bot_tx_spot_cost_price
                )

                hedge_bot_tx["profit"] = tx_profit
                hedge_bot_tx["profit_rate"] = profit_rate
                hedge_bot["total_profit"] += tx_profit

                hedge_bot["open_spot"] -= hedge_bot_tx_spot_quantity
                hedge_bot["open_hedge"] -= hedge_bot_tx_hedge_quantity

            elif hedge_bot_tx_side == "open":
                hedge_bot["open_spot"] += hedge_bot_tx_spot_quantity
                hedge_bot["open_hedge"] += hedge_bot_tx_hedge_quantity

            hedge_bot["total_profit"] -= hedge_bot_tx_fee

            hedge_bot["transactions"].append(hedge_bot_tx)

        hedge_bots.append(hedge_bot)

    return Response(hedge_bots)


@api_view(["GET"])
def get_exchange_funds(request):
    funds = []
    apis = ExchangeApi.objects.all()

    for exchange_api in apis:
        exchange = exchange_api.exchange
        exchange_id = exchange.exchange_id
        exchange_name = exchange.name

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

        fund = {
            "id": exchange_id,
            "name": exchange_name,
            "logo": exchange.logo,
            "spot_fund": None,
            "future_fund": None,
        }

        if exchange_api.exchange.spot:
            params["options"]["defaultType"] = "spot"
            exchange_class = getattr(ccxt, exchange_id)
            exchange_class = exchange_class(params)
            exchange_class.markets = cache.get(f"{exchange_id}_markets")

            spot_balance = exchange_class.fetch_balance()

            try:
                usdt = {
                    "available": spot_balance["USDT"]["free"],
                    "total": spot_balance["USDT"]["total"],
                }
            except KeyError:
                usdt = {"available": 0, "total": 0}

            fund["spot_fund"] = usdt

        if exchange_api.exchange.future:
            params["options"]["defaultType"] = "swap"
            exchange_class = getattr(ccxt, exchange_id)
            exchange_class = exchange_class(params)
            exchange_class.markets = cache.get(f"{exchange_id}_markets")

            future_balance = exchange_class.fetch_balance()
            try:
                usdt = {
                    "available": future_balance["USDT"]["free"],
                    "total": future_balance["USDT"]["total"],
                }
            except KeyError:
                usdt = {"available": 0, "total": 0}

            fund["future_fund"] = usdt

        funds.append(fund)

    return Response(funds)


@api_view(["GET"])
def run_hedge_bot(request):
    run_hedge_bot_task.delay(282)

    return Response({"status": "success"})
