from django.urls import path, include

from crypto import views

urlpatterns = [
    path("tickers", views.tickers, name="tickers"),
    path("future-arbitrage", views.future_arbitrages, name="future_arbitrages"),
    path("spot-arbitrage", views.spot_arbitrages, name="spot_arbitrages"),
    path("spot-arb-details", views.spot_arb_details_view, name="spot_arb_details"),
]
