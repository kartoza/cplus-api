"""Model factories."""
import factory
import uuid
from typing import Generic, TypeVar
from django.contrib.auth import get_user_model
from django.utils import timezone
from cplus_api.models.scenario import ScenarioTask
from cplus_api.models.layer import (
    BaseLayer, InputLayer,
    OutputLayer, MultipartUpload
)


T = TypeVar('T')
User = get_user_model()


class BaseMetaFactory(Generic[T], factory.base.FactoryMetaClass):
    def __call__(cls, *args, **kwargs) -> T:
        return super().__call__(*args, **kwargs)


class BaseFactory(Generic[T], factory.django.DjangoModelFactory):
    @classmethod
    def create(cls, **kwargs) -> T:
        return super().create(**kwargs)


class UserF(BaseFactory[User],
            metaclass=BaseMetaFactory[User]):
    class Meta:
        model = User

    username = factory.Sequence(
        lambda n: u'username %s' % n
    )
    first_name = 'John'
    last_name = 'Doe'


class ScenarioTaskF(BaseFactory[ScenarioTask],
                    metaclass=BaseMetaFactory[ScenarioTask]):
    class Meta:
        model = ScenarioTask

    api_version = 'v1'
    plugin_version = '0.0.1'
    submitted_by = factory.SubFactory(UserF)
    submitted_on = timezone.now()
    detail = {
        "scenario_name": "Scenario 1",
        "scenario_desc": "Test",
        "extent": [
            878529.3786140494,
            911063.0818645271,
            7216308.751738624,
            7279753.465204147
        ],
        "snap_layer": "",
        "snap_layer_uuid": "",
        "pathway_suitability_index": 0,
        "snap_rescale": False,
        "snap_method": "0",
        "sieve_enabled": False,
        "sieve_threshold": 10,
        "sieve_mask_path": "",
        "sieve_mask_uuid": "",
        "mask_path": "",
        "mask_layer_uuids": [],
        "priority_layers": [
            {
                "uuid": "3e0c7dff-51f2-48c5-a316-15d9ca2407cb",
                "name": "Ecological Infrastructure inverse",
                "description": (
                    "Placeholder text for ecological infrastructure inverse"
                ),
                "path": "ei_all_gknp_clip_norm.tif",
                "selected": False,
                "user_defined": False,
                "groups": []
            },
            {
                "uuid": "88c1c7dd-c5d1-420c-a71c-a5c595c1c5be",
                "name": "Ecological Infrastructure",
                "description": (
                    "Placeholder text for ecological infrastructure"
                ),
                "path": "ei_all_gknp_clip_norm.tif",
                "selected": False,
                "user_defined": False,
                "groups": []
            },
            {
                "uuid": "9ab8c67a-5642-4a09-a777-bd94acfae9d1",
                "name": "Biodiversity norm",
                "description": "Placeholder text for biodiversity norm",
                "path": "biocombine_clip_norm.tif",
                "selected": False,
                "user_defined": False,
                "groups": []
            },
            {
                "uuid": "c2dddd0f-a430-444a-811c-72b987b5e8ce",
                "name": "Biodiversity norm inverse",
                "description": (
                    "Placeholder text for biodiversity norm inverse"
                ),
                "path": "biocombine_clip_norm_inverse.tif",
                "selected": False,
                "user_defined": False,
                "groups": []
            },
            {
                "uuid": "c931282f-db2d-4644-9786-6720b3ab206a",
                "name": "Social norm",
                "description": "Placeholder text for social norm ",
                "path": "social_int_clip_norm.tif",
                "selected": True,
                "user_defined": False,
                "groups": []
            },
            {
                "uuid": "f5687ced-af18-4cfc-9bc3-8006e40420b6",
                "name": "Social norm inverse",
                "description": "Placeholder text for social norm inverse",
                "path": "social_int_clip_norm_inverse.tif",
                "selected": False,
                "user_defined": False,
                "groups": []
            },
            {
                "uuid": "fce41934-5196-45d5-80bd-96423ff0e74e",
                "name": "Climate Resilience norm",
                "description": "Placeholder text for climate resilience norm",
                "path": "cccombo_clip_norm.tif",
                "selected": False,
                "user_defined": False,
                "groups": []
            },
            {
                "uuid": "fef3c7e4-0cdf-477f-823b-a99da42f931e",
                "name": "Climate Resilience norm inverse",
                "description": "Placeholder text for climate resilience",
                "path": "cccombo_clip_norm_inverse.tif",
                "selected": False,
                "user_defined": False,
                "groups": []
            }
        ],
        "priority_layer_groups": [
            {
                "name": "Climate Resilience",
                "value": 0,
                "layers": []
            },
            {
                "name": "Finance - Net Present value",
                "value": "0",
                "layers": []
            },
            {
                "name": "Finance - Years Experience",
                "value": "0",
                "layers": []
            },
            {
                "name": "Finance - Carbon",
                "value": "0",
                "layers": []
            },
            {
                "name": "Livelihood",
                "value": "0",
                "layers": []
            },
            {
                "name": "Policy",
                "value": "0",
                "layers": []
            },
            {
                "name": "Ecological infrastructure",
                "value": "0",
                "layers": []
            },
            {
                "name": "Finance - Market Trends",
                "value": "0",
                "layers": []
            },
            {
                "name": "Biodiversity",
                "value": "0",
                "layers": []
            }
        ],
        "activities": [
            {
                "uuid": "1c8db48b-717b-451b-a644-3af1bee984ea",
                "name": "Alien Plant Removal",
                "description": "Test.",
                "path": "",
                "layer_type": -1,
                "user_defined": False,
                "pathways": [
                    {
                        "uuid": "5fe775ba-0e80-4b70-a53a-1ed874b72da3",
                        "name": "Alien Plant Removal",
                        "description": "Alien Plant Class.",
                        "path": (
                            "/home/web/media/ncs_pathways/"
                            "Final_Alien_Invasive_Plant_priority_norm.tif"
                        ),
                        "layer_type": 0,
                        "carbon_paths": []
                    }
                ],
                "priority_layers": [
                    {
                        "uuid": "c931282f-db2d-4644-9786-6720b3ab206a",
                        "name": "Social norm",
                        "description": "Placeholder text for social norm ",
                        "path": "social_int_clip_norm.tif",
                        "selected": True,
                        "user_defined": False,
                        "groups": []
                    },
                    {
                        "uuid": "88c1c7dd-c5d1-420c-a71c-a5c595c1c5be",
                        "name": "Ecological Infrastructure",
                        "description": "Placeholder text for ecological",
                        "path": "ei_all_gknp_clip_norm.tif",
                        "selected": False,
                        "user_defined": False,
                        "groups": []
                    },
                    {
                        "uuid": "9ab8c67a-5642-4a09-a777-bd94acfae9d1",
                        "name": "Biodiversity norm",
                        "description": "Placeholder text for biodiversity",
                        "path": "biocombine_clip_norm.tif",
                        "selected": False,
                        "user_defined": False,
                        "groups": []
                    }
                ],
                "layer_styles": {
                    "scenario_layer": {
                        "color": "#6f6f6f",
                        "style": "solid",
                        "outline_width": "0",
                        "outline_color": "35,35,35,0"
                    },
                    "model_layer": {
                        "color_ramp": {
                            "colors": "8",
                            "inverted": "0",
                            "rampType": "colorbrewer",
                            "schemeName": "Greys"
                        },
                        "ramp_type": "colorbrewer"
                    }
                }
            }
        ]
    }


