from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.utils.timezone import now
from django.core.cache import cache

from hedge_bot.models import HedgeBot, HedgeBotTx
from octofolio.models import Asset


@api_view(["GET"])
def get_hedge_bots(request):
    spot = cache.get("spot")
    swap = cache.get("swap")

    hedge_bots = []

    hedge_bot_objects = HedgeBot.objects.all()
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
        hedge_bot_min_profit = hedge_bot_object.min_profit
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
            "min_profit": hedge_bot_min_profit,
            "created_at": hedge_bot_created_at,
            "total_value": 0,
            "total_investment": 0,
            "total_profit": 0,
            "total_profit_percentage": 0,
            "transactions": [],
        }

        hedge_bot_tx_objects = HedgeBotTx.objects.filter(bot=hedge_bot_object)

        for hedge_bot_tx_object in hedge_bot_tx_objects:
            hedge_bot_tx_id = hedge_bot_tx_object.id
            hedge_bot_tx_side = hedge_bot_tx_object.side
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
                "spot_price": hedge_bot_tx_spot_price,
                "hedge_price": hedge_bot_tx_hedge_price,
                "spot_total": hedge_bot_tx_spot_quantity * hedge_bot_tx_spot_price,
                "hedge_total": hedge_bot_tx_hedge_quantity * hedge_bot_tx_hedge_price,
                "spot_exchange": hedge_bot_tx_spot_exchange,
                "hedge_exchange": hedge_bot_tx_hedge_exchange,
                "spot_quantity": hedge_bot_tx_spot_quantity,
                "hedge_quantity": hedge_bot_tx_hedge_quantity,
                "fee": hedge_bot_tx_fee,
                "created_at": hedge_bot_tx_created_at.strftime("%s"),
            }

            hedge_bot_tx["profit"] = (
                hedge_bot_tx_hedge_quantity * hedge_bot_tx_hedge_price
                - hedge_bot_tx_spot_quantity * hedge_bot_tx_spot_price
                - hedge_bot_tx_fee
            )

            hedge_bot_tx["profit_percentage"] = (
                hedge_bot_tx["profit"] / hedge_bot_tx["spot_total"]
            )

            hedge_bot["transactions"].append(hedge_bot_tx)

        hedge_bots.append(hedge_bot)

    return Response(hedge_bots)
