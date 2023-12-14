from django.urls import path, include

from crypto import views

urlpatterns = [
    path("tickers", views.tickers, name="tickers"),
    path("future-arbitrage", views.future_arbitrages, name="future_arbitrages"),
]
