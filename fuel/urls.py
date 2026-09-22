from django.urls import path

from fuel import views

urlpatterns = [
    path("", views.index_view, name="index"),
    path("api/route/", views.route_view, name="route"),
    path("api/cities/", views.city_search_view, name="city-search"),
    path("api/health/", views.health_view, name="health"),
]
