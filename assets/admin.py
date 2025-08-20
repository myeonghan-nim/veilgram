from django.contrib import admin

from .models import Asset


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "type", "status", "created_at")
    list_filter = ("type", "status", "created_at")
    search_fields = ("id", "owner__id", "storage_key")
    ordering = ("-created_at",)
