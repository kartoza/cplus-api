import json
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from rest_framework.test import APIClient

from core.settings.utils import absolute_path
from cplus_api.models.layer import InputLayer
from cplus_api.models.statistics import ZonalStatisticsTask
from cplus_api.serializers.statistics import (
    ZonalStatisticsRequestSerializer,
)
from cplus_api.tasks.zonal_statistics import calculate_zonal_statistics
from cplus_api.tests.common import (
    BaseAPIViewTransactionTest,
)
from cplus_api.tests.factories import InputLayerF


class TestZonalStatisticsAPI(BaseAPIViewTransactionTest):
    """Test the statistics API view."""

    def setUp(self):
        super().setUp()
        self.nature_base_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.COMMON,
            source=InputLayer.LayerSources.NATURE_BASE,
        )
        # Non-NatureBase layer to assert filtering if needed
        self.other_layer = InputLayerF.create()

        # Ensure the layer file exists so that layer.is_available()
        # returns True in the zonal stats task
        try:
            file_path = absolute_path(
                "cplus_api", "tests", "data", "models", "test_model_1.tif"
            )
            self.store_layer_file(self.nature_base_layer, file_path)
        except Exception:
            # If the file is missing, computation will be patched in the
            # other tests.
            pass

    @staticmethod
    def _sample_bbox_list():
        return [32.837359200, -2.446597436, 39.840833391, 5.444363593]

    @staticmethod
    def _sample_bbox_string():
        bbox_list = TestZonalStatisticsAPI._sample_bbox_list()
        return ",".join(str(v) for v in bbox_list)

    def _get(self, url, params, client=None):
        # Encode values for querystring.
        qs = {
            k: (json.dumps(v) if isinstance(v, (dict, list)) else str(v))
            for k, v in params.items()
        }
        if client is None:
            client = self.client
        return client.get(url, data=qs)

    def test_request_serializer_validates_bbox(self):
        """Assert bbox validation."""
        bbox_str = self._sample_bbox_string()
        data = {"bbox": bbox_str}
        serializer = ZonalStatisticsRequestSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        # In case of a missing bbox
        missing_bbox = {}
        missing_serializer = ZonalStatisticsRequestSerializer(
            data=missing_bbox
        )
        assert not missing_serializer.is_valid()
        assert "bbox" in missing_serializer.errors

        # In case of an empty bbox
        empty_bbox = {"bbox": ""}
        empty_bbox_serializer = ZonalStatisticsRequestSerializer(
            data=empty_bbox
        )
        assert not empty_bbox_serializer.is_valid()
        assert "bbox" in empty_bbox_serializer.errors

    def test_unauthenticated_get_returns_401_or_403(self):
        """Assert that unauthenticated requests are rejected
        i.e. 401 or 403.
        """
        url = reverse("v1:zonal-statistics")
        params = {"bbox": self._sample_bbox_string()}
        resp = self._get(url, params)
        assert resp.status_code in (401, 403)

    def test_zonal_statistics_get_creates_task_and_enqueues_celery(self):
        """Simulate the zonal stats celery task."""
        url = reverse("v1:zonal-statistics")
        params = {"bbox": self._sample_bbox_string()}
        patch_path = (
            "cplus_api.tasks.zonal_statistics.calculate_zonal_statistics.delay"
        )

        api_client = APIClient()
        api_client.force_authenticate(user=self.superuser)

        with mock.patch(patch_path) as mock_delay:
            mock_delay.return_value = mock.Mock(id="celery-task-id")
            resp = self._get(url, params, client=api_client)

            assert 200 <= resp.status_code < 300, getattr(
                resp, "content", None
            )

            data = resp.json()
            if "task_uuid" in data:
                task_uuid = data["task_uuid"]
            else:
                task_uuid = data.get("uuid")

            assert task_uuid is not None, f"unexpected response: {data}"

            task = ZonalStatisticsTask.objects.filter(uuid=task_uuid).first()
            assert task is not None

            # Assert the celery task was enqueued
            mock_delay.assert_called_once()
            called_args = mock_delay.call_args[0]
            assert len(called_args) == 1

    def test_zonal_statistics_task_error_is_persisted_by_worker(self):
        """Simulate zonal stats task internal failure."""
        bbox = self._sample_bbox_list()
        task = ZonalStatisticsTask.objects.create(
            bbox_minx=bbox[0],
            bbox_miny=bbox[1],
            bbox_maxx=bbox[2],
            bbox_maxy=bbox[3],
            submitted_by=self.superuser,
            submitted_on=timezone.now(),
        )

        # Patch the layer queryset to raise so the task catches
        # and persists the error
        with mock.patch(
            "cplus_api.models.layer.InputLayer.objects.filter",
            side_effect=RuntimeError("simulated worker failure"),
        ):
            try:
                calculate_zonal_statistics(task.id)
            except Exception:
                pass

        task.refresh_from_db()
        assert (
            task.error_message is not None and
            str(task.error_message) != ""
        )
        assert (
            task.stack_trace_errors is not None and
            str(task.stack_trace_errors) != ""
        )
