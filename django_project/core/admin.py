"""Core admin."""
from django.contrib import admin
from core.models import SitePreferences, TaskLog


class SitePreferencesAdmin(admin.ModelAdmin):
    """Site Preferences admin."""

    fieldsets = (
        (None, {
            'fields': ('site_title',)
        }),
        ('API Configs', {
            'fields': (
                'api_config',
            )
        }),
    )


class TaskLogAdmin(admin.ModelAdmin):
    list_display = ('content_object', 'object_id', 'date_time',
                    'level', 'log',)
    list_filter = ["content_type"]


admin.site.register(SitePreferences, SitePreferencesAdmin)
admin.site.register(TaskLog, TaskLogAdmin)
