"""
Unit tests for the new client-managed job resources (CopyJob, PluginJob,
UploadJob, DeleteJob) with a mocked DockerManager — no running Docker
daemon required.

Tests cover:
- CopyJobList POST: schedules copy container, saves job_params.json
- CopyJob GET: returns copy container status
- CopyJob DELETE: removes copy container
- PluginJobList POST: schedules plugin container directly (no copy)
- PluginJob GET/DELETE: returns/removes plugin container
- UploadJobList POST: schedules upload container, idempotency checks
- UploadJob GET/DELETE: returns/removes upload container
- DeleteJobList POST: schedules delete container
- DeleteJob GET/DELETE: returns/removes delete container
- No-op behavior for storage modes that don't need copy/upload
"""

import json
import logging
import os
import shutil
import tempfile
from unittest import TestCase, mock

from flask import url_for

from pfcon.app import create_app
from pfcon.compute.abstractmgr import JobInfo, JobStatus, ManagerException


def _make_job_info(status, message='', image='test-image', cmd='',
                   timestamp=''):
    return JobInfo(
        name='test-job',
        image=image,
        cmd=cmd,
        timestamp=timestamp,
        message=message,
        status=status,
    )


class NewResourcesTestBase(TestCase):
    """Base class for all new resource tests with mocked compute."""

    def setUp(self):
        logging.disable(logging.WARNING)
        self.tmpdir = tempfile.mkdtemp()

        env_patch = {
            'APPLICATION_MODE': 'dev',
            'COMPUTE_VOLUME_TYPE': 'host',
            'STOREBASE': self.tmpdir,
            'STOREBASE_MOUNT': self.tmpdir,
        }
        with mock.patch.dict(os.environ, env_patch):
            self.app = create_app({
                'PFCON_INNETWORK': True,
                'STORAGE_ENV': 'fslink',
                'PFCON_OP_IMAGE': 'ghcr.io/fnndsc/pfconopjob:test',
            })

        self.client = self.app.test_client()

        with self.app.test_request_context():
            url = url_for('api.auth')
            creds = {
                'pfcon_user': self.app.config.get('PFCON_USER'),
                'pfcon_password': self.app.config.get('PFCON_PASSWORD'),
            }
            r = self.client.post(url, data=json.dumps(creds),
                                 content_type='application/json')
            self.headers = {'Authorization': 'Bearer ' + r.json['token']}

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        logging.disable(logging.NOTSET)


# ---------------------------------------------------------------------------
# CopyJobList / CopyJob tests
# ---------------------------------------------------------------------------

