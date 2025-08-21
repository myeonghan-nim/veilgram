from django.contrib import admin

from .models import Poll, PollOption, Vote


class PollOptionInline(admin.TabularInline):
    model = PollOption
    extra = 0


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("id", "owner", "allow_multiple", "created_at")
    list_filter = ("allow_multiple", "created_at")
    search_fields = ("id", "owner__id")
    inlines = [PollOptionInline]
    ordering = ("-created_at",)


@admin.register(PollOption)
class PollOptionAdmin(admin.ModelAdmin):
    list_display = ("id", "poll", "position", "text", "vote_count")
    search_fields = ("id", "poll__id", "text")
    ordering = ("poll", "position")


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("id", "voter", "poll", "option", "created_at")
    search_fields = ("id", "voter__id", "poll__id", "option__id")
    ordering = ("-created_at",)
