from django.contrib import admin
from django.urls import path
from django.http import HttpResponse


def index(request):
    return HttpResponse("alans-albums project is configured")


urlpatterns = [
    path("", index, name="index"),
    path("admin/", admin.site.urls),
]
