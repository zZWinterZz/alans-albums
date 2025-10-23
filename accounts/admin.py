from django.contrib import admin
from .models import Listing
from .models import ListingImage


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ('artist', 'title', 'catalog_number', 'price', 'condition', 'featured', 'created_at', 'created_by')
    search_fields = ('artist', 'title', 'catalog_number')
    list_filter = ('condition', 'created_at')


class ListingImageInline(admin.TabularInline):
    model = ListingImage
    fields = ('image', 'caption', 'order', 'uploaded_by', 'created_at')
    readonly_fields = ('created_at',)
    extra = 1


ListingAdmin.inlines = [ListingImageInline]
