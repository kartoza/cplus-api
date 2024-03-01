"""Core admin."""
from django.contrib import admin
from core.models import SitePreferences


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


admin.site.register(SitePreferences, SitePreferencesAdmin)
