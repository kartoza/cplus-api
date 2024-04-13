import os
import mock
from django.urls import reverse
from core.models.base_task_request import TaskStatus
from core.settings.utils import absolute_path
from cplus_api.api_views.scenario import (
    ScenarioAnalysisSubmit,
    ExecuteScenarioAnalysis
)
from cplus_api.models.scenario import ScenarioTask
from cplus_api.tests.common import (
    FakeResolverMatchV1,
    BaseAPIViewTransactionTest,
    mocked_process
)
from cplus_api.tests.factories import ScenarioTaskF


class TestScenarioAPIView(BaseAPIViewTransactionTest):

    def test_submit_valid_scenario(self):
        pass

    def test_submit_scenario_non_exist_layer(self):
        pass

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
