from django.urls import path, include

from hedge_bot import views

urlpatterns = [
    path("", views.get_hedge_bots, name="hedge_bots"),
    path("funds", views.get_exchange_funds, name="get_exchange_funds"),
    path("run", views.run_hedge_bot, name="run_hedge_bot"),
]
