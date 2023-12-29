from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.utils.timezone import now
from django.core.cache import cache

from octofolio.models import Asset, Portfolio, Transaction


@api_view(["GET"])
def get_portfolios(request):
    spot = cache.get("spot")

    portfolios = []

    portfolio_objects = Portfolio.objects.all()
    for portfolio_object in portfolio_objects:
        portfolio_id = portfolio_object.id
        portfolio_name = portfolio_object.name

        portfolio = {
            "id": portfolio_id,
            "name": portfolio_name,
            "assets": [],
            "total_value": 0,
            "total_investment": 0,
            "total_profit": 0,
            "total_profit_percentage": 0,
        }

        asset_objects = portfolio_object.get_assets()

        for asset_object in asset_objects:
            asset_id = asset_object.id
            asset_symbol = asset_object.symbol
            asset_name = asset_object.name
            asset_type = asset_object.asset_type
            asset_tag = asset_object.tag
            asset_logo = asset_object.logo

            asset_ticker = f"{asset_symbol}/USDT"
            asset_price = spot[asset_ticker]["price"]

            asset = {
                "id": asset_id,
                "symbol": asset_symbol,
                "name": asset_name,
                "type": asset_type,
                "tag": asset_tag,
                "logo": asset_logo,
                "asset_quantity": 0,
                "asset_value": 0,
                "asset_investment": 0,
                "average_cost": 0,
                "asset_profit": 0,
                "asset_profit_percentage": 0,
                "transactions": [],
                "price": asset_price,
            }

            transaction_objects = Transaction.objects.filter(
                portfolio=portfolio_object, asset=asset_object
            )

            for transaction_object in transaction_objects:
                transaction_id = transaction_object.id
                transaction_type = transaction_object.transaction_type
                transaction_price = transaction_object.price
                transaction_quantity = transaction_object.quantity
                transaction_date = transaction_object.date

                transaction = {
                    "id": transaction_id,
                    "type": transaction_type,
                    "price": transaction_price,
                    "quantity": transaction_quantity,
                    "total": transaction_price * transaction_quantity,
                    "date": transaction_date.strftime("%s"),
                }

                asset["transactions"].append(transaction)

                if transaction_type == "buy":
                    asset["asset_investment"] += (
                        transaction_price * transaction_quantity
                    )
                    asset["asset_quantity"] += transaction_quantity
                else:
                    asset["asset_investment"] -= (
                        transaction_price * transaction_quantity
                    )
                    asset["asset_quantity"] -= transaction_quantity

            asset["average_cost"] = asset["asset_investment"] / asset["asset_quantity"]
            asset["asset_value"] = asset["price"] * asset["asset_quantity"]
            asset["asset_profit"] = asset["asset_value"] - asset["asset_investment"]
            asset["asset_profit_percentage"] = (
                asset["asset_profit"] / asset["asset_investment"]
            )

            portfolio["assets"].append(asset)

            portfolio["total_investment"] += asset["asset_investment"]
            portfolio["total_value"] += asset["asset_value"]
            portfolio["total_profit"] += asset["asset_profit"]
            portfolio["total_profit_percentage"] += asset["asset_profit_percentage"]

        portfolios.append(portfolio)

    return Response(portfolios)


@api_view(["GET"])
def get_assets_price_list(request):
    spot = cache.get("spot")

    assets_price_list = []

    asset_objects = Asset.objects.all()
    for asset_object in asset_objects:
        asset_symbol = asset_object.symbol

        asset_ticker = f"{asset_symbol}/USDT"
        asset_price = spot[asset_ticker]["price"]

        asset = {
            "symbol": asset_symbol,
            "name": asset_object.name,
            "price": asset_price,
            "logo": asset_object.logo,
        }

        assets_price_list.append(asset)

    return Response(assets_price_list)
