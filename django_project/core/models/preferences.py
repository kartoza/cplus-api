"""Model for Website Preferences."""
from django.db import models

from core.models.singleton import SingletonModel


def default_api_config():
    """
    Default value for Preference's api_config.
    """
    return {'default_page_size': 50, 'max_page_size': 50}


class SitePreferences(SingletonModel):
    """Preference settings specifically for website.

    Preference contains
    - site_title
    - primary_color
    - secondary_color
    - icon
    - favicon
    - search_similarity
    """

    site_title = models.CharField(
        max_length=512,
        default='CPLUS API'
    )
    # -----------------------------------------------
    # API pagination setting
    # -----------------------------------------------
    api_config = models.JSONField(
        default=default_api_config,
        blank=True,
        help_text='API pagination configuration.'
    )

    class Meta:  # noqa: D106
        verbose_name_plural = "site preferences"

    @staticmethod  # noqa
    def preferences() -> "SitePreferences":
        """Load Site Preference."""
        return SitePreferences.load()

    def __str__(self):
        return 'Site Preference'
