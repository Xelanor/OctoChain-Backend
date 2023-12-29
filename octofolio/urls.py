from django.urls import path, include

from octofolio import views

urlpatterns = [
    path("", views.get_portfolios, name="portfolios"),
    path("assets", views.get_assets_price_list, name="get_assets_price_list"),
]
