import uuid
from django.urls import reverse
from core.models.base_task_request import TaskStatus
from core.settings.utils import absolute_path
from cplus_api.api_views.output import (
    UserScenarioAnalysisOutput,
    FetchScenarioAnalysisOutput
)
from cplus_api.tests.common import (
    FakeResolverMatchV1,
    BaseAPIViewTransactionTest
)
from cplus_api.tests.factories import (
    ScenarioTaskF,
    OutputLayerF
)


class TestOutputAPIView(BaseAPIViewTransactionTest):

    def filter_layers_having_urls(self, layers):
        return [
            layer for layer in layers if
            'url' in layer and layer['url']
        ]

    def test_fetch_output_list(self):
        file_path = absolute_path(
            'cplus_api', 'tests', 'data',
            'models', 'test_model_1.tif'
        )
        view = UserScenarioAnalysisOutput.as_view()
        scenario_task = ScenarioTaskF.create(
            submitted_by=self.superuser,
            status=TaskStatus.PENDING
        )
        kwargs = {
            'scenario_uuid': str(scenario_task.uuid)
        }
        # test invalid page
        page = 200
        request = self.factory.get(
            reverse(
                'v1:scenario-output-list',
                kwargs=kwargs
            ) + f'?page={page}'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 0)
        # add final output
        output_layer_1 = OutputLayerF.create(
            scenario=scenario_task,
            owner=scenario_task.submitted_by,
            is_final_output=True
        )
        self.store_layer_file(output_layer_1, file_path)
        # add weighted_ims
        output_layer_2 = OutputLayerF.create(
            scenario=scenario_task,
            owner=scenario_task.submitted_by,
            is_final_output=False,
            group='weighted_ims'
        )
        self.store_layer_file(output_layer_2, file_path)
        # add activities
        output_layer_3 = OutputLayerF.create(
            scenario=scenario_task,
            owner=scenario_task.submitted_by,
            is_final_output=False,
            group='activities'
        )
        self.store_layer_file(output_layer_3, file_path)
        # add weighted_ims with empty output file
        OutputLayerF.create(
            scenario=scenario_task,
            owner=scenario_task.submitted_by,
            is_final_output=False,
            group='weighted_ims'
        )
        # add weighted_ims with file does not exist
        output_layer_5 = OutputLayerF.create(
            scenario=scenario_task,
            owner=scenario_task.submitted_by,
            is_final_output=False,
            group='weighted_ims'
        )
        output_layer_5.file.name = (
            'common_layers/ncs_pathway/test_model_2_123.tif'
        )
        output_layer_5.save()
        # test success, should return 5 items
        request = self.factory.get(
            reverse('v1:scenario-output-list', kwargs=kwargs)
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 5)
        # 2 items should have url, 3 items should not have
        filtered_layers = self.filter_layers_having_urls(
            response.data['results'])
        self.assertEqual(len(filtered_layers), 2)
        find_layer = self.find_layer_from_response(
            filtered_layers, output_layer_1.uuid)
        self.assertTrue(find_layer)
        find_layer = self.find_layer_from_response(
            filtered_layers, output_layer_2.uuid)
        self.assertTrue(find_layer)
        # test with download_all, should return 5 items
        # 3 items should have url
        request = self.factory.get(
            reverse(
                'v1:scenario-output-list',
                kwargs=kwargs
            ) + '?download_all=true'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 5)
        filtered_layers = self.filter_layers_having_urls(
            response.data['results'])
        self.assertEqual(len(filtered_layers), 3)
        find_layer = self.find_layer_from_response(
            filtered_layers, output_layer_1.uuid)
        self.assertTrue(find_layer)
        find_layer = self.find_layer_from_response(
            filtered_layers, output_layer_2.uuid)
        self.assertTrue(find_layer)
        find_layer = self.find_layer_from_response(
            filtered_layers, output_layer_3.uuid)
        self.assertTrue(find_layer)
        # filter by group
        request = self.factory.get(
            reverse(
                'v1:scenario-output-list',
                kwargs=kwargs
            ) + '?download_all=true&group=activities'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
        find_layer = self.find_layer_from_response(
            filtered_layers, output_layer_3.uuid)
        self.assertTrue(find_layer)
        self.assertTrue(find_layer['url'])

    def test_fetch_output_by_uuid(self):
        view = FetchScenarioAnalysisOutput.as_view()
        scenario_task = ScenarioTaskF.create(
            submitted_by=self.superuser,
            status=TaskStatus.PENDING
        )
        kwargs = {
            'scenario_uuid': str(scenario_task.uuid)
        }
        output_layer = OutputLayerF.create(
            scenario=scenario_task,
            owner=scenario_task.submitted_by,
            is_final_output=True
        )
        data = [
            str(output_layer.uuid),
            str(uuid.uuid4())
        ]
        # should return 1 item
        request = self.factory.post(
            reverse('v1:scenario-output-list-by-uuids', kwargs=kwargs),
            data=data, format='json'
        )
        request.resolver_match = FakeResolverMatchV1
        request.user = self.superuser
        response = view(request, **kwargs)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        find_layer = self.find_layer_from_response(
            response.data, output_layer.uuid)
        self.assertTrue(find_layer)
        self.assertFalse(find_layer['url'])
