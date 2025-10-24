from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.contrib.auth import views as auth_views
from django.urls import include
from accounts.views import register
from accounts.views import manage_landing, discogs_search
from accounts.views import discogs_price_suggestions_view, discogs_release_details_view
from accounts.views import create_listing, listing_list, listing_edit, listing_delete, listing_toggle_featured, store_list


def index(request):
    return render(request, "home.html")


def placeholder(request, name):
    # Simple placeholder view that renders a template named <name>.html
    template = f"{name}.html"
    return render(request, template, {"placeholder_name": name})


urlpatterns = [
    path("", index, name="index"),
    path("admin/", admin.site.urls),
    path("store/", store_list, name="store"),
    path("contact/", lambda r: placeholder(r, 'contact'), name="contact"),
    path("dashboard/", lambda r: placeholder(r, 'dashboard'), name="dashboard"),
    path("basket/", lambda r: placeholder(r, 'basket'), name="basket"),
    path("messages/", lambda r: placeholder(r, 'messages'), name="messages"),
    path("manage/", manage_landing, name="manage_landing"),
    path("manage/discogs/", discogs_search, name="manage_discogs"),
    path("manage/listings/", listing_list, name="listing_list"),
    path("manage/discogs/price_suggestions/<int:release_id>/", discogs_price_suggestions_view, name="discogs_price_suggestions"),
    path("manage/discogs/release_details/<int:release_id>/", discogs_release_details_view, name="discogs_release_details"),
    path("manage/listings/create/", create_listing, name="create_listing"),
    path("manage/listings/<int:pk>/edit/", listing_edit, name="listing_edit"),
    path("manage/listings/<int:pk>/delete/", listing_delete, name="listing_delete"),
    path("manage/listings/<int:pk>/toggle-featured/", listing_toggle_featured, name="listing_toggle_featured"),
    path("store/listings/", store_list, name="store_list"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path("accounts/register/", register, name='register'),
]
