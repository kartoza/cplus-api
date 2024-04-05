from drf_yasg import openapi
from core.models.preferences import SitePreferences


LAYER_API_TAG = '01-layer'
SCENARIO_API_TAG = '02-scenario-analysis'
SCENARIO_OUTPUT_API_TAG = '03-scenario-outputs'

# API MANUAL PARAMETERS
PARAM_LAYER_UUID_IN_PATH = openapi.Parameter(
    'layer_uuid', openapi.IN_PATH,
    description='Layer UUID', type=openapi.TYPE_STRING
)


def get_page_size(request):
    """
    Get page size from request if exists
    if it does not exist in request, then get default from SitePreferences
    if over the maximum allowed size, then returns the maximum
    """
    config = SitePreferences.preferences().api_config
    page_size = request.GET.get('page_size', None)
    if page_size is None:
        page_size = (
            config['default_page_size'] if 'default_page_size' in config
            else 50
        )
    else:
        page_size = int(page_size)
    max_size = config['max_page_size'] if 'max_page_size' in config else 50
    if page_size > max_size:
        page_size = max_size
    return page_size