class TestCopyJobList(NewResourcesTestBase):

    def test_get_returns_server_info(self):
        with self.app.test_request_context():
            url = url_for('api.copyjoblist')
        response = self.client.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn('server_version', response.json)
        self.assertEqual(response.json['storage_env'], 'fslink')

    def test_post_schedules_copy_container(self):
        job_id = 'copy-test-1'
        data = {
            'jid': job_id,
            'input_dirs': ['home/foo/feed/input'],
            'output_dir': 'home/foo/feed/output',
        }

        copy_info = _make_job_info(JobStatus.notStarted)

        with self.app.test_request_context():
            url = url_for('api.copyjoblist')

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            # First get_job call: idempotency check finds no existing job
            mgr.get_job.side_effect = [
                ManagerException('not found', status_code=404),
            ]
            mgr.schedule_job.return_value = 'mock_copy_job'
            mgr.get_job_info.return_value = copy_info

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        self.assertIn('compute', response.json)

        # job_params.json must have been written
        params_file = os.path.join(self.tmpdir, 'key-' + job_id,
                                   'job_params.json')
        self.assertTrue(os.path.isfile(params_file))
        with open(params_file) as f:
            saved = json.load(f)
        self.assertEqual(saved['jid'], job_id)
        self.assertEqual(saved['storage_env'], 'fslink')

        # Schedule was called with '-copy' suffix
        scheduled_name = mgr.schedule_job.call_args[0][2]
        self.assertEqual(scheduled_name, job_id + '-copy')

        # fslink copy needs input mount (storebase root)
        mounts = mgr.schedule_job.call_args[0][7]
        self.assertNotEqual(mounts['inputdir_source'], '')

    def test_post_idempotent_existing_copy(self):
        """If copy container already exists and is running, return
        its status without scheduling a new one."""
        job_id = 'copy-idemp-1'
        data = {
            'jid': job_id,
            'input_dirs': ['home/foo/feed/input'],
            'output_dir': 'home/foo/feed/output',
        }

        with self.app.test_request_context():
            url = url_for('api.copyjoblist')

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            # Existing copy container found and running
            mgr.get_job.return_value = 'existing_copy'
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.started, image='pfconopjob')
            mgr.get_job_logs.return_value = ''

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['compute']['status'], 'started')
        # schedule_job NOT called (idempotent)
        mgr.schedule_job.assert_not_called()

    def test_post_reschedules_failed_copy(self):
        """If previous copy failed, remove it and re-schedule."""
        job_id = 'copy-resched-1'
        key_dir = os.path.join(self.tmpdir, 'key-' + job_id)
        os.makedirs(os.path.join(key_dir, 'incoming'), exist_ok=True)

        data = {
            'jid': job_id,
            'input_dirs': ['home/foo/feed/input'],
            'output_dir': 'home/foo/feed/output',
        }

        failed_info = _make_job_info(JobStatus.finishedWithError)
        new_info = _make_job_info(JobStatus.notStarted)

        with self.app.test_request_context():
            url = url_for('api.copyjoblist')

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mock_failed = mock.MagicMock()
            mgr.get_job.side_effect = [mock_failed]
            mgr.get_job_info.side_effect = [failed_info, new_info]
            mgr.schedule_job.return_value = 'new_copy_job'

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        # Old copy was removed
        mgr.remove_job.assert_called_once_with(mock_failed)
        # New copy was scheduled
        mgr.schedule_job.assert_called_once()

    def test_post_reschedules_undefined_copy(self):
        """If previous copy has undefined status, remove it and re-schedule."""
        job_id = 'copy-undef-1'
        key_dir = os.path.join(self.tmpdir, 'key-' + job_id)
        os.makedirs(os.path.join(key_dir, 'incoming'), exist_ok=True)

        data = {
            'jid': job_id,
            'input_dirs': ['home/foo/feed/input'],
            'output_dir': 'home/foo/feed/output',
        }

        undef_info = _make_job_info(JobStatus.undefined)
        new_info = _make_job_info(JobStatus.notStarted)

        with self.app.test_request_context():
            url = url_for('api.copyjoblist')

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mock_undef = mock.MagicMock()
            mgr.get_job.side_effect = [mock_undef]
            mgr.get_job_info.side_effect = [undef_info, new_info]
            mgr.schedule_job.return_value = 'new_copy_job'

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        mgr.remove_job.assert_called_once_with(mock_undef)
        mgr.schedule_job.assert_called_once()

    def test_post_idempotent_finished_copy(self):
        """If copy container finished successfully, return its status."""
        job_id = 'copy-done-1'
        data = {
            'jid': job_id,
            'input_dirs': ['home/foo/feed/input'],
            'output_dir': 'home/foo/feed/output',
        }

        with self.app.test_request_context():
            url = url_for('api.copyjoblist')

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.return_value = 'existing_copy'
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.finishedSuccessfully, image='pfconopjob')
            mgr.get_job_logs.return_value = 'copy done'

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['compute']['status'],
                         'finishedSuccessfully')
        mgr.schedule_job.assert_not_called()

    def test_post_noop_for_zipfile_storage(self):
        """Copy is a no-op for non-fslink/swift storage."""
        original = self.app.config['PFCON_INNETWORK']
        self.app.config['PFCON_INNETWORK'] = False
        self.app.config['STORAGE_ENV'] = 'zipfile'
        try:
            with self.app.test_request_context():
                url = url_for('api.copyjoblist')
            data = {
                'jid': 'copy-noop-1',
                'input_dirs': ['foo'],
                'output_dir': 'bar',
            }
            response = self.client.post(url, data=data,
                                        headers=self.headers)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json['compute']['status'],
                             'finishedSuccessfully')
            self.assertEqual(response.json['compute']['message'],
                             'copySkipped')
        finally:
            self.app.config['PFCON_INNETWORK'] = original
            self.app.config['STORAGE_ENV'] = 'fslink'

    def test_post_empty_input_dirs_schedules_copy_container(self):
        """Copy with no input_dirs still creates the container (it will do
        nothing and exit 0 — useful for fs-type plugins)."""
        job_id = 'copy-empty-1'
        data = {
            'jid': job_id,
            'output_dir': 'home/foo/feed/output',
            # no input_dirs sent — empty list by default
        }

        copy_info = _make_job_info(JobStatus.notStarted)

        with self.app.test_request_context():
            url = url_for('api.copyjoblist')

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.side_effect = [
                ManagerException('not found', status_code=404),
            ]
            mgr.schedule_job.return_value = 'mock_copy_job'
            mgr.get_job_info.return_value = copy_info

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        self.assertIn('compute', response.json)
        # Container must still be scheduled
        mgr.schedule_job.assert_called_once()

        # job_params.json must have been written with an empty input_dirs list
        params_file = os.path.join(self.tmpdir, 'key-' + job_id,
                                   'job_params.json')
        self.assertTrue(os.path.isfile(params_file))
        with open(params_file) as f:
            saved = json.load(f)
        self.assertEqual(saved['input_dirs'], [])


class TestCopyJob(NewResourcesTestBase):

    def test_get_returns_copy_status(self):
        job_id = 'copy-get-1'
        with self.app.test_request_context():
            url = url_for('api.copyjob', job_id=job_id)

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.return_value = 'mock_copy_job'
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.started, image='pfconopjob')
            mgr.get_job_logs.return_value = ''

            response = self.client.get(url, headers=self.headers)

        self.assertEqual(response.status_code, 200)
        compute = response.json['compute']
        self.assertEqual(compute['jid'], job_id)
        self.assertEqual(compute['status'], 'started')
        # get_job was called with '-copy' suffix
        mgr.get_job.assert_called_once_with(job_id + '-copy')

    def test_delete_removes_copy_container(self):
        job_id = 'copy-del-1'
        with self.app.test_request_context():
            url = url_for('api.copyjob', job_id=job_id)

        mock_job = mock.MagicMock()
        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.return_value = mock_job

            response = self.client.delete(url, headers=self.headers)

        self.assertEqual(response.status_code, 204)
        mgr.get_job.assert_called_once_with(job_id + '-copy')
        mgr.remove_job.assert_called_once_with(mock_job)

    def test_delete_tolerates_missing_container(self):
        job_id = 'copy-del-2'
        with self.app.test_request_context():
            url = url_for('api.copyjob', job_id=job_id)

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.side_effect = ManagerException('not found',
                                                        status_code=404)

            response = self.client.delete(url, headers=self.headers)

        self.assertEqual(response.status_code, 204)
        mgr.remove_job.assert_not_called()


# ---------------------------------------------------------------------------
# PluginJobList / PluginJob tests
# ---------------------------------------------------------------------------

