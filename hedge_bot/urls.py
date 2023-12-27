from django.urls import path, include

from hedge_bot import views

urlpatterns = [
    path("", views.get_hedge_bots, name="hedge_bots"),
]
