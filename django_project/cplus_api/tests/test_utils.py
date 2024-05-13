from django.test import TestCase

from cplus_api.utils.api_helper import todict


class SampleObj:
    def __init__(self, name, value):
        self.name = name
        self.value = value


class TestUtils(TestCase):
    def test_dict(self):
        test_obj = {'key': 1}
        self.assertEqual(todict(test_obj), test_obj)

    def test_ast(self):
        def _ast():
            return {
                'name': 'test1',
                'value': 1
            }
        test_obj = SampleObj('test1', 1)
        test_obj._ast = _ast
        self.assertEqual(todict(test_obj), {'name': 'test1', 'value': 1})

    def test_list_dict(self):
        test_obj = [SampleObj('test1', 1), SampleObj('test2', 2)]
        expected_value = [
            {
                'name': 'test1',
                'value': 1,
                SampleObj: 'SampleObj'
            },
            {
                'name': 'test2',
                'value': 2,
                SampleObj: 'SampleObj'
            }
        ]
        self.assertEqual(todict(test_obj, SampleObj), expected_value)