class InputLayerF(BaseFactory[InputLayer],
                  metaclass=BaseMetaFactory[InputLayer]):
    class Meta:
        model = InputLayer

    name = factory.Sequence(
        lambda n: u'input_layer_ %s' % n
    )
    created_on = timezone.now()
    owner = factory.SubFactory(UserF)
    layer_type = BaseLayer.LayerTypes.RASTER
    component_type = InputLayer.ComponentTypes.NCS_PATHWAY
    privacy_type = InputLayer.PrivacyTypes.PRIVATE


class OutputLayerF(BaseFactory[OutputLayer],
                   metaclass=BaseMetaFactory[OutputLayer]):
    class Meta:
        model = OutputLayer

    name = factory.Sequence(
        lambda n: u'output_layer_ %s' % n
    )
    created_on = timezone.now()
    owner = factory.SubFactory(UserF)
    layer_type = BaseLayer.LayerTypes.RASTER
    scenario = factory.SubFactory(ScenarioTaskF)


class MultipartUploadF(BaseFactory[MultipartUpload],
                       metaclass=BaseMetaFactory[MultipartUpload]):
    class Meta:
        model = MultipartUpload

    upload_id = factory.Sequence(
        lambda n: u'upload_id_ %s' % n
    )
    input_layer_uuid = uuid.uuid4()
    created_on = timezone.now()
    uploader = factory.SubFactory(UserF)
    parts = 10
    is_aborted = False
