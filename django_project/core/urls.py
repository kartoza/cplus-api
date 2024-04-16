"""core URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator
from django.http import HttpResponseNotFound
import json


class CustomSchemaGenerator(OpenAPISchemaGenerator):
    def get_schema(self, request=None, public=False):
        schema = super().get_schema(request, public)
        schema.schemes = ['https']
        # if settings.DEBUG:
        schema.schemes = ['http'] + schema.schemes
        return schema


schema_view_v1 = get_schema_view(
    openapi.Info(
        title="CPlus API",
        default_version='v0.0.1'
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
    generator_class=CustomSchemaGenerator,
    patterns=[
        re_path(r'api/v1/', include(
            ('cplus_api.urls_v1', 'api'),
            namespace='v1')
        )
    ],
)

admin.autodiscover()

urlpatterns = [
    re_path(r'^api/v1/docs/$', schema_view_v1.with_ui(
                'swagger', cache_timeout=0),
            name='schema-swagger-ui'),
    re_path(
        r'^admin/core/sitepreferences/$',
        RedirectView.as_view(
            url='/admin/core/sitepreferences/1/change/',
            permanent=False
        ),
        name='site-preferences'
    ),
    path('admin/', admin.site.urls),
    re_path(r'^api/v1/',
            include(('cplus_api.urls_v1', 'api'), namespace='v1')),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


def response404(request, exception):
    # handler when no url is found
    data = {'detail': 'Not Found'}
    return HttpResponseNotFound(
        json.dumps(data),
        content_type='application/json'
    )


handler404 = response404  # noqa
