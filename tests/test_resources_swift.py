"""
Integration tests for the new client-managed job resources in swift mode.
Requires a running Docker daemon and Swift service.

Tests the full lifecycle:
  POST /copyjobs/    -> schedule copy container (fetches from Swift)
  GET  /copyjobs/id/ -> poll copy status until finished
  POST /pluginjobs/  -> schedule plugin container
  GET  /pluginjobs/id/ -> poll plugin status until finished
  GET  /pluginjobs/id/file/ -> retrieve output metadata
  POST /uploadjobs/  -> schedule upload container (pushes to Swift)
  GET  /uploadjobs/id/ -> poll upload status until finished
  POST /deletejobs/  -> schedule delete container
  GET  /deletejobs/id/ -> poll delete status until finished
  DELETE /copyjobs/id/, /pluginjobs/id/, /uploadjobs/id/, /deletejobs/id/
"""

import io
import logging
import os
import shutil
import time
import json
from unittest import TestCase

from flask import url_for

from pfcon.app import create_app
from pfcon.compute.container_user import ContainerUser
from pfcon.compute.abstractmgr import ManagerException
from pfcon.base_resources import get_compute_mgr
from pfcon.storage.swiftmanager import SwiftManager


class NewResourcesSwiftTests(TestCase):
    """Base class for the new resources integration tests in swift mode."""

    def setUp(self):
        logging.disable(logging.WARNING)

        self.app = create_app({
            'PFCON_INNETWORK': True,
            'STORAGE_ENV': 'swift',
            'SWIFT_CONTAINER_NAME': 'users',
            'SWIFT_CONNECTION_PARAMS': {
                'user': 'chris:chris1234',
                'key': 'testing',
                'authurl': 'http://swift_service:8080/auth/v1.0',
            },
        })
        self.client = self.app.test_client()

        with self.app.test_request_context():
            url = url_for('api.auth')
            creds = {
                'pfcon_user': self.app.config.get('PFCON_USER'),
                'pfcon_password': self.app.config.get('PFCON_PASSWORD'),
            }
            response = self.client.post(url, data=json.dumps(creds),
                                        content_type='application/json')
            self.headers = {'Authorization': 'Bearer ' + response.json['token']}

            self.storebase_mount = self.app.config.get('STOREBASE_MOUNT')
            self.storebase = self.app.config.get('STOREBASE')
            self.container_env = self.app.config.get('CONTAINER_ENV')
            self.user = ContainerUser.parse(
                self.app.config.get('CONTAINER_USER'))

            self.swift_manager = SwiftManager(
                self.app.config.get('SWIFT_CONTAINER_NAME'),
                self.app.config.get('SWIFT_CONNECTION_PARAMS'))

            self.swift_input_path = 'foo/feed/input'
            self.swift_output_path = 'foo/feed/output'

            # Upload a test file to Swift input path
            with io.StringIO('Test file') as f:
                self.swift_manager.upload_obj(
                    self.swift_input_path + '/test.txt',
                    f.read(), content_type='text/plain')

    def tearDown(self):
        # Clean up Swift objects
        for prefix in (self.swift_input_path, self.swift_output_path):
            for obj_path in self.swift_manager.ls(prefix):
                self.swift_manager.delete_obj(obj_path)

        logging.disable(logging.NOTSET)

    def _remove_container(self, name):
        with self.app.test_request_context():
            compute_mgr = get_compute_mgr(self.container_env)
            try:
                job = compute_mgr.get_job(name)
                compute_mgr.remove_job(job)
            except ManagerException:
                pass


