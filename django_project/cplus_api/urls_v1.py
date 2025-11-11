from django.urls import path
from cplus_api.api_views.user import UserInfo
from cplus_api.api_views.layer import (
    LayerList,
    LayerDetail,
    LayerUpload,
    LayerUploadStart,
    LayerUploadFinish,
    CheckLayer,
    LayerUploadAbort,
    FetchLayerByClientId,
    DefaultLayerList,
    ReferenceLayerDownload,
    DefaultLayerDownload,
)
from cplus_api.api_views.scenario import (
    ScenarioAnalysisSubmit,
    ExecuteScenarioAnalysis,
    CancelScenarioAnalysisTask,
    ScenarioAnalysisTaskStatus,
    ScenarioAnalysisTaskLogs,
    ScenarioAnalysisHistory,
    ScenarioAnalysisTaskDetail,
)
from cplus_api.api_views.statistics import (
    ZonalStatisticsView,
    ZonalStatisticsProgressView,
)
from cplus_api.api_views.output import (
    UserScenarioAnalysisOutput,
    FetchScenarioAnalysisOutput,
)


# USER API
user_urls = [
    path("user/me", UserInfo.as_view(), name="user-info"),
]

# LAYER API
layer_urls = [
    path(
        "layer/default/", DefaultLayerList.as_view(), name="layer-default-list"
    ),
    path("layer/list/", LayerList.as_view(), name="layer-list"),
    path(
        "layer/filter/client_id/",
        FetchLayerByClientId.as_view(),
        name="fetch-layer-by-client-id",
    ),
    path(
        "layer/upload/start/",
        LayerUploadStart.as_view(),
        name="layer-upload-start",
    ),
    path(
        "layer/upload/<uuid:layer_uuid>/finish/",
        LayerUploadFinish.as_view(),
        name="layer-upload-finish",
    ),
    path(
        "layer/upload/<uuid:layer_uuid>/abort/",
        LayerUploadAbort.as_view(),
        name="layer-upload-abort",
    ),
    path("layer/upload/", LayerUpload.as_view(), name="layer-upload"),
    path("layer/check/", CheckLayer.as_view(), name="layer-check"),
    path(
        "layer/<uuid:layer_uuid>/", LayerDetail.as_view(), name="layer-detail"
    ),
    path(
        "reference_layer/carbon_calculation/",
        ReferenceLayerDownload.as_view(),
        name="reference-layer-download",
    ),
    path(
        "priority_layer/<uuid:layer_uuid>/download/",
        DefaultLayerDownload.as_view(),
        name="default-priority-layer-download",
    ),
]

# SCENARIO ANALYSIS API
scenario_urls = [
    path(
        "scenario/submit/",
        ScenarioAnalysisSubmit.as_view(),
        name="scenario-submit",
    ),
    path(
        "scenario/<uuid:scenario_uuid>/execute/",
        ExecuteScenarioAnalysis.as_view(),
        name="scenario-execute",
    ),
    path(
        "scenario/<uuid:scenario_uuid>/cancel/",
        CancelScenarioAnalysisTask.as_view(),
        name="scenario-cancel",
    ),
    path(
        "scenario/<uuid:scenario_uuid>/status/",
        ScenarioAnalysisTaskStatus.as_view(),
        name="scenario-status",
    ),
    path(
        "scenario/<uuid:scenario_uuid>/logs/",
        ScenarioAnalysisTaskLogs.as_view(),
        name="scenario-logs",
    ),
    path(
        "scenario/history/",
        ScenarioAnalysisHistory.as_view(),
        name="scenario-history",
    ),
    path(
        "scenario/<uuid:scenario_uuid>/detail/",
        ScenarioAnalysisTaskDetail.as_view(),
        name="scenario-detail",
    ),
]

# SCENARIO OUTPUTS API
scenario_output_urls = [
    path(
        "scenario_output/<uuid:scenario_uuid>/list/",
        UserScenarioAnalysisOutput.as_view(),
        name="scenario-output-list",
    ),
    path(
        "scenario_output/<uuid:scenario_uuid>/filter/",
        FetchScenarioAnalysisOutput.as_view(),
        name="scenario-output-list-by-uuids",
    ),
]

# Statistics API
layer_statistics_urls = [
    path(
        "zonal_statistics/",
        ZonalStatisticsView.as_view(),
        name="zonal-statistics",
    ),
    path(
        "zonal_statistics/<uuid:task_uuid>/progress/",
        ZonalStatisticsProgressView.as_view(),
        name="zonal-statistics-progress",
    ),
]

urlpatterns = []
urlpatterns += user_urls
urlpatterns += layer_urls
urlpatterns += scenario_urls
urlpatterns += scenario_output_urls
urlpatterns += layer_statistics_urls
