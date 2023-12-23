from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.core.cache import cache

from crypto.future_arbitrage import calculate_future_arbitrage
from crypto.spot_arbitrage import spot_arb_details


@api_view(["GET"])
def tickers(request):
    if request.method == "GET":
        spot = cache.get("spot")
        swap = cache.get("swap")
        future = cache.get("future")

        spot = list(spot.values())
        spot = [i for i in spot if i["quote"] == "USDT"]

        # spot = [
        #     {**coin, "exchanges": list(coin["exchanges"].values())} for coin in spot
        # ]

        swap = list(swap.values())
        swap = [i for i in swap if i["type"] == "swap"]

        future = list(future.values())
        future = [i for i in future if i["type"] == "future"]

        return Response({"spot": spot, "swap": swap, "future": future})


@api_view(["GET"])
def future_arbitrages(request):
    if request.method == "GET":
        arbitrages = calculate_future_arbitrage()

        return Response({"arbitrages": arbitrages})


@api_view(["GET"])
def spot_arbitrages(request):
    if request.method == "GET":
        arbitrages = []
        arbs_keys = cache.keys("arb_*")
        for arb_key in arbs_keys:
            arb = cache.get(arb_key)
            arbitrages.append(arb)

        return Response({"arbitrages": arbitrages})


@api_view(["POST"])
def spot_arb_details_view(request):
    if request.method == "POST":
        body = request.data
        symbol = body["symbol"]
        from_exc = body["from_exc"]
        to_exc = body["to_exc"]
        hedge_symbol = body["hedge_symbol"]
        hedge_exc = body["hedge_exc"]

        details = spot_arb_details(symbol, from_exc, to_exc, hedge_symbol, hedge_exc)

        return Response({"details": details})
