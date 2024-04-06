from django.urls import path
from cplus_api.api_views.user import UserInfo
from cplus_api.api_views.layer import LayerList, LayerDetail, LayerUpload
from cplus_api.api_views.scenario import (
    ScenarioAnalysisSubmit,
    ExecuteScenarioAnalysis
)


# USER API
user_urls = [
    path(
        'user/me',
        UserInfo.as_view(),
        name='user-info'
    ),
]

# LAYER API
layer_urls = [
    path(
        'layer/list/',
        LayerList.as_view(),
        name='layer-list'
    ),
    path(
        'layer/upload/',
        LayerUpload.as_view(),
        name='layer-upload'
    ),
    path(
        'layer/<uuid:layer_uuid>/',
        LayerDetail.as_view(),
        name='layer-detail'
    ),
]

# SCENARIO ANALYSIS API
scenario_urls = [
    path(
        'scenario/submit/',
        ScenarioAnalysisSubmit.as_view(),
        name='scenario-submit'
    ),
    path(
        'scenario/<uuid:scenario_uuid>/execute/',
        ExecuteScenarioAnalysis.as_view(),
        name='scenario-execute'
    ),
]

urlpatterns = []
urlpatterns += user_urls
urlpatterns += layer_urls
urlpatterns += scenario_urls
