
import logging
import io
import time
import zipfile
from unittest import TestCase
from unittest import mock, skip

from flask import url_for

from pfcon.app import create_app
from pfcon.services import PmanService, PfiohService


class ResourceTests(TestCase):
    """
    Base class for all the resource tests.
    """
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.app = create_app({
            'TESTING': True,
        })
        self.client = self.app.test_client()

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class TestJobList(ResourceTests):
    """
    Test the JobList resource.
    """
    def setUp(self):
        super().setUp()
        with self.app.test_request_context():
            self.url = url_for('api.joblist')

    def test_get(self):
        response = self.client.get(self.url)
        self.assertTrue('server_version' in response.json)

    def test_post(self):
        job_id = 'chris-jid-1'

        # create zip data file
        memory_zip_file = io.BytesIO()
        with zipfile.ZipFile(memory_zip_file, 'w', zipfile.ZIP_DEFLATED) as job_data_zip:
            job_data_zip.writestr('data.txt', 'test data')
        memory_zip_file.seek(0)

        data = {
            'jid': job_id,
            'cmd_args': '--saveinputmeta --saveoutputmeta --dir /share/incoming',
            'auid': 'cube',
            'number_of_workers': '1',
            'cpu_limit': '1000',
            'memory_limit': '200',
            'gpu_limit': '0',
            'image': 'fnndsc/pl-simplefsapp',
            'selfexec': 'simplefsapp.py',
            'selfpath': '/usr/src/simplefsapp',
            'execshell': 'python3',
            'type': 'fs',
            'data_file': (memory_zip_file, 'data.txt.zip')
        }
        # make the POST request
        response = self.client.post(self.url,
                                    data=data,
                                    content_type='multipart/form-data')
        self.assertIn('compute', response.json)
        self.assertIn('pushData', response.json)

        time.sleep(3)
        with self.app.test_request_context():
            # cleanup swarm job
            pman = PmanService.get_service_obj()
            d_compute_response = pman.get_job(job_id)
            self.assertTrue(d_compute_response['status'])

            # cleanup data from pfioh
            pfioh = PfiohService.get_service_obj()
            pfioh.pull_data(job_id)


class TestJob(ResourceTests):
    """
    Test the JobList resource.
    """
    def setUp(self):
        super().setUp()
        with self.app.test_request_context():
            self.url = url_for('api.job', job_id='chris-jid-2')

    def test_get(self):
        job_id = 'chris-jid-2'

        # create zip data file
        memory_zip_file = io.BytesIO()
        with zipfile.ZipFile(memory_zip_file, 'w', zipfile.ZIP_DEFLATED) as job_data_zip:
            job_data_zip.writestr('data.txt', 'test data')
        memory_zip_file.seek(0)
        memory_zip_file.filename = 'data.txt.zip'

        compute_data = {
            'cmd_args': '--saveinputmeta --saveoutputmeta path:--dir cube',
            'auid': 'cube',
            'number_of_workers': '1',
            'cpu_limit': '1000',
            'memory_limit': '200',
            'gpu_limit': '0',
            'image': 'fnndsc/pl-simplefsapp',
            'selfexec': 'simplefsapp.py',
            'selfpath': '/usr/src/simplefsapp',
            'execshell': 'python3',
            'type': 'fs'
        }

        with self.app.test_request_context():
            # create job
            pfioh = PfiohService.get_service_obj()
            d_data_push_response = pfioh.push_data(job_id, memory_zip_file)
            self.assertTrue(d_data_push_response['status'])
            pman = PmanService.get_service_obj()
            data_share_dir = d_data_push_response['postop']['shareDir']
            d_compute_response = pman.run_job(job_id, compute_data, data_share_dir)
            self.assertTrue(d_compute_response['status'])

            time.sleep(3)
            # make the GET request
            response = self.client.get(self.url)
            self.assertIn('compute', response.json)
            self.assertTrue(response.json['compute']['status'])

            # cleanup data from pfioh
            pfioh = PfiohService.get_service_obj()
            pfioh.pull_data(job_id)