class TestPluginJobList(NewResourcesTestBase):

    def test_post_schedules_plugin_directly_for_fslink(self):
        """For fslink in-network, PluginJobList.post schedules the plugin
        container directly (no copy phase)."""
        job_id = 'plugin-test-1'

        # Create the incoming dir (as if copy already ran)
        incoming = os.path.join(self.tmpdir, 'key-' + job_id, 'incoming')
        os.makedirs(incoming, exist_ok=True)
        with open(os.path.join(incoming, 'test.txt'), 'w') as f:
            f.write('test')

        data = {
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
            'input_dirs': ['home/foo/feed/input'],
            'output_dir': 'home/foo/feed/output',
        }

        plugin_info = _make_job_info(JobStatus.notStarted,
                                     image='fnndsc/pl-simplefsapp')

        with self.app.test_request_context():
            url = url_for('api.pluginjoblist')

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.side_effect = [
                ManagerException('not found', status_code=404),  # idempotency
                'mock_copy_job',  # copy guard
            ]
            mgr.schedule_job.return_value = 'mock_plugin_job'
            mgr.get_job_info.side_effect = [
                _make_job_info(JobStatus.finishedSuccessfully),  # copy guard
                plugin_info,  # schedule response
            ]

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['data'], {})
        self.assertIn('compute', response.json)

        # Main job scheduled directly (no '-copy' suffix)
        scheduled_name = mgr.schedule_job.call_args[0][2]
        self.assertEqual(scheduled_name, job_id)


    def test_post_idempotent_existing_plugin(self):
        """If plugin container already exists and is running, return
        its status without scheduling a new one."""
        job_id = 'plugin-idemp-1'

        incoming = os.path.join(self.tmpdir, 'key-' + job_id, 'incoming')
        os.makedirs(incoming, exist_ok=True)

        data = {
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
            'input_dirs': ['home/foo/feed/input'],
            'output_dir': 'home/foo/feed/output',
        }

        with self.app.test_request_context():
            url = url_for('api.pluginjoblist')

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.return_value = 'existing_plugin'
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.started, image='fnndsc/pl-simplefsapp')
            mgr.get_job_logs.return_value = ''

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['compute']['status'], 'started')
        mgr.schedule_job.assert_not_called()

    def test_post_reschedules_failed_plugin(self):
        """If previous plugin failed, remove it and re-schedule."""
        job_id = 'plugin-resched-1'

        incoming = os.path.join(self.tmpdir, 'key-' + job_id, 'incoming')
        os.makedirs(incoming, exist_ok=True)
        with open(os.path.join(incoming, 'test.txt'), 'w') as f:
            f.write('test')

        data = {
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
            'input_dirs': ['home/foo/feed/input'],
            'output_dir': 'home/foo/feed/output',
        }

        failed_info = _make_job_info(JobStatus.finishedWithError,
                                     image='fnndsc/pl-simplefsapp')
        new_info = _make_job_info(JobStatus.notStarted,
                                  image='fnndsc/pl-simplefsapp')

        with self.app.test_request_context():
            url = url_for('api.pluginjoblist')

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mock_failed = mock.MagicMock()
            mgr.get_job.side_effect = [mock_failed, 'mock_copy_job']
            mgr.get_job_info.side_effect = [
                failed_info,  # idempotency → remove
                _make_job_info(JobStatus.finishedSuccessfully),  # copy guard
                new_info,  # schedule response
            ]
            mgr.schedule_job.return_value = 'new_plugin_job'

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        mgr.remove_job.assert_called_once_with(mock_failed)
        mgr.schedule_job.assert_called_once()

    def test_post_reschedules_undefined_plugin(self):
        """If previous plugin has undefined status, remove and re-schedule."""
        job_id = 'plugin-undef-1'

        incoming = os.path.join(self.tmpdir, 'key-' + job_id, 'incoming')
        os.makedirs(incoming, exist_ok=True)
        with open(os.path.join(incoming, 'test.txt'), 'w') as f:
            f.write('test')

        data = {
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
            'input_dirs': ['home/foo/feed/input'],
            'output_dir': 'home/foo/feed/output',
        }

        undef_info = _make_job_info(JobStatus.undefined,
                                    image='fnndsc/pl-simplefsapp')
        new_info = _make_job_info(JobStatus.notStarted,
                                  image='fnndsc/pl-simplefsapp')

        with self.app.test_request_context():
            url = url_for('api.pluginjoblist')

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mock_undef = mock.MagicMock()
            mgr.get_job.side_effect = [mock_undef, 'mock_copy_job']
            mgr.get_job_info.side_effect = [
                undef_info,  # idempotency → remove
                _make_job_info(JobStatus.finishedSuccessfully),  # copy guard
                new_info,  # schedule response
            ]
            mgr.schedule_job.return_value = 'new_plugin_job'

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        mgr.remove_job.assert_called_once_with(mock_undef)
        mgr.schedule_job.assert_called_once()

    def test_post_empty_input_dirs_allowed_for_fslink(self):
        """For fslink storage the plugin POST accepts no input_dirs (e.g. fs-type
        plugins that generate their own data and have nothing to copy)."""
        job_id = 'plugin-empty-1'

        # Copy worker creates incoming dir even when input_dirs is empty
        incoming = os.path.join(self.tmpdir, 'key-' + job_id, 'incoming')
        os.makedirs(incoming, exist_ok=True)

        data = {
            'jid': job_id,
            'entrypoint': ['python3', '/usr/local/bin/simplefsapp'],
            'args': ['/share/outgoing'],
            'auid': 'cube',
            'number_of_workers': '1',
            'cpu_limit': '1000',
            'memory_limit': '200',
            'gpu_limit': '0',
            'image': 'fnndsc/pl-simplefsapp',
            'type': 'fs',
            # no input_dirs sent — empty list by default
            'output_dir': 'home/foo/feed/output',
        }

        plugin_info = _make_job_info(JobStatus.notStarted,
                                     image='fnndsc/pl-simplefsapp')

        with self.app.test_request_context():
            url = url_for('api.pluginjoblist')

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.side_effect = [
                ManagerException('not found', status_code=404),  # idempotency
                'mock_copy_job',  # copy guard
            ]
            mgr.schedule_job.return_value = 'mock_plugin_job'
            mgr.get_job_info.side_effect = [
                _make_job_info(JobStatus.finishedSuccessfully),  # copy guard
                plugin_info,  # schedule response
            ]

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        mgr.schedule_job.assert_called_once()


