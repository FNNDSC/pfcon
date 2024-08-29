
import logging
from pathlib import Path
import shutil
import os
import time
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

        self.app = create_app({'PFCON_INNETWORK': True,
                               'STORAGE_ENV': 'fslink'
                               })
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

            self.storebase_mount = self.app.config.get('STOREBASE_MOUNT')
            self.user_dir = os.path.join(self.storebase_mount, 'home/foo')

            # copy a file to the filesystem storage input path
            self.fs_input_path = os.path.join(self.user_dir, 'feed/input')
            self.fs_output_path = os.path.join(self.user_dir, 'feed/output')
            os.makedirs(self.fs_input_path, exist_ok=True)
            os.makedirs(self.fs_output_path, exist_ok=True)
            with open(self.fs_input_path + '/test.txt', 'w') as f:
                f.write('Test file')

    def tearDown(self):
        # delete files from filesystem storage
        if os.path.isdir(self.user_dir):
            shutil.rmtree(self.user_dir)

        pipeline_dir = os.path.join(self.storebase_mount, 'PIPELINES')
        if os.path.isdir(pipeline_dir):
            shutil.rmtree(pipeline_dir)

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
        response = self.client.get(self.url, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue('server_version' in response.json)
        self.assertTrue(response.json['pfcon_innetwork'])
        self.assertEqual(response.json['storage_env'], 'fslink')

    def test_post(self):
        job_id = 'chris-jid-1'

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
            'input_dirs': [os.path.relpath(self.fs_input_path, self.storebase_mount)],
            'output_dir': os.path.relpath(self.fs_output_path, self.storebase_mount)
        }

        # make the POST request
        response = self.client.post(self.url, data=data, headers=self.headers)
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

    def test_post_with_chris_links(self):
        job_id = 'chris-jid-1'

        data = {
            'jid': job_id,
            'entrypoint': ['python3', '/usr/local/bin/simpledsapp'],
            'args': ['--saveinputmeta', '--saveoutputmeta', '--prefix', 'lo'],
            'auid': 'cube',
            'number_of_workers': '1',
            'cpu_limit': '1000',
            'memory_limit': '200',
            'gpu_limit': '0',
            'image': 'fnndsc/pl-simpledsapp',
            'type': 'ds',
            'input_dirs': [os.path.relpath(self.fs_input_path, self.storebase_mount)],
            'output_dir': os.path.relpath(self.fs_output_path, self.storebase_mount)
        }

        pipeline_dir = os.path.join(self.storebase_mount, 'PIPELINES/bob')
        os.makedirs(pipeline_dir, exist_ok=True)
        link_dir = os.path.join(self.storebase_mount, 'home/bob')
        os.makedirs(link_dir, exist_ok=True)

        with open(pipeline_dir + '/pipeline.yml', 'w') as f:
            f.write('Test pipeline')
        with open(link_dir + '/PIPELINES_bob.chrislink', 'w') as f:
            f.write('PIPELINES/bob')
        with open(self.fs_input_path + '/home_bob.chrislink', 'w') as f:
            f.write('home/bob')

        # make the POST request
        response = self.client.post(self.url, data=data, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertIn('compute', response.json)
        self.assertIn('data', response.json)
        self.assertEqual(response.json['data']['nfiles'], 2)

        with self.app.test_request_context():
            pman = PmanService.get_service_obj()
            for _ in range(10):
                time.sleep(3)
                d_compute_response = pman.get_job(job_id)
                if d_compute_response['status'] == 'finishedSuccessfully': break
            self.assertEqual(d_compute_response['status'], 'finishedSuccessfully')

            self.assertTrue(os.path.isfile(f'{self.fs_output_path}/home_bob/PIPELINES_bob/lopipeline.yml'))

            # cleanup swarm job
            pman.delete_job(job_id)


class TestJob(ResourceTests):
    """
    Test the Job resource.
    """
    def setUp(self):
        super().setUp()

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
            'type': 'fs',
            'input_dir': os.path.relpath(self.fs_input_path, self.storebase_mount),
            'output_dir': os.path.relpath(self.fs_output_path, self.storebase_mount)
        }

    def test_get(self):
        job_id = 'chris-jid-2'

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

    def test_get_without_query_parameters(self):
        job_id = 'chris-jid-4'

        with self.app.test_request_context():
            url = url_for('api.jobfile', job_id=job_id)

        response = self.client.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 400)

    def test_get_with_query_parameters(self):
        job_id = 'chris-jid-4'

        with self.app.test_request_context():
            url = url_for('api.jobfile', job_id=job_id)

        test_file_path = os.path.join(self.fs_output_path, 'out')
        Path(test_file_path).mkdir(parents=True, exist_ok=True)

        with open(os.path.join(test_file_path, 'test.txt'), 'w') as f:
            f.write('job output test file')

        job_output_path = os.path.relpath(self.fs_output_path, self.storebase_mount)
        response = self.client.get(url,
                                   query_string={'job_output_path': job_output_path},
                                   headers=self.headers)
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data.decode())
        self.assertEqual(content['job_output_path'], job_output_path)
        self.assertEqual(content['rel_file_paths'], ['out/test.txt'])
