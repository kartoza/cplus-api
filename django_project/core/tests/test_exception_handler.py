from django.test import TestCase
from rest_framework.exceptions import (
    APIException,
    MethodNotAllowed
)
from django.core.exceptions import (
    ValidationError
)
from django.db.utils import (
    ProgrammingError
)
from core.tools.custom_exception_handler import custom_exception_handler


class CustomException(Exception):

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class TestExceptionHandler(TestCase):

    def test_internal_server_error(self):
        exc = APIException(detail='error_test')
        response = custom_exception_handler(exc, None)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'error_test')

    def test_validation_error(self):
        exc = ValidationError(message='error_test')
        response = custom_exception_handler(exc, None)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], str(['error_test']))

    def test_programming_error(self):
        exc = ProgrammingError('error_test')
        response = custom_exception_handler(exc, None)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'error_test')

    def test_custom_exception(self):
        exc = CustomException('error_test')
        response = custom_exception_handler(exc, None)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'error_test')

    def test_other_error(self):
        exc = MethodNotAllowed(method='get', detail='error_test')
        response = custom_exception_handler(exc, None)
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.data['detail'], 'error_test')
