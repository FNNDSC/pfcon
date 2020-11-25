
from unittest import TestCase

from pfcon.app import create_app


class ResourceTests(TestCase):
    """
    Base class for all the resource tests.
    """
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        app = create_app({
            'TESTING': True,
        })
        self.client = app.test_client()


class TestJobList(ResourceTests):
    """
    Test the JobList resource.
    """
    def test_get(self):
        response = self.client.get('/api/v1/')
        self.assertTrue('server_version' in response.json)