class TestPluginJob(NewResourcesTestBase):

    def test_get_returns_plugin_status(self):
        job_id = 'plugin-get-1'
        with self.app.test_request_context():
            url = url_for('api.pluginjob', job_id=job_id)

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.return_value = 'mock_job'
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.finishedSuccessfully,
                image='fnndsc/pl-simplefsapp')
            mgr.get_job_logs.return_value = 'done'

            response = self.client.get(url, headers=self.headers)

        self.assertEqual(response.status_code, 200)
        compute = response.json['compute']
        self.assertEqual(compute['status'], 'finishedSuccessfully')
        self.assertEqual(compute['logs'], 'done')
        # Called with the job_id directly (no suffix)
        mgr.get_job.assert_called_once_with(job_id)

    def test_delete_removes_plugin_container(self):
        job_id = 'plugin-del-1'
        with self.app.test_request_context():
            url = url_for('api.pluginjob', job_id=job_id)

        mock_job = mock.MagicMock()
        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.return_value = mock_job

            response = self.client.delete(url, headers=self.headers)

        self.assertEqual(response.status_code, 204)
        mgr.get_job.assert_called_once_with(job_id)
        mgr.remove_job.assert_called_once_with(mock_job)


class TestPluginJobFile(NewResourcesTestBase):

    def test_get_returns_metadata_for_fslink(self):
        job_id = 'pluginfile-1'

        # Create output files
        output_path = os.path.join(self.tmpdir, 'home/foo/feed/output')
        os.makedirs(os.path.join(output_path, 'results'), exist_ok=True)
        with open(os.path.join(output_path, 'results', 'out.txt'), 'w') as f:
            f.write('output')

        with self.app.test_request_context():
            url = url_for('api.pluginjobfile', job_id=job_id)

        response = self.client.get(
            url,
            query_string={'job_output_path': 'home/foo/feed/output'},
            headers=self.headers)

        self.assertEqual(response.status_code, 200)
        content = json.loads(response.data.decode())
        self.assertEqual(content['job_output_path'], 'home/foo/feed/output')
        self.assertIn('results/out.txt', content['rel_file_paths'])

    def test_get_without_query_param_returns_400(self):
        job_id = 'pluginfile-2'
        with self.app.test_request_context():
            url = url_for('api.pluginjobfile', job_id=job_id)

        response = self.client.get(url, headers=self.headers)
        self.assertEqual(response.status_code, 400)

    def test_get_does_not_schedule_upload(self):
        """PluginJobFile.get must NOT schedule an upload container
        (unlike the legacy JobFile)."""
        job_id = 'pluginfile-noupload'

        output_path = os.path.join(self.tmpdir, 'home/foo/feed/output')
        os.makedirs(output_path, exist_ok=True)
        with open(os.path.join(output_path, 'test.txt'), 'w') as f:
            f.write('data')

        with self.app.test_request_context():
            url = url_for('api.pluginjobfile', job_id=job_id)

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value

            response = self.client.get(
                url,
                query_string={'job_output_path': 'home/foo/feed/output'},
                headers=self.headers)

        self.assertEqual(response.status_code, 200)
        # schedule_job must not have been called
        mgr.schedule_job.assert_not_called()


# ---------------------------------------------------------------------------
# UploadJobList / UploadJob tests
# ---------------------------------------------------------------------------

