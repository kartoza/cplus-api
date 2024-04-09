from django.urls import path
from cplus_api.api_views.user import UserInfo
from cplus_api.api_views.layer import LayerList, LayerDetail, LayerUpload, LayerUploadStart, LayerUploadFinish


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
        'layer/upload/finish/<uuid:layer_uuid>/<str:filename>/',
        LayerUploadStart.as_view(),
        name='layer-upload-start'
    ),
    path(
        'layer/upload/finish/<uuid:layer_uuid>/',
        LayerUploadFinish.as_view(),
        name='layer-upload-finish'
    ),
    path(
        'layer/<uuid:layer_uuid>/',
        LayerDetail.as_view(),
        name='layer-detail'
    ),
]

urlpatterns = []
urlpatterns += user_urls
urlpatterns += layer_urls