class TestFullLifecycleSwift(NewResourcesSwiftTests):
    """Full end-to-end test of the new client-managed job flow with Swift."""

    def test_full_lifecycle(self):
        job_id = 'new-swift-e2e-1'

        try:
            # 1. Schedule copy job
            with self.app.test_request_context():
                copy_list_url = url_for('api.copyjoblist')
                copy_url = url_for('api.copyjob', job_id=job_id)

            copy_data = {
                'jid': job_id,
                'input_dirs': [self.swift_input_path],
                'output_dir': self.swift_output_path,
            }
            response = self.client.post(copy_list_url, data=copy_data,
                                        headers=self.headers)
            self.assertEqual(response.status_code, 201)

            # 2. Poll copy until finished
            for _ in range(30):
                time.sleep(3)
                response = self.client.get(copy_url, headers=self.headers)
                status = response.json['compute']['status']
                if status == 'finishedSuccessfully':
                    break
            self.assertEqual(response.json['compute']['status'],
                             'finishedSuccessfully')

            # Verify files were copied to storebase
            incoming = os.path.join(self.storebase_mount, 'key-' + job_id,
                                    'incoming')
            self.assertTrue(os.path.isfile(
                os.path.join(incoming, 'test.txt')))

            # 3. Schedule plugin job
            with self.app.test_request_context():
                plugin_list_url = url_for('api.pluginjoblist')
                plugin_url = url_for('api.pluginjob', job_id=job_id)

            plugin_data = {
                'jid': job_id,
                'entrypoint': ['python3', '/usr/local/bin/simplefsapp'],
                'args': ['--dir', '/share/incoming'],
                'auid': 'cube',
                'number_of_workers': '1',
                'cpu_limit': '1000',
                'memory_limit': '200',
                'gpu_limit': '0',
                'image': 'fnndsc/pl-simplefsapp',
                'type': 'fs',
                'input_dirs': [self.swift_input_path],
                'output_dir': self.swift_output_path,
            }
            response = self.client.post(plugin_list_url, data=plugin_data,
                                        headers=self.headers)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json['data'], {})

            # 4. Poll plugin until finished
            for _ in range(30):
                time.sleep(3)
                response = self.client.get(plugin_url, headers=self.headers)
                status = response.json['compute']['status']
                if status == 'finishedSuccessfully':
                    break
            self.assertEqual(response.json['compute']['status'],
                             'finishedSuccessfully')

            # 5. Get output file metadata
            with self.app.test_request_context():
                file_url = url_for('api.pluginjobfile', job_id=job_id)

            response = self.client.get(
                file_url,
                query_string={'job_output_path': self.swift_output_path},
                headers=self.headers)
            self.assertEqual(response.status_code, 200)
            content = json.loads(response.data.decode())
            self.assertEqual(content['job_output_path'],
                             self.swift_output_path)
            self.assertIsInstance(content['rel_file_paths'], list)
            self.assertGreater(len(content['rel_file_paths']), 0)

            # 6. Schedule upload job
            with self.app.test_request_context():
                upload_list_url = url_for('api.uploadjoblist')
                upload_url = url_for('api.uploadjob', job_id=job_id)

            upload_data = {
                'jid': job_id,
                'job_output_path': self.swift_output_path,
            }
            response = self.client.post(upload_list_url, data=upload_data,
                                        headers=self.headers)
            self.assertEqual(response.status_code, 201)

            # 7. Poll upload until finished
            for _ in range(30):
                time.sleep(3)
                response = self.client.get(upload_url, headers=self.headers)
                status = response.json['compute']['status']
                if status == 'finishedSuccessfully':
                    break
            self.assertEqual(response.json['compute']['status'],
                             'finishedSuccessfully')

            # Verify files were uploaded to Swift
            swift_files = list(self.swift_manager.ls(self.swift_output_path))
            self.assertGreater(len(swift_files), 0,
                               'Files should be uploaded to Swift')

            # 8. Schedule delete job
            with self.app.test_request_context():
                delete_list_url = url_for('api.deletejoblist')
                delete_url = url_for('api.deletejob', job_id=job_id)

            delete_data = {'jid': job_id}
            response = self.client.post(delete_list_url, data=delete_data,
                                        headers=self.headers)
            self.assertEqual(response.status_code, 201)

            # 9. Poll delete until finished
            for _ in range(30):
                time.sleep(3)
                response = self.client.get(delete_url, headers=self.headers)
                status = response.json['compute']['status']
                if status == 'finishedSuccessfully':
                    break
            self.assertEqual(response.json['compute']['status'],
                             'finishedSuccessfully')

            # Verify storebase data was deleted
            key_dir = os.path.join(self.storebase_mount, 'key-' + job_id)
            incoming = os.path.join(key_dir, 'incoming')
            self.assertFalse(os.path.isdir(incoming))

            # 10. Delete all containers
            response = self.client.delete(copy_url, headers=self.headers)
            self.assertEqual(response.status_code, 204)

            response = self.client.delete(plugin_url, headers=self.headers)
            self.assertEqual(response.status_code, 204)

            response = self.client.delete(upload_url, headers=self.headers)
            self.assertEqual(response.status_code, 204)

            response = self.client.delete(delete_url, headers=self.headers)
            self.assertEqual(response.status_code, 204)

        except Exception:
            # Force-cleanup on failure
            for suffix in ('-copy', '', '-upload', '-delete'):
                self._remove_container(job_id + suffix)
            key_dir = os.path.join(self.storebase_mount, 'key-' + job_id)
            if os.path.isdir(key_dir):
                shutil.rmtree(key_dir)
            raise

    def test_copy_with_chris_links(self):
        """Copy job should recursively follow .chrislink files from Swift."""
        job_id = 'new-swift-links-1'

        # Set up ChRIS link structure in Swift
        with io.StringIO('Test pipeline') as f:
            self.swift_manager.upload_obj(
                'PIPELINES/bob/pipeline.yml',
                f.read(), content_type='text/plain')
        with io.StringIO('PIPELINES/bob') as f:
            self.swift_manager.upload_obj(
                'home/bob/PIPELINES_bob.chrislink',
                f.read(), content_type='text/plain')
        with io.StringIO('home/bob') as f:
            self.swift_manager.upload_obj(
                self.swift_input_path + '/home_bob.chrislink',
                f.read(), content_type='text/plain')

        try:
            with self.app.test_request_context():
                copy_list_url = url_for('api.copyjoblist')
                copy_url = url_for('api.copyjob', job_id=job_id)

            copy_data = {
                'jid': job_id,
                'input_dirs': [self.swift_input_path],
                'output_dir': self.swift_output_path,
            }
            response = self.client.post(copy_list_url, data=copy_data,
                                        headers=self.headers)
            self.assertEqual(response.status_code, 201)

            for _ in range(30):
                time.sleep(3)
                response = self.client.get(copy_url, headers=self.headers)
                status = response.json['compute']['status']
                if status == 'finishedSuccessfully':
                    break

            self.assertEqual(response.json['compute']['status'],
                             'finishedSuccessfully')

            # Verify ChRIS links were followed
            incoming = os.path.join(self.storebase_mount, 'key-' + job_id,
                                    'incoming')
            self.assertTrue(os.path.isfile(
                os.path.join(incoming, 'home_bob', 'PIPELINES_bob',
                             'pipeline.yml')))

        finally:
            self._remove_container(job_id + '-copy')
            key_dir = os.path.join(self.storebase_mount, 'key-' + job_id)
            if os.path.isdir(key_dir):
                shutil.rmtree(key_dir)
            # Clean up extra Swift objects
            for prefix in ('PIPELINES/bob', 'home/bob'):
                for obj_path in self.swift_manager.ls(prefix):
                    self.swift_manager.delete_obj(obj_path)