class TestUploadJobList(NewResourcesTestBase):

    def test_post_noop_for_fslink(self):
        """Upload is a no-op for fslink storage."""
        with self.app.test_request_context():
            url = url_for('api.uploadjoblist')
        data = {
            'jid': 'upload-noop-1',
            'job_output_path': 'foo/output',
        }
        response = self.client.post(url, data=data, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['compute']['status'],
                         'finishedSuccessfully')
        self.assertEqual(response.json['compute']['message'],
                         'uploadSkipped')

    def test_post_schedules_upload_for_swift(self):
        """Upload container is scheduled for swift storage."""
        self.app.config['STORAGE_ENV'] = 'swift'
        self.app.config.setdefault('SWIFT_CONNECTION_PARAMS', {
            'user': 'u', 'key': 'k', 'authurl': 'http://swift:8080/auth/v1.0'
        })
        self.app.config.setdefault('SWIFT_CONTAINER_NAME', 'users')

        job_id = 'upload-swift-1'
        key_dir = os.path.join(self.tmpdir, 'key-' + job_id)
        os.makedirs(key_dir, exist_ok=True)

        try:
            with self.app.test_request_context():
                url = url_for('api.uploadjoblist')

            data = {
                'jid': job_id,
                'job_output_path': 'foo/output',
            }

            upload_info = _make_job_info(JobStatus.notStarted)

            with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
                mgr = MockMgr.return_value
                mgr.get_job.side_effect = [
                    'mock_plugin_job',  # plugin guard
                    ManagerException('not found', status_code=404),  # idempotency
                ]
                mgr.schedule_job.return_value = 'mock_upload_job'
                mgr.get_job_info.side_effect = [
                    _make_job_info(JobStatus.finishedSuccessfully),  # plugin guard
                    upload_info,  # schedule response
                ]

                with mock.patch(
                        'pfcon.resources.connect_to_pfcon_networks'):
                    response = self.client.post(url, data=data,
                                                headers=self.headers)

            self.assertEqual(response.status_code, 201)
            scheduled_name = mgr.schedule_job.call_args[0][2]
            self.assertEqual(scheduled_name, job_id + '-upload')

            # upload worker needs no input mount
            mounts = mgr.schedule_job.call_args[0][7]
            self.assertEqual(mounts['inputdir_source'], '')

            # upload_params.json should exist
            params_file = os.path.join(key_dir, 'upload_params.json')
            self.assertTrue(os.path.isfile(params_file))
        finally:
            self.app.config['STORAGE_ENV'] = 'fslink'

    def test_post_idempotent_existing_upload(self):
        """If upload container already exists and is running, return
        its status without scheduling a new one."""
        self.app.config['STORAGE_ENV'] = 'swift'
        self.app.config.setdefault('SWIFT_CONNECTION_PARAMS', {
            'user': 'u', 'key': 'k', 'authurl': 'http://swift:8080/auth/v1.0'
        })
        self.app.config.setdefault('SWIFT_CONTAINER_NAME', 'users')

        job_id = 'upload-idemp-1'

        try:
            with self.app.test_request_context():
                url = url_for('api.uploadjoblist')

            data = {
                'jid': job_id,
                'job_output_path': 'foo/output',
            }

            with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
                mgr = MockMgr.return_value
                mgr.get_job.side_effect = [
                    'mock_plugin_job',  # plugin guard
                    'existing_upload',  # idempotency: found running
                ]
                mgr.get_job_info.side_effect = [
                    _make_job_info(JobStatus.finishedSuccessfully),  # plugin guard
                    _make_job_info(JobStatus.started, image='pfconopjob'),  # idempotency
                ]
                mgr.get_job_logs.return_value = ''

                response = self.client.post(url, data=data,
                                            headers=self.headers)

            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json['compute']['status'], 'started')
            # schedule_job NOT called (idempotent)
            mgr.schedule_job.assert_not_called()
        finally:
            self.app.config['STORAGE_ENV'] = 'fslink'

    def test_post_reschedules_failed_upload(self):
        """If previous upload failed, remove it and re-schedule."""
        self.app.config['STORAGE_ENV'] = 'swift'
        self.app.config.setdefault('SWIFT_CONNECTION_PARAMS', {
            'user': 'u', 'key': 'k', 'authurl': 'http://swift:8080/auth/v1.0'
        })
        self.app.config.setdefault('SWIFT_CONTAINER_NAME', 'users')

        job_id = 'upload-resched-1'
        key_dir = os.path.join(self.tmpdir, 'key-' + job_id)
        os.makedirs(key_dir, exist_ok=True)

        try:
            with self.app.test_request_context():
                url = url_for('api.uploadjoblist')

            data = {
                'jid': job_id,
                'job_output_path': 'foo/output',
            }

            failed_info = _make_job_info(JobStatus.finishedWithError)
            new_info = _make_job_info(JobStatus.notStarted)

            with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
                mgr = MockMgr.return_value
                mock_failed = mock.MagicMock()
                mgr.get_job.side_effect = [
                    'mock_plugin_job',  # plugin guard
                    mock_failed,  # idempotency: found failed
                ]
                mgr.get_job_info.side_effect = [
                    _make_job_info(JobStatus.finishedSuccessfully),  # plugin guard
                    failed_info,  # idempotency → remove
                    new_info,  # schedule response
                ]
                mgr.schedule_job.return_value = 'new_upload_job'

                with mock.patch(
                        'pfcon.resources.connect_to_pfcon_networks'):
                    response = self.client.post(url, data=data,
                                                headers=self.headers)

            self.assertEqual(response.status_code, 201)
            # Old upload was removed
            mgr.remove_job.assert_called_once_with(mock_failed)
            # New upload was scheduled
            mgr.schedule_job.assert_called_once()
        finally:
            self.app.config['STORAGE_ENV'] = 'fslink'


class TestUploadJob(NewResourcesTestBase):

    def test_get_returns_upload_status(self):
        job_id = 'upload-get-1'
        with self.app.test_request_context():
            url = url_for('api.uploadjob', job_id=job_id)

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.return_value = 'mock_upload'
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.finishedSuccessfully)
            mgr.get_job_logs.return_value = 'upload done'

            response = self.client.get(url, headers=self.headers)

        self.assertEqual(response.status_code, 200)
        compute = response.json['compute']
        self.assertEqual(compute['jid'], job_id)
        self.assertEqual(compute['status'], 'finishedSuccessfully')
        mgr.get_job.assert_called_once_with(job_id + '-upload')

    def test_delete_removes_upload_container(self):
        job_id = 'upload-del-1'
        with self.app.test_request_context():
            url = url_for('api.uploadjob', job_id=job_id)

        mock_job = mock.MagicMock()
        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.return_value = mock_job

            response = self.client.delete(url, headers=self.headers)

        self.assertEqual(response.status_code, 204)
        mgr.get_job.assert_called_once_with(job_id + '-upload')
        mgr.remove_job.assert_called_once_with(mock_job)


# ---------------------------------------------------------------------------
# DeleteJobList / DeleteJob tests
# ---------------------------------------------------------------------------

