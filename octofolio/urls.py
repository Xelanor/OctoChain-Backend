from django.urls import path, include

from octofolio import views

urlpatterns = [
    path("", views.get_portfolios, name="portfolios"),
]
