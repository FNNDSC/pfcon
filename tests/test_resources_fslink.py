"""
Integration tests for the new client-managed job resources in fslink mode.
Requires a running Docker daemon (containers are actually scheduled).

Tests the full lifecycle:
  POST /copyjobs/    -> schedule copy container
  GET  /copyjobs/id/ -> poll copy status until finished
  POST /pluginjobs/  -> schedule plugin container
  GET  /pluginjobs/id/ -> poll plugin status until finished
  GET  /pluginjobs/id/file/ -> retrieve output metadata
  POST /deletejobs/  -> schedule delete container
  GET  /deletejobs/id/ -> poll delete status until finished
  DELETE /copyjobs/id/, /pluginjobs/id/, /deletejobs/id/ -> cleanup
"""

import logging
from pathlib import Path
import shutil
import os
import time
import json
from unittest import TestCase

from flask import url_for

from pfcon.app import create_app
from pfcon.compute.container_user import ContainerUser
from pfcon.compute.abstractmgr import ManagerException
from pfcon.base_resources import get_compute_mgr


class NewResourcesFsLinkTests(TestCase):
    """Base class for the new resources integration tests in fslink mode."""

    def setUp(self):
        logging.disable(logging.WARNING)

        self.app = create_app({'PFCON_INNETWORK': True,
                               'STORAGE_ENV': 'fslink'})
        self.client = self.app.test_client()

        with self.app.test_request_context():
            url = url_for('api.auth')
            creds = {
                'pfcon_user': self.app.config.get('PFCON_USER'),
                'pfcon_password': self.app.config.get('PFCON_PASSWORD')
            }
            response = self.client.post(url, data=json.dumps(creds),
                                        content_type='application/json')
            self.headers = {'Authorization': 'Bearer ' + response.json['token']}

            self.storebase_mount = self.app.config.get('STOREBASE_MOUNT')
            self.storebase = self.app.config.get('STOREBASE')
            self.container_env = self.app.config.get('CONTAINER_ENV')
            self.user = ContainerUser.parse(
                self.app.config.get('CONTAINER_USER'))

            self.user_dir = os.path.join(self.storebase_mount, 'home/foo')
            self.fs_input_path = os.path.join(self.user_dir, 'feed/input')
            self.fs_output_path = os.path.join(self.user_dir, 'feed/output')

            os.makedirs(self.fs_input_path, exist_ok=True)
            os.makedirs(self.fs_output_path, exist_ok=True)

            with open(self.fs_input_path + '/test.txt', 'w') as f:
                f.write('Test file')

    def tearDown(self):
        if os.path.isdir(self.user_dir):
            shutil.rmtree(self.user_dir)
        pipeline_dir = os.path.join(self.storebase_mount, 'PIPELINES')
        if os.path.isdir(pipeline_dir):
            shutil.rmtree(pipeline_dir)
        logging.disable(logging.NOTSET)

    def _remove_container(self, name):
        with self.app.test_request_context():
            compute_mgr = get_compute_mgr(self.container_env)
            try:
                job = compute_mgr.get_job(name)
                compute_mgr.remove_job(job)
            except ManagerException:
                pass


class TestFullLifecycleFsLink(NewResourcesFsLinkTests):
    """Full end-to-end test of the new client-managed job flow."""

    def test_full_lifecycle(self):
        job_id = 'new-fslink-e2e-1'
        input_rel = os.path.relpath(self.fs_input_path, self.storebase_mount)
        output_rel = os.path.relpath(self.fs_output_path, self.storebase_mount)

        try:
            # 1. Schedule copy job
            with self.app.test_request_context():
                copy_list_url = url_for('api.copyjoblist')
                copy_url = url_for('api.copyjob', job_id=job_id)

            copy_data = {
                'jid': job_id,
                'input_dirs': [input_rel],
                'output_dir': output_rel,
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

            # Verify files were copied
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
                'input_dirs': [input_rel],
                'output_dir': output_rel,
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
                query_string={'job_output_path': output_rel},
                headers=self.headers)
            self.assertEqual(response.status_code, 200)
            content = json.loads(response.data.decode())
            self.assertEqual(content['job_output_path'], output_rel)

            # 6. Schedule delete job
            with self.app.test_request_context():
                delete_list_url = url_for('api.deletejoblist')
                delete_url = url_for('api.deletejob', job_id=job_id)

            delete_data = {'jid': job_id}
            response = self.client.post(delete_list_url, data=delete_data,
                                        headers=self.headers)
            self.assertEqual(response.status_code, 201)

            # 7. Poll delete until finished
            for _ in range(30):
                time.sleep(3)
                response = self.client.get(delete_url, headers=self.headers)
                status = response.json['compute']['status']
                if status == 'finishedSuccessfully':
                    break
            self.assertEqual(response.json['compute']['status'],
                             'finishedSuccessfully')

            # Verify data was deleted
            self.assertFalse(os.path.isdir(incoming))

            # 8. Delete all containers
            response = self.client.delete(copy_url, headers=self.headers)
            self.assertEqual(response.status_code, 204)

            response = self.client.delete(plugin_url, headers=self.headers)
            self.assertEqual(response.status_code, 204)

            response = self.client.delete(delete_url, headers=self.headers)
            self.assertEqual(response.status_code, 204)

        except Exception:
            # Force-cleanup on failure
            for suffix in ('-copy', '', '-delete'):
                self._remove_container(job_id + suffix)
            key_dir = os.path.join(self.storebase_mount, 'key-' + job_id)
            if os.path.isdir(key_dir):
                shutil.rmtree(key_dir)
            raise

    def test_copy_with_chris_links(self):
        """Copy job should recursively follow .chrislink files."""
        job_id = 'new-fslink-links-1'
        input_rel = os.path.relpath(self.fs_input_path, self.storebase_mount)
        output_rel = os.path.relpath(self.fs_output_path, self.storebase_mount)

        # Set up ChRIS link structure
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

        try:
            with self.app.test_request_context():
                copy_list_url = url_for('api.copyjoblist')
                copy_url = url_for('api.copyjob', job_id=job_id)

            copy_data = {
                'jid': job_id,
                'input_dirs': [input_rel],
                'output_dir': output_rel,
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
            link_parent = os.path.join(self.storebase_mount, 'home/bob')
            if os.path.isdir(link_parent):
                shutil.rmtree(link_parent)


class TestCopyJobListFsLink(NewResourcesFsLinkTests):
    """Test CopyJobList resource specifically."""

    def test_get_returns_server_info(self):
        with self.app.test_request_context():
            url = url_for('api.copyjoblist')
        response = self.client.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['pfcon_innetwork'])
        self.assertEqual(response.json['storage_env'], 'fslink')


class TestPluginJobListFsLink(NewResourcesFsLinkTests):
    """Test PluginJobList resource specifically."""

    def test_get_returns_server_info(self):
        with self.app.test_request_context():
            url = url_for('api.pluginjoblist')
        response = self.client.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['pfcon_innetwork'])


class TestDeleteJobNoDataFsLink(NewResourcesFsLinkTests):
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