class TestDeleteJobList(NewResourcesTestBase):

    def test_post_schedules_delete_container(self):
        job_id = 'del-test-1'
        key_dir = os.path.join(self.tmpdir, 'key-' + job_id)
        os.makedirs(os.path.join(key_dir, 'incoming'), exist_ok=True)

        with self.app.test_request_context():
            url = url_for('api.deletejoblist')

        data = {'jid': job_id}
        del_info = _make_job_info(JobStatus.notStarted)

        not_found = ManagerException('not found', status_code=404)
        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.side_effect = [
                not_found,  # copy guard
                not_found,  # plugin guard
                not_found,  # upload guard
                not_found,  # idempotency
            ]
            mgr.schedule_job.return_value = 'mock_del_job'
            mgr.get_job_info.return_value = del_info

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        self.assertIn('compute', response.json)

        # delete_params.json must exist
        params_file = os.path.join(key_dir, 'delete_params.json')
        self.assertTrue(os.path.isfile(params_file))
        with open(params_file) as f:
            saved = json.load(f)
        self.assertEqual(saved['jid'], job_id)

        # Scheduled with '-delete' suffix
        scheduled_name = mgr.schedule_job.call_args[0][2]
        self.assertEqual(scheduled_name, job_id + '-delete')

        # delete worker needs no input mount
        mounts = mgr.schedule_job.call_args[0][7]
        self.assertEqual(mounts['inputdir_source'], '')

    def test_post_noop_when_no_key_dir(self):
        """If the key directory doesn't exist, return success immediately."""
        job_id = 'del-noop-1'
        with self.app.test_request_context():
            url = url_for('api.deletejoblist')

        data = {'jid': job_id}
        response = self.client.post(url, data=data, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['compute']['status'],
                         'finishedSuccessfully')
        self.assertEqual(response.json['compute']['message'],
                         'deleteSkipped')


    def test_post_idempotent_existing_delete(self):
        """If delete container already exists and is running, return
        its status without scheduling a new one."""
        job_id = 'del-idemp-1'
        key_dir = os.path.join(self.tmpdir, 'key-' + job_id)
        os.makedirs(os.path.join(key_dir, 'incoming'), exist_ok=True)

        with self.app.test_request_context():
            url = url_for('api.deletejoblist')

        data = {'jid': job_id}

        not_found = ManagerException('not found', status_code=404)
        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.side_effect = [
                not_found,           # copy guard
                not_found,           # plugin guard
                not_found,           # upload guard
                'existing_delete',   # idempotency: found running
            ]
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.started, image='pfconopjob')
            mgr.get_job_logs.return_value = ''

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['compute']['status'], 'started')
        mgr.schedule_job.assert_not_called()

    def test_post_reschedules_failed_delete(self):
        """If previous delete failed, remove it and re-schedule."""
        job_id = 'del-resched-1'
        key_dir = os.path.join(self.tmpdir, 'key-' + job_id)
        os.makedirs(os.path.join(key_dir, 'incoming'), exist_ok=True)

        with self.app.test_request_context():
            url = url_for('api.deletejoblist')

        data = {'jid': job_id}

        failed_info = _make_job_info(JobStatus.finishedWithError)
        new_info = _make_job_info(JobStatus.notStarted)

        not_found = ManagerException('not found', status_code=404)
        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mock_failed = mock.MagicMock()
            mgr.get_job.side_effect = [
                not_found,     # copy guard
                not_found,     # plugin guard
                not_found,     # upload guard
                mock_failed,   # idempotency: found failed
            ]
            mgr.get_job_info.side_effect = [failed_info, new_info]
            mgr.schedule_job.return_value = 'new_del_job'

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        mgr.remove_job.assert_called_once_with(mock_failed)
        mgr.schedule_job.assert_called_once()

    def test_post_reschedules_undefined_delete(self):
        """If previous delete has undefined status, remove and re-schedule."""
        job_id = 'del-undef-1'
        key_dir = os.path.join(self.tmpdir, 'key-' + job_id)
        os.makedirs(os.path.join(key_dir, 'incoming'), exist_ok=True)

        with self.app.test_request_context():
            url = url_for('api.deletejoblist')

        data = {'jid': job_id}

        undef_info = _make_job_info(JobStatus.undefined)
        new_info = _make_job_info(JobStatus.notStarted)

        not_found = ManagerException('not found', status_code=404)
        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mock_undef = mock.MagicMock()
            mgr.get_job.side_effect = [
                not_found,    # copy guard
                not_found,    # plugin guard
                not_found,    # upload guard
                mock_undef,   # idempotency: found undefined
            ]
            mgr.get_job_info.side_effect = [undef_info, new_info]
            mgr.schedule_job.return_value = 'new_del_job'

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        mgr.remove_job.assert_called_once_with(mock_undef)
        mgr.schedule_job.assert_called_once()

    def test_post_idempotent_finished_delete(self):
        """If delete container finished successfully, return its status."""
        job_id = 'del-done-1'
        key_dir = os.path.join(self.tmpdir, 'key-' + job_id)
        os.makedirs(os.path.join(key_dir, 'incoming'), exist_ok=True)

        with self.app.test_request_context():
            url = url_for('api.deletejoblist')

        data = {'jid': job_id}

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.return_value = 'existing_delete'
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.finishedSuccessfully, image='pfconopjob')
            mgr.get_job_logs.return_value = 'deleted'

            response = self.client.post(url, data=data,
                                        headers=self.headers)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['compute']['status'],
                         'finishedSuccessfully')
        mgr.schedule_job.assert_not_called()


class TestDeleteJob(NewResourcesTestBase):

    def test_get_returns_delete_status(self):
        job_id = 'del-get-1'
        with self.app.test_request_context():
            url = url_for('api.deletejob', job_id=job_id)

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.return_value = 'mock_del'
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.finishedSuccessfully)
            mgr.get_job_logs.return_value = 'deleted'

            response = self.client.get(url, headers=self.headers)

        self.assertEqual(response.status_code, 200)
        compute = response.json['compute']
        self.assertEqual(compute['jid'], job_id)
        self.assertEqual(compute['status'], 'finishedSuccessfully')
        mgr.get_job.assert_called_once_with(job_id + '-delete')

    def test_delete_removes_delete_container(self):
        job_id = 'del-del-1'
        with self.app.test_request_context():
            url = url_for('api.deletejob', job_id=job_id)

        mock_job = mock.MagicMock()
        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr.get_job.return_value = mock_job

            response = self.client.delete(url, headers=self.headers)

        self.assertEqual(response.status_code, 204)
        mgr.get_job.assert_called_once_with(job_id + '-delete')
        mgr.remove_job.assert_called_once_with(mock_job)


# ---------------------------------------------------------------------------
# Job safeguard tests
# ---------------------------------------------------------------------------

