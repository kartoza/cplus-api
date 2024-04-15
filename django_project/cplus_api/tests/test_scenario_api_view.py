import mock
import json
from django.urls import reverse
from core.models.base_task_request import TaskStatus
from core.settings.utils import absolute_path
from cplus_api.api_views.scenario import (
    ScenarioAnalysisSubmit,
    ExecuteScenarioAnalysis
)
from cplus_api.models.layer import InputLayer
from cplus_api.models.scenario import ScenarioTask
from cplus_api.tests.common import (
    FakeResolverMatchV1,
    BaseAPIViewTransactionTest,
    mocked_process
)
from cplus_api.tests.factories import (
    ScenarioTaskF,
    InputLayerF
)


class TestScenarioAPIView(BaseAPIViewTransactionTest):

    def test_submit_valid_scenario(self):
        input_layer = InputLayerF.create(
            privacy_type=InputLayer.PrivacyTypes.COMMON
        )
        scenario_path = absolute_path(
            'cplus_api', 'tests', 'samples', 'scenario_input.json'
        )
        data = {}
        with open(scenario_path, 'r') as f:
            data = json.load(f)
        view = ScenarioAnalysisSubmit.as_view()
        # invalid UUID
        data['implementation_models'][0]['pathways'][0]['layer_uuid'] = (
            'aedf5106'
        )
        request = self.factory.post(
            reverse('v1:scenario-submit'), data, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.user_1
        response = view(request)
        self.assertEqual(response.status_code, 400)
        # InputLayer object does not exist
        data['implementation_models'][0]['pathways'][0]['layer_uuid'] = (
            '5fe775ba-0e80-4b70-a53a-1ed874b72da3'
        )
        request = self.factory.post(
            reverse('v1:scenario-submit'), data, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.user_1
        response = view(request)
        self.assertEqual(response.status_code, 400)
        # missing file in the storage
        data['implementation_models'][0]['pathways'][0]['layer_uuid'] = (
            str(input_layer.uuid)
        )
        request = self.factory.post(
            reverse('v1:scenario-submit'), data, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.user_1
        response = view(request)
        self.assertEqual(response.status_code, 400)
        # valid scenario
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        self.store_input_layer_file(input_layer, file_path)
        request = self.factory.post(
            reverse('v1:scenario-submit'), data, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.user_1
        response = view(request)
        self.assertEqual(response.status_code, 201)
        scenario_uuid = response.data['uuid']
        scenario_task = ScenarioTask.objects.filter(
            uuid=scenario_uuid).first()
        self.assertTrue(scenario_task)
        self.assertEqual(scenario_task.detail['scenario_name'],
                         data['scenario_name'])
        self.assertEqual(scenario_task.api_version, 'v1')

    @mock.patch('cplus_api.tasks.runner.'
                'run_scenario_analysis_task.apply_async')
    def test_execute_scenario(self, mocked_task):
        mocked_task.side_effect = mocked_process
        scenario_task = ScenarioTaskF.create(
            submitted_by=self.superuser
        )
        kwargs = {
            'scenario_uuid': str(scenario_task.uuid)
        }
        request = self.factory.get(
            reverse('v1:scenario-execute', kwargs=kwargs)
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        view = ExecuteScenarioAnalysis.as_view()
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['uuid'], str(scenario_task.uuid))
        self.assertEqual(response.data['task_id'], '1')
        mocked_task.assert_called_once()
        # invalid user
        mocked_task.reset_mock()
        request = self.factory.get(
            reverse('v1:scenario-execute', kwargs=kwargs)
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.user_1
        view = ExecuteScenarioAnalysis.as_view()
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 403)
        mocked_task.assert_not_called()
        # invalid status
        scenario_task.status = TaskStatus.QUEUED
        scenario_task.save()
        mocked_task.reset_mock()
        request = self.factory.get(
            reverse('v1:scenario-execute', kwargs=kwargs)
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        view = ExecuteScenarioAnalysis.as_view()
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 400)
        mocked_task.assert_not_called()
