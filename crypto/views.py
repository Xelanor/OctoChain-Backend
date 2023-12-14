from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.core.cache import cache

from crypto.business_logic import calculate_future_arbitrage


@api_view(["GET"])
def tickers(request):
    if request.method == "GET":
        spot = cache.get("spot")
        swap = cache.get("swap")
        future = cache.get("future")

        spot = list(spot.values())
        spot = [i for i in spot if i["quote"] == "USDT"]

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