class TestPluginJobCopyGuard(NewResourcesTestBase):
    """Safeguard: plugin job requires a successfully completed copy job
    in fslink/swift in-network mode."""

    _plugin_data = {
        'entrypoint': ['python3', '/usr/local/bin/simplefsapp'],
        'args': ['--dir', '/share/incoming'],
        'auid': 'cube',
        'number_of_workers': '1',
        'cpu_limit': '1000',
        'memory_limit': '200',
        'gpu_limit': '0',
        'image': 'fnndsc/pl-simplefsapp',
        'type': 'fs',
        'input_dirs': ['home/foo/feed/input'],
        'output_dir': 'home/foo/feed/output',
    }

    def _post_plugin(self, job_id, mgr_setup):
        data = dict(self._plugin_data, jid=job_id)

        with self.app.test_request_context():
            url = url_for('api.pluginjoblist')

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr_setup(mgr)
            response = self.client.post(url, data=data,
                                        headers=self.headers)
        return response

    def test_rejected_when_no_copy_job(self):
        """409 when no copy job exists."""
        not_found = ManagerException('not found', status_code=404)

        def setup(mgr):
            mgr.get_job.side_effect = [
                not_found,  # idempotency
                not_found,  # copy guard: not found
            ]

        response = self._post_plugin('guard-nocopy', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('No copy job found', response.json['message'])

    def test_rejected_when_copy_started(self):
        """409 when copy job is still running."""
        not_found = ManagerException('not found', status_code=404)

        def setup(mgr):
            mgr.get_job.side_effect = [
                not_found,        # idempotency
                'mock_copy_job',  # copy guard
            ]
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.started)

        response = self._post_plugin('guard-copyrun', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('started', response.json['message'])
        self.assertIn('copy job', response.json['message'].lower())

    def test_rejected_when_copy_not_started(self):
        """409 when copy job hasn't started yet."""
        not_found = ManagerException('not found', status_code=404)

        def setup(mgr):
            mgr.get_job.side_effect = [
                not_found,        # idempotency
                'mock_copy_job',  # copy guard
            ]
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.notStarted)

        response = self._post_plugin('guard-copyns', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('notStarted', response.json['message'])

    def test_rejected_when_copy_failed(self):
        """409 when copy job finished with error."""
        not_found = ManagerException('not found', status_code=404)

        def setup(mgr):
            mgr.get_job.side_effect = [
                not_found,        # idempotency
                'mock_copy_job',  # copy guard
            ]
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.finishedWithError)

        response = self._post_plugin('guard-copyfail', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('finishedWithError', response.json['message'])

    def test_rejected_when_copy_undefined(self):
        """409 when copy job has undefined status."""
        not_found = ManagerException('not found', status_code=404)

        def setup(mgr):
            mgr.get_job.side_effect = [
                not_found,        # idempotency
                'mock_copy_job',  # copy guard
            ]
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.undefined)

        response = self._post_plugin('guard-copyundef', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('undefined', response.json['message'])

    def test_no_guard_for_zipfile_storage(self):
        """Copy guard does not apply for out-of-network zipfile mode."""
        self.app.config['PFCON_INNETWORK'] = False
        self.app.config['STORAGE_ENV'] = 'zipfile'

        try:
            job_id = 'guard-zipfile'
            incoming = os.path.join(self.tmpdir, 'key-' + job_id,
                                    'incoming')
            os.makedirs(incoming, exist_ok=True)

            data = dict(self._plugin_data, jid=job_id)

            # Create a minimal zip file for zipfile storage
            import io
            import zipfile
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, 'w') as zf:
                zf.writestr('test.txt', 'test')
            zip_buf.seek(0)

            with self.app.test_request_context():
                url = url_for('api.pluginjoblist')

            with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
                mgr = MockMgr.return_value
                mgr.get_job.side_effect = ManagerException(
                    'not found', status_code=404)
                mgr.schedule_job.return_value = 'mock_plugin'
                mgr.get_job_info.return_value = _make_job_info(
                    JobStatus.notStarted)

                response = self.client.post(
                    url,
                    data={**data, 'data_file': (zip_buf, 'data.zip')},
                    headers=self.headers,
                    content_type='multipart/form-data')

            self.assertEqual(response.status_code, 201)
            mgr.schedule_job.assert_called_once()
        finally:
            self.app.config['PFCON_INNETWORK'] = True
            self.app.config['STORAGE_ENV'] = 'fslink'


class TestUploadJobPluginGuard(NewResourcesTestBase):
    """Safeguard: upload job requires a successfully completed plugin job
    in swift in-network mode."""

    def setUp(self):
        super().setUp()
        self.app.config['STORAGE_ENV'] = 'swift'
        self.app.config.setdefault('SWIFT_CONNECTION_PARAMS', {
            'user': 'u', 'key': 'k',
            'authurl': 'http://swift:8080/auth/v1.0',
        })
        self.app.config.setdefault('SWIFT_CONTAINER_NAME', 'users')

    def tearDown(self):
        self.app.config['STORAGE_ENV'] = 'fslink'
        super().tearDown()

    def _post_upload(self, job_id, mgr_setup):
        data = {'jid': job_id, 'job_output_path': 'foo/output'}

        with self.app.test_request_context():
            url = url_for('api.uploadjoblist')

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr_setup(mgr)
            response = self.client.post(url, data=data,
                                        headers=self.headers)
        return response

    def test_rejected_when_no_plugin_job(self):
        """409 when no plugin job exists."""
        def setup(mgr):
            mgr.get_job.side_effect = ManagerException(
                'not found', status_code=404)

        response = self._post_upload('guard-noplugin', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('No plugin job found', response.json['message'])

    def test_rejected_when_plugin_started(self):
        """409 when plugin job is still running."""
        def setup(mgr):
            mgr.get_job.return_value = 'mock_plugin'
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.started)

        response = self._post_upload('guard-plugrun', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('started', response.json['message'])
        self.assertIn('plugin job', response.json['message'].lower())

    def test_rejected_when_plugin_not_started(self):
        """409 when plugin job hasn't started yet."""
        def setup(mgr):
            mgr.get_job.return_value = 'mock_plugin'
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.notStarted)

        response = self._post_upload('guard-plugns', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('notStarted', response.json['message'])

    def test_rejected_when_plugin_failed(self):
        """409 when plugin job finished with error."""
        def setup(mgr):
            mgr.get_job.return_value = 'mock_plugin'
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.finishedWithError)

        response = self._post_upload('guard-plugfail', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('finishedWithError', response.json['message'])

    def test_rejected_when_plugin_undefined(self):
        """409 when plugin job has undefined status."""
        def setup(mgr):
            mgr.get_job.return_value = 'mock_plugin'
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.undefined)

        response = self._post_upload('guard-plugundef', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('undefined', response.json['message'])

    def test_noop_skips_guard_for_fslink(self):
        """Upload guard does not apply for fslink (upload is a no-op)."""
        self.app.config['STORAGE_ENV'] = 'fslink'

        data = {'jid': 'guard-fslink', 'job_output_path': 'foo/output'}
        with self.app.test_request_context():
            url = url_for('api.uploadjoblist')
        response = self.client.post(url, data=data, headers=self.headers)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['compute']['message'],
                         'uploadSkipped')


