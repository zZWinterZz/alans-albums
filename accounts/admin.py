from django.contrib import admin
from .models import Listing, ListingImage
from .models import Message, MessageImage, Reply, ReplyImage


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


class MessageImageInline(admin.TabularInline):
    model = MessageImage
    fields = ('image', 'caption', 'uploaded_by', 'uploaded_at')
    readonly_fields = ('uploaded_at',)
    extra = 0


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'name', 'email', 'phone', 'is_read', 'replied', 'created_at')
    search_fields = ('name', 'email', 'username', 'body')
    list_filter = ('subject', 'is_read', 'replied', 'created_at')
    inlines = [MessageImageInline]


class ReplyImageInline(admin.TabularInline):
    model = ReplyImage
    fields = ('image', 'uploaded_at')
    readonly_fields = ('uploaded_at',)
    extra = 0


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ('message', 'user', 'created_at')
    search_fields = ('body', 'user__username', 'message__email')
    inlines = [ReplyImageInline]


@admin.register(MessageImage)
class MessageImageAdmin(admin.ModelAdmin):
    list_display = ('message', 'uploaded_by', 'uploaded_at')


@admin.register(ReplyImage)
class ReplyImageAdmin(admin.ModelAdmin):
    list_display = ('reply', 'uploaded_at')
