
import logging
from pathlib import Path
import shutil
import os
import io
import time
import zipfile
import json
from unittest import TestCase
from unittest import mock, skip

from flask import url_for

from pfcon.app import create_app
from pfcon.services import PmanService, ServiceException


class ResourceTests(TestCase):
    """
    Base class for all the resource tests.
    """
    def setUp(self):
        # avoid cluttered console output (for instance logging all the http requests)
        logging.disable(logging.WARNING)

        self.app = create_app()
        self.client = self.app.test_client()
        with self.app.test_request_context():
            # create a header with authorization token
            url = url_for('api.auth')
            creds = {
                'pfcon_user': self.app.config.get('PFCON_USER'),
                'pfcon_password': self.app.config.get('PFCON_PASSWORD')
            }
            response = self.client.post(url, data=json.dumps(creds), content_type='application/json')
            self.headers = {'Authorization': 'Bearer ' + response.json['token']}

    def tearDown(self):
        # re-enable logging
        logging.disable(logging.NOTSET)


class TestJobList(ResourceTests):
    """
    Test the JobList resource.
    """
    def setUp(self):
        super().setUp()

        self.job_dir = ''
        with self.app.test_request_context():
            self.url = url_for('api.joblist')

    def tearDown(self):
        if os.path.isdir(self.job_dir):
            shutil.rmtree(self.job_dir)
        super().tearDown()

    def test_get(self):
        response = self.client.get(self.url, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('server_version' in response.json)

    def test_post(self):
        job_id = 'chris-jid-1'
        self.job_dir = os.path.join('/var/local/storeBase', 'key-' + job_id)
        # create zip data file
        memory_zip_file = io.BytesIO()
        with zipfile.ZipFile(memory_zip_file, 'w', zipfile.ZIP_DEFLATED) as job_data_zip:
            job_data_zip.writestr('data.txt', 'test data')
        memory_zip_file.seek(0)

        data = {
            'jid': job_id,
            'entrypoint': ['python3', '/usr/local/bin/simplefsapp'],
            'args': ['--saveinputmeta', '--saveoutputmeta', '--dir', '/share/incoming'],
            'auid': 'cube',
            'number_of_workers': '1',
            'cpu_limit': '1000',
            'memory_limit': '200',
            'gpu_limit': '0',
            'image': 'fnndsc/pl-simplefsapp',
            'type': 'fs',
            'data_file': (memory_zip_file, 'data.txt.zip')
        }
        # make the POST request
        response = self.client.post(self.url, data=data, headers=self.headers,
                                    content_type='multipart/form-data')
        self.assertEqual(response.status_code, 201)
        self.assertIn('compute', response.json)
        self.assertIn('data', response.json)
        self.assertEqual(response.json['data']['nfiles'], 1)

        with self.app.test_request_context():
            pman = PmanService.get_service_obj()
            for _ in range(10):
                time.sleep(3)
                d_compute_response = pman.get_job(job_id)
                if d_compute_response['status'] == 'finishedSuccessfully': break
            self.assertEqual(d_compute_response['status'], 'finishedSuccessfully')

            # cleanup swarm job
            pman.delete_job(job_id)


class TestJob(ResourceTests):
    """
    Test the Job resource.
    """
    def setUp(self):
        super().setUp()

        self.job_dir = ''
        self.compute_data = {
            'entrypoint': ['python3', '/usr/local/bin/simplefsapp'],
            'args': ['--saveinputmeta', '--saveoutputmeta', '--dir', 'cube'],
            'args_path_flags': ['--dir'],
            'auid': 'cube',
            'number_of_workers': '1',
            'cpu_limit': '1000',
            'memory_limit': '200',
            'gpu_limit': '0',
            'image': 'fnndsc/pl-simplefsapp',
            'type': 'fs'
        }

    def tearDown(self):
        if os.path.isdir(self.job_dir):
            shutil.rmtree(self.job_dir)
        super().tearDown()

    def test_get(self):
        job_id = 'chris-jid-2'
        self.job_dir = os.path.join('/var/local/storeBase', 'key-' + job_id)
        incoming = os.path.join(self.job_dir, 'incoming')
        Path(incoming).mkdir(parents=True, exist_ok=True)
        outgoing = os.path.join(self.job_dir, 'outgoing')
        Path(outgoing).mkdir(parents=True, exist_ok=True)
        with open(os.path.join(incoming, 'test.txt'), 'w') as f:
            f.write('job input test file')

        with self.app.test_request_context():
            # create job
            url = url_for('api.job', job_id=job_id)
            pman = PmanService.get_service_obj()
            pman.run_job(job_id, self.compute_data)

            # make the GET requests
            for _ in range(10):
                time.sleep(3)
                response = self.client.get(url, headers=self.headers)
                if response.json['compute']['status'] == 'finishedSuccessfully': break
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json['compute']['status'], 'finishedSuccessfully')

            # cleanup swarm job
            pman.delete_job(job_id)

    def test_delete(self):
        job_id = 'chris-jid-3'
        self.job_dir = os.path.join('/var/local/storeBase', 'key-' + job_id)
        incoming = os.path.join(self.job_dir, 'incoming')
        Path(incoming).mkdir(parents=True, exist_ok=True)
        outgoing = os.path.join(self.job_dir, 'outgoing')
        Path(outgoing).mkdir(parents=True, exist_ok=True)
        with open(os.path.join(incoming, 'test.txt'), 'w') as f:
            f.write('job input test file')

        with self.app.test_request_context():
            # create job
            url = url_for('api.job', job_id=job_id)
            pman = PmanService.get_service_obj()
            pman.run_job(job_id, self.compute_data)

        # make the DELETE request
        time.sleep(3)
        response = self.client.delete(url, headers=self.headers)
        self.assertEqual(response.status_code, 204)


class TestJobFile(ResourceTests):
    """
    Test the JobFile resource.
    """
    def setUp(self):
        super().setUp()

        self.job_dir = ''

    def tearDown(self):
        if os.path.isdir(self.job_dir):
            shutil.rmtree(self.job_dir)
        super().tearDown()

    def test_get(self):
        job_id = 'chris-jid-4'
        self.job_dir = os.path.join('/var/local/storeBase', 'key-' + job_id)
        with self.app.test_request_context():
            url = url_for('api.jobfile', job_id=job_id)
        outgoing = os.path.join(self.job_dir, 'outgoing')
        Path(outgoing).mkdir(parents=True, exist_ok=True)
        with open(os.path.join(outgoing, 'test.txt'), 'w') as f:
            f.write('job input test file')
        response = self.client.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        memory_zip_file = io.BytesIO(response.data)
        with zipfile.ZipFile(memory_zip_file, 'r', zipfile.ZIP_DEFLATED) as job_zip:
            filenames = job_zip.namelist()
        self.assertEqual(len(filenames), 1)
        self.assertEqual(filenames[0], 'test.txt')