class TestDeleteJobSiblingGuard(NewResourcesTestBase):
    """Safeguard: delete job requires all sibling jobs (copy, plugin,
    upload) to be in a terminal state or not exist."""

    def _post_delete(self, job_id, mgr_setup):
        # Ensure key dir exists (delete skips if missing)
        key_dir = os.path.join(self.tmpdir, 'key-' + job_id)
        os.makedirs(key_dir, exist_ok=True)

        data = {'jid': job_id}

        with self.app.test_request_context():
            url = url_for('api.deletejoblist')

        with mock.patch('pfcon.base_resources.DockerManager') as MockMgr:
            mgr = MockMgr.return_value
            mgr_setup(mgr)
            response = self.client.post(url, data=data,
                                        headers=self.headers)
        return response

    def test_rejected_when_copy_running(self):
        """409 when copy job is still running."""
        def setup(mgr):
            mgr.get_job.return_value = 'mock_copy'
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.started)

        response = self._post_delete('guard-delcopy', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('copy', response.json['message'])
        self.assertIn('started', response.json['message'])

    def test_rejected_when_copy_not_started(self):
        """409 when copy job hasn't started yet."""
        def setup(mgr):
            mgr.get_job.return_value = 'mock_copy'
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.notStarted)

        response = self._post_delete('guard-delcopyns', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('copy', response.json['message'])
        self.assertIn('notStarted', response.json['message'])

    def test_rejected_when_plugin_running(self):
        """409 when plugin job is still running."""
        not_found = ManagerException('not found', status_code=404)

        def setup(mgr):
            mgr.get_job.side_effect = [
                not_found,       # copy guard: not found → pass
                'mock_plugin',   # plugin guard
            ]
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.started)

        response = self._post_delete('guard-delplug', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('plugin', response.json['message'])

    def test_rejected_when_plugin_not_started(self):
        """409 when plugin job hasn't started yet."""
        not_found = ManagerException('not found', status_code=404)

        def setup(mgr):
            mgr.get_job.side_effect = [
                not_found,       # copy guard: not found → pass
                'mock_plugin',   # plugin guard
            ]
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.notStarted)

        response = self._post_delete('guard-delplugns', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('plugin', response.json['message'])

    def test_rejected_when_upload_running(self):
        """409 when upload job is still running."""
        not_found = ManagerException('not found', status_code=404)

        def setup(mgr):
            mgr.get_job.side_effect = [
                not_found,       # copy guard: not found → pass
                not_found,       # plugin guard: not found → pass
                'mock_upload',   # upload guard
            ]
            mgr.get_job_info.return_value = _make_job_info(
                JobStatus.started)

        response = self._post_delete('guard-delupload', setup)
        self.assertEqual(response.status_code, 409)
        self.assertIn('upload', response.json['message'])

    def test_allowed_when_all_siblings_terminal(self):
        """201 when all sibling jobs are in terminal states."""
        not_found = ManagerException('not found', status_code=404)
        del_info = _make_job_info(JobStatus.notStarted)

        def setup(mgr):
            mgr.get_job.side_effect = [
                'mock_copy',     # copy guard: finishedSuccessfully
                'mock_plugin',   # plugin guard: finishedWithError
                'mock_upload',   # upload guard: undefined
                not_found,       # idempotency: not found
            ]
            mgr.get_job_info.side_effect = [
                _make_job_info(JobStatus.finishedSuccessfully),
                _make_job_info(JobStatus.finishedWithError),
                _make_job_info(JobStatus.undefined),
                del_info,  # schedule response
            ]
            mgr.schedule_job.return_value = 'mock_del_job'

        response = self._post_delete('guard-delok', setup)
        self.assertEqual(response.status_code, 201)

    def test_allowed_when_no_sibling_jobs(self):
        """201 when no sibling jobs exist at all."""
        not_found = ManagerException('not found', status_code=404)
        del_info = _make_job_info(JobStatus.notStarted)

        def setup(mgr):
            mgr.get_job.side_effect = [
                not_found,  # copy guard
                not_found,  # plugin guard
                not_found,  # upload guard
                not_found,  # idempotency
            ]
            mgr.schedule_job.return_value = 'mock_del_job'
            mgr.get_job_info.return_value = del_info

        response = self._post_delete('guard-delnone', setup)
        self.assertEqual(response.status_code, 201)

    def test_noop_skips_guard_when_no_key_dir(self):
        """Delete skips all guards if key directory doesn't exist."""
        job_id = 'guard-nodir'
        # Do NOT create key dir

        data = {'jid': job_id}
        with self.app.test_request_context():
            url = url_for('api.deletejoblist')

        response = self.client.post(url, data=data, headers=self.headers)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['compute']['message'],
                         'deleteSkipped')
