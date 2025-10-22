from django.contrib import admin
from .models import Listing


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('artist', 'title', 'catalog_number', 'price', 'condition', 'featured', 'created_at', 'created_by')
    search_fields = ('artist', 'title', 'catalog_number')
    list_filter = ('condition', 'created_at')
