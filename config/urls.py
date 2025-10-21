from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.contrib.auth import views as auth_views
from django.urls import include
from accounts.views import register
from accounts.views import manage_landing, discogs_search


def index(request):
    return render(request, "home.html")


def placeholder(request, name):
    # Simple placeholder view that renders a template named <name>.html
    template = f"{name}.html"
    return render(request, template, {"placeholder_name": name})


urlpatterns = [
    path("", index, name="index"),
    path("admin/", admin.site.urls),
    path("store/", lambda r: placeholder(r, 'store'), name="store"),
    path("contact/", lambda r: placeholder(r, 'contact'), name="contact"),
    path("dashboard/", lambda r: placeholder(r, 'dashboard'), name="dashboard"),
    path("basket/", lambda r: placeholder(r, 'basket'), name="basket"),
    path("messages/", lambda r: placeholder(r, 'messages'), name="messages"),
    path("manage/", manage_landing, name="manage_landing"),
    path("manage/discogs/", discogs_search, name="manage_discogs"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path("accounts/register/", register, name='register'),
]
