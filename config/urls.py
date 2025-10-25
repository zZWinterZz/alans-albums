from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.contrib.auth import views as auth_views
from accounts.views import CustomLoginView
from django.urls import include
from accounts.views import register, contact_view, messages_inbox
from accounts.views import manage_landing, discogs_search
from accounts.views import message_thread, guest_reply
from accounts.views import discogs_price_suggestions_view, discogs_release_details_view
from accounts.views import create_listing, listing_list, listing_edit, listing_delete, listing_toggle_featured, store_list
from accounts.views import delete_reply, delete_message, delete_selected_messages
# Import the module namespace so we can reference basket/stripe views below
from accounts import views as accounts_views


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
    path("contact/", contact_view, name="contact"),
    path("dashboard/", accounts_views.dashboard_view, name="dashboard"),
    # Basket views (session-backed) and Stripe webhook
    path("basket/", accounts_views.basket_view, name="basket"),
    path("basket/add/<int:listing_id>/", accounts_views.basket_add, name="basket_add"),
    path("basket/remove/<int:listing_id>/", accounts_views.basket_remove, name="basket_remove"),
    path("basket/checkout/", accounts_views.basket_checkout, name="basket_checkout"),
    path("basket/success/", accounts_views.basket_success, name="basket_success"),
    path("basket/cancel/", accounts_views.basket_cancel, name="basket_cancel"),
    path("stripe/webhook/", accounts_views.stripe_webhook, name="stripe_webhook"),
    path("messages/", messages_inbox, name="messages"),
    path("messages/<int:pk>/", message_thread, name="message_thread"),
    path("messages/<int:pk>/delete/", delete_message, name="delete_message"),
    path("messages/reply/<int:reply_id>/delete/", delete_reply, name="delete_reply"),
    path("messages/delete_selected/", delete_selected_messages, name="messages_delete_selected"),
    path("messages/guest/<uuid:reference>/", guest_reply, name="guest_reply"),
    path("manage/", manage_landing, name="manage_landing"),
    path("manage/discogs/", discogs_search, name="manage_discogs"),
    path("manage/listings/", listing_list, name="listing_list"),
    path("manage/listings/<int:pk>/quick-update/", accounts_views.listing_quick_update, name="listing_quick_update"),
    path("manage/discogs/price_suggestions/<int:release_id>/", discogs_price_suggestions_view, name="discogs_price_suggestions"),
    path("manage/discogs/release_details/<int:release_id>/", discogs_release_details_view, name="discogs_release_details"),
    path("manage/listings/create/", create_listing, name="create_listing"),
    path("manage/listings/<int:pk>/edit/", listing_edit, name="listing_edit"),
    path("manage/listings/<int:pk>/delete/", listing_delete, name="listing_delete"),
    path("manage/listings/<int:pk>/toggle-featured/", listing_toggle_featured, name="listing_toggle_featured"),
    path("store/listings/", store_list, name="store_list"),
    path("accounts/login/", CustomLoginView.as_view(), name='login'),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path("accounts/register/", register, name='register'),
    # Profile edit
    path("accounts/profile/edit/", accounts_views.profile_edit, name='profile_edit'),
    # Include Django's built-in auth URLs (password change, reset, etc.)
    path('accounts/', include('django.contrib.auth.urls')),
]
