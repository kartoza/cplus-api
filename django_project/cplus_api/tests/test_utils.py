import uuid
import json
import datetime
from unittest.mock import patch
from django.test import TestCase
from django.core.mail import send_mail
from django.conf import settings
from cplus_api.utils.api_helper import (
    todict,
    CustomJsonEncoder,
    get_layer_type
)


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

    def test_get_layer_type(self):
        filepath = '/tmp/test/file.tif'
        self.assertEqual(get_layer_type(filepath), 0)

        filepath = '/tmp/test/file.zip'
        self.assertEqual(get_layer_type(filepath), 1)

        filepath = '/tmp/test/file.shp'
        self.assertEqual(get_layer_type(filepath), 1)

        filepath = '/tmp/test/file.netcdf'
        self.assertEqual(get_layer_type(filepath), -1)

    def test_email_send(self):
        """Test email send when scenario is finished."""
        self.recipients = []
        parent = self

        def mock_send_fn(self, fail_silently=False):
            """Mock send messages."""
            parent.recipients = self.recipients()
            return 0

        with patch(
                "django.core.mail.EmailMessage.send", mock_send_fn
        ):
            send_mail(
                "Test",
                None,
                settings.DEFAULT_FROM_EMAIL,
                ['email_1@domain.com', 'email_2@domain.com'],
                html_message="Test message"
            )
            parent.assertEqual(len(self.recipients), 2)
            parent.assertEqual(
                self.recipients,
                ['email_1@domain.com', 'email_2@domain.com']
            )


class TestCustomJSONEncoder(TestCase):
    def test_uuid(self):
        test_obj = {
            'uuid': uuid.uuid4()
        }
        try:
            json.dumps(test_obj)
        except TypeError:
            try:
                json.dumps(test_obj, cls=CustomJsonEncoder)
            except TypeError:
                self.fail('TypeError raised')

    def test_datetime(self):
        test_obj = {
            'datetime': datetime.datetime(2024, 5, 13, 1, 1, 1, 0)
        }
        try:
            json.dumps(test_obj)
        except TypeError:
            try:
                json.dumps(test_obj, cls=CustomJsonEncoder)
            except TypeError:
                self.fail('TypeError raised')

    def test_other_type(self):
        test_obj = {
            'name': 'name'
        }
        try:
            json.dumps(test_obj)
        except TypeError:
            self.fail('TypeError raised')
