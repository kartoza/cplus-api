from django.urls import path
from cplus_api.api_views.user import UserInfo
from cplus_api.api_views.layer import (
    LayerList, LayerDetail, LayerUpload,
    LayerUploadStart, LayerUploadFinish
)
from cplus_api.api_views.scenario import (
    ScenarioAnalysisSubmit,
    ExecuteScenarioAnalysis,
    CancelScenarioAnalysisTask,
    ScenarioAnalysisTaskStatus,
    ScenarioAnalysisTaskLogs,
    ScenarioAnalysisHistory,
    ScenarioAnalysisTaskDetail
)
from cplus_api.api_views.output import (
    UserScenarioAnalysisOutput,
    FetchScenarioAnalysisOutput
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
        'layer/upload/start/',
        LayerUploadStart.as_view(),
        name='layer-upload-start'
    ),
    path(
        'layer/upload/<uuid:layer_uuid>/finish/',
        LayerUploadFinish.as_view(),
        name='layer-upload-finish'
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
    path(
        'scenario/<uuid:scenario_uuid>/cancel/',
        CancelScenarioAnalysisTask.as_view(),
        name='scenario-cancel'
    ),
    path(
        'scenario/<uuid:scenario_uuid>/status/',
        ScenarioAnalysisTaskStatus.as_view(),
        name='scenario-status'
    ),
    path(
        'scenario/<uuid:scenario_uuid>/logs/',
        ScenarioAnalysisTaskLogs.as_view(),
        name='scenario-logs'
    ),
    path(
        'scenario/history/',
        ScenarioAnalysisHistory.as_view(),
        name='scenario-history'
    ),
    path(
        'scenario/<uuid:scenario_uuid>/detail/',
        ScenarioAnalysisTaskDetail.as_view(),
        name='scenario-detail'
    ),
]

# SCENARIO OUTPUTS API
scenario_output_urls = [
    path(
        'scenario_output/<uuid:scenario_uuid>/list/',
        UserScenarioAnalysisOutput.as_view(),
        name='scenario-output-list'
    ),
    path(
        'scenario_output/<uuid:scenario_uuid>/filter/',
        FetchScenarioAnalysisOutput.as_view(),
        name='scenario-output-list-by-uuids'
    ),
]

urlpatterns = []
urlpatterns += user_urls
urlpatterns += layer_urls
urlpatterns += scenario_urls
urlpatterns += scenario_output_urls