class TestUploadIdempotencySwift(NewResourcesSwiftTests):
    """Test upload idempotency with real Swift."""

    def test_upload_idempotent_no_duplicate(self):
        """Calling POST /uploadjobs/ twice should not schedule a second
        container if the first one is still running or succeeded."""
        job_id = 'new-swift-idemp-1'
        key_dir = os.path.join(self.storebase_mount, 'key-' + job_id)

        try:
            # Run copy + plugin first so the plugin guard passes
            with self.app.test_request_context():
                copy_list_url = url_for('api.copyjoblist')
                copy_url = url_for('api.copyjob', job_id=job_id)
                plugin_list_url = url_for('api.pluginjoblist')
                plugin_url = url_for('api.pluginjob', job_id=job_id)
                upload_list_url = url_for('api.uploadjoblist')
                upload_url = url_for('api.uploadjob', job_id=job_id)

            copy_data = {
                'jid': job_id,
                'input_dirs': [self.swift_input_path],
                'output_dir': self.swift_output_path,
            }
            response = self.client.post(copy_list_url, data=copy_data,
                                        headers=self.headers)
            self.assertEqual(response.status_code, 201)

            for _ in range(30):
                time.sleep(3)
                response = self.client.get(copy_url, headers=self.headers)
                if response.json['compute']['status'] == 'finishedSuccessfully':
                    break
            self.assertEqual(response.json['compute']['status'],
                             'finishedSuccessfully')

            plugin_data = {
                'jid': job_id,
                'entrypoint': ['python3', '/usr/local/bin/simplefsapp'],
                'args': ['--dir', '/share/incoming'],
                'auid': 'cube',
                'number_of_workers': '1',
                'cpu_limit': '1000',
                'memory_limit': '200',
                'gpu_limit': '0',
                'image': 'fnndsc/pl-simplefsapp',
                'type': 'fs',
                'input_dirs': [self.swift_input_path],
                'output_dir': self.swift_output_path,
            }
            response = self.client.post(plugin_list_url, data=plugin_data,
                                        headers=self.headers)
            self.assertEqual(response.status_code, 201)

            for _ in range(30):
                time.sleep(3)
                response = self.client.get(plugin_url, headers=self.headers)
                if response.json['compute']['status'] == 'finishedSuccessfully':
                    break
            self.assertEqual(response.json['compute']['status'],
                             'finishedSuccessfully')

            # Now test upload idempotency
            upload_data = {
                'jid': job_id,
                'job_output_path': self.swift_output_path,
            }

            # First POST — schedules the upload container
            response1 = self.client.post(upload_list_url, data=upload_data,
                                         headers=self.headers)
            self.assertEqual(response1.status_code, 201)

            # Second POST — should return the existing container's status
            response2 = self.client.post(upload_list_url, data=upload_data,
                                         headers=self.headers)
            self.assertEqual(response2.status_code, 201)

            # Poll until upload finishes
            for _ in range(30):
                time.sleep(3)
                response = self.client.get(upload_url, headers=self.headers)
                status = response.json['compute']['status']
                if status == 'finishedSuccessfully':
                    break
            self.assertEqual(response.json['compute']['status'],
                             'finishedSuccessfully')

            # Verify files were uploaded to Swift
            swift_files = list(self.swift_manager.ls(self.swift_output_path))
            self.assertGreater(len(swift_files), 0,
                               'Files should be uploaded to Swift')

        finally:
            for suffix in ('-copy', '', '-upload'):
                self._remove_container(job_id + suffix)
            if os.path.isdir(key_dir):
                shutil.rmtree(key_dir)


class TestCopyJobListSwift(NewResourcesSwiftTests):
    """Test CopyJobList resource with swift."""

    def test_get_returns_server_info(self):
        with self.app.test_request_context():
            url = url_for('api.copyjoblist')
        response = self.client.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['pfcon_innetwork'])
        self.assertEqual(response.json['storage_env'], 'swift')
        self.assertIn('swift_auth_url', response.json)


class TestPluginJobListSwift(NewResourcesSwiftTests):
    """Test PluginJobList resource with swift."""

    def test_get_returns_server_info(self):
        with self.app.test_request_context():
            url = url_for('api.pluginjoblist')
        response = self.client.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['pfcon_innetwork'])
        self.assertEqual(response.json['storage_env'], 'swift')


class TestDeleteJobNoDataSwift(NewResourcesSwiftTests):
    """Test DeleteJob when no data directory exists."""

    def test_post_noop_when_no_key_dir(self):
        with self.app.test_request_context():
            url = url_for('api.deletejoblist')
        data = {'jid': 'nonexistent-job'}
        response = self.client.post(url, data=data, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['compute']['status'],
                         'finishedSuccessfully')
        self.assertEqual(response.json['compute']['message'],
                         'deleteSkipped')
