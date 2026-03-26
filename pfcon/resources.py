
import json
import os
import logging
import zipfile
from datetime import datetime, timedelta
import jwt
from typing import List, Collection

from flask import request, send_file, current_app as app
from flask_restful import reqparse, abort, Resource

from .storage.zip_file_storage import ZipFileStorage
from .storage.swift_storage import SwiftStorage
from .storage.filesystem_storage import FileSystemStorage
from .storage.fslink_storage import FSLinkStorage
from .compute.abstractmgr import JobStatus, ManagerException
from .compute._helpers import connect_to_pfcon_networks
from .base_resources import BaseJobList, BaseJob, get_compute_mgr


logger = logging.getLogger(__name__)

parser_auth = reqparse.RequestParser(bundle_errors=True)
parser_auth.add_argument('pfcon_user', dest='pfcon_user', required=True)
parser_auth.add_argument('pfcon_password', dest='pfcon_password', required=True)


class Auth(Resource):
    """
    Authorization resource.
    """

    def __init__(self):
        super(Auth, self).__init__()

        self.pfcon_user = app.config.get('PFCON_USER')
        self.pfcon_password = app.config.get('PFCON_PASSWORD')
        self.secret_key = app.config.get('SECRET_KEY')

    def post(self):
        args = parser_auth.parse_args()

        if not self.check_credentials(args.pfcon_user, args.pfcon_password):
            abort(400, message='Unable to log in with provided credentials.')
        return {
            'token': self.create_token()
        }

    def check_credentials(self, user, password):
        return user == self.pfcon_user and password == self.pfcon_password

    def create_token(self):
        dt = datetime.now() + timedelta(days=2)
        return jwt.encode({'pfcon_user': self.pfcon_user, 'exp': dt},
                          self.secret_key,
                          algorithm='HS256')

    @staticmethod
    def check_token():
        bearer_token = request.headers.get('Authorization')

        if not bearer_token:
            abort(401, message='Missing authorization header.')

        if not bearer_token.startswith('Bearer '):
            abort(401, message='Invalid authorization header.')

        token = bearer_token.split(' ')[1]

        try:
            jwt.decode(token, app.config.get('SECRET_KEY'), algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            logger.info(f'Authorization Token {token} expired')
            abort(401, message='Expired authorization token.')
        except jwt.InvalidTokenError:
            logger.info(f'Invalid authorization token {token}')
            abort(401, message='Invalid authorization token.')


class HealthCheck(Resource):
    """
    Health check resource.
    """

    def get(self):
        return {
            'health': 'OK'
        }


# ---------------------------------------------------------------------------
# Parsers for client-managed job resources
# ---------------------------------------------------------------------------

parser_plugin = reqparse.RequestParser(bundle_errors=True)
parser_plugin.add_argument('jid', dest='jid', required=True, location='form')
parser_plugin.add_argument('args', dest='args', required=True, type=str,
                           action='append', location='form', default=[])
parser_plugin.add_argument('args_path_flags', dest='args_path_flags', type=str,
                           action='append', location='form', default=[])
parser_plugin.add_argument('auid', dest='auid', required=True, location='form')
parser_plugin.add_argument('number_of_workers', dest='number_of_workers',
                           type=int, required=True, location='form')
parser_plugin.add_argument('cpu_limit', dest='cpu_limit', type=int,
                           required=True, location='form')
parser_plugin.add_argument('memory_limit', dest='memory_limit', type=int,
                           required=True, location='form')
parser_plugin.add_argument('gpu_limit', dest='gpu_limit', type=int,
                           required=True, location='form')
parser_plugin.add_argument('image', dest='image', required=True,
                           location='form')
parser_plugin.add_argument('entrypoint', dest='entrypoint', type=str,
                           required=True, action='append', location='form')
parser_plugin.add_argument('type', dest='type', choices=('ds', 'fs', 'ts'),
                           required=True, location='form')
parser_plugin.add_argument('env', dest='env', type=str, action='append',
                           location='form', default=[])
parser_plugin.add_argument('input_dirs', dest='input_dirs', required=False,
                           type=str, action='append', location='form')
parser_plugin.add_argument('output_dir', dest='output_dir', required=False,
                           location='form')
parser_plugin.add_argument('data_file', dest='data_file', required=False,
                           location='files')

parser_copy = reqparse.RequestParser(bundle_errors=True)
parser_copy.add_argument('jid', dest='jid', required=True, location='form')
parser_copy.add_argument('input_dirs', dest='input_dirs', required=False,
                         type=str, action='append', location='form', default=[])
parser_copy.add_argument('output_dir', dest='output_dir', required=True,
                         location='form')
parser_copy.add_argument('cpu_limit', dest='cpu_limit', type=int,
                         location='form', default=1000)
parser_copy.add_argument('memory_limit', dest='memory_limit', type=int,
                         location='form', default=300)

parser_upload = reqparse.RequestParser(bundle_errors=True)
parser_upload.add_argument('jid', dest='jid', required=True, location='form')
parser_upload.add_argument('job_output_path', dest='job_output_path',
                           required=True, location='form')
parser_upload.add_argument('cpu_limit', dest='cpu_limit', type=int,
                           location='form', default=1000)
parser_upload.add_argument('memory_limit', dest='memory_limit', type=int,
                           location='form', default=300)

parser_delete = reqparse.RequestParser(bundle_errors=True)
parser_delete.add_argument('jid', dest='jid', required=True, location='form')
parser_delete.add_argument('cpu_limit', dest='cpu_limit', type=int,
                           location='form', default=1000)
parser_delete.add_argument('memory_limit', dest='memory_limit', type=int,
                           location='form', default=300)


# ---------------------------------------------------------------------------
# CopyJobList / CopyJob
# ---------------------------------------------------------------------------

class CopyJobList(BaseJobList):
    """
    Resource for scheduling and listing copy jobs.
    POST schedules an async copy container for fslink/swift storage.
    For other storage modes the copy is a no-op.
    Idempotent: if the copy container already exists and hasn't failed,
    the POST returns the existing container's status.
    """

    def get(self):
        return self._get_server_info()

    def post(self):
        args = parser_copy.parse_args()
        job_id = args.jid.lstrip('/')

        logger.info(f'Received copy job request for {job_id}')

        # No-op for storage modes that don't need async copy
        if not (self.pfcon_innetwork
                and self.storage_env in ('fslink', 'swift')):
            return {'compute': {
                'jid': job_id,
                'image': '',
                'cmd': '',
                'status': 'finishedSuccessfully',
                'message': 'copySkipped',
                'timestamp': '',
                'logs': '',
            }}, 201

        copy_name = job_id + '-copy'

        exists, response = self._check_existing_job(copy_name,
                                                     jid_for_response=job_id)
        if exists:
            return response, 201

        key_dir = os.path.join(self.storebase_mount, 'key-' + job_id)
        incoming_dir = os.path.join(key_dir, 'incoming')
        os.makedirs(incoming_dir, exist_ok=True)

        # Save parameters for the copy worker
        params = {
            'jid': job_id,
            'storage_env': self.storage_env,
            'input_dirs': args.input_dirs,
            'output_dir': args.output_dir,
        }
        params_file = os.path.join(key_dir, 'job_params.json')
        with open(params_file, 'w') as f:
            json.dump(params, f)

        op_image = self._get_op_image()
        copy_cmd = ['python', '-m', 'pfcon.copy_worker',
                    self.str_app_container_outputdir]

        resources_dict = {
            'number_of_workers': 1,
            'cpu_limit': args.cpu_limit,
            'memory_limit': args.memory_limit,
            'gpu_limit': 0,
        }

        # For fslink: inputdir -> storebase root (read-only shared filesystem)
        # For swift: no input mount needed (copy worker reads from network)
        if self.storage_env == 'fslink':
            if self.compute_volume_type in ('host', 'docker_local_volume'):
                inputdir_override = app.config.get('STOREBASE')
            else:
                inputdir_override = ''  # PVC root
            mounts_dict = self._build_key_mounts(job_id, inputdir_override)
        else:
            mounts_dict = self._build_key_mounts(job_id)
            mounts_dict['inputdir_source'] = ''  # swift copy reads from network

        copy_env = []
        if self.storage_env == 'swift':
            copy_env = self._build_swift_env()

        job, d_compute = self._schedule_container(
            op_image, copy_cmd, copy_name, resources_dict, copy_env,
            mounts_dict, jid_for_response=job_id, pfcon_user=True)

        # For swift+docker: connect to pfcon's network for Swift DNS
        if self.storage_env == 'swift' and self.container_env == 'docker':
            connect_to_pfcon_networks(job, app.config.get('PFCON_SELECTOR'))

        return {'compute': d_compute}, 201


class CopyJob(BaseJob):
    """
    Resource for checking status of and deleting a single data copy job.
    """

    def get(self, job_id):
        return self._get_job_status(job_id + '-copy',
                                    jid_for_response=job_id)

    def delete(self, job_id):
        self._remove_job(job_id + '-copy')
        return '', 204


# ---------------------------------------------------------------------------
# PluginJobList / PluginJob / PluginJobFile
# ---------------------------------------------------------------------------

class PluginJobList(BaseJobList):
    """
    Resource for scheduling plugin container jobs.
    The client is responsible for scheduling copy/upload/delete separately.
    Idempotent: if the plugin container already exists and hasn't failed,
    the POST returns the existing container's status.
    """

    def get(self):
        return self._get_server_info()

    def post(self):
        args = parser_plugin.parse_args()
        self._validate_data(args)

        job_id = args.jid.lstrip('/')
        logger.info(f'Received plugin job {job_id}')

        exists, response = self._check_existing_job(job_id)
        if exists:
            return {'data': {}, 'compute': response['compute']}, 201

        # For fslink/swift in-network: copy already done by client via
        # CopyJobList. Schedule the plugin container directly.
        if self.pfcon_innetwork and self.storage_env in ('fslink', 'swift'):
            copy_name = job_id + '-copy'
            compute_mgr = get_compute_mgr(self.container_env)
            try:
                copy_job = compute_mgr.get_job(copy_name)
                copy_info = compute_mgr.get_job_info(copy_job)
                if copy_info.status != JobStatus.finishedSuccessfully:
                    abort(409, message=f'Copy job has not completed '
                                       f'successfully (status: '
                                       f'{copy_info.status.value}). Run the '
                                       f'copy job first.')
            except ManagerException:
                abort(409, message='No copy job found. A copy job must '
                                   'complete successfully before scheduling '
                                   'a plugin job.')

            input_dir = 'key-' + job_id + '/incoming'

            if self.storage_env == 'swift':
                output_dir = 'key-' + job_id + '/outgoing'
                outgoing_dir = os.path.join(self.storebase_mount, output_dir)
                os.makedirs(outgoing_dir, exist_ok=True)
                os.chmod(outgoing_dir, 0o777)
            else:
                output_dir = args.output_dir.strip('/')

            d_compute = self._process_compute(args, job_id, input_dir,
                                              output_dir)
            return {'data': {}, 'compute': d_compute}, 201

        # For zipfile/filesystem: process data synchronously then compute
        input_dir, output_dir, d_info = self._process_data(args, job_id)
        d_compute = self._process_compute(args, job_id, input_dir, output_dir)
        return {'data': d_info, 'compute': d_compute}, 201

    def _process_data(self, args, job_id):
        input_dir = 'key-' + job_id + '/incoming'
        output_dir = 'key-' + job_id + '/outgoing'

        if self.pfcon_innetwork and self.storage_env == 'filesystem':
            input_dir = args.input_dirs[0].strip('/')
            output_dir = args.output_dir.strip('/')
            incoming_dir = os.path.join(self.storebase_mount, input_dir)
            storage = FileSystemStorage(app.config)

            try:
                d_info = storage.store_data(job_id, incoming_dir, None)
            except Exception as e:
                logger.error(f'Error while accessing files from shared '
                             f'filesystem for job {job_id}, detail: {str(e)}')
                abort(400, message='input_dirs: Error accessing files from '
                                   'shared filesystem')
            return input_dir, output_dir, d_info

        incoming_dir = os.path.join(self.storebase_mount, input_dir)
        os.makedirs(incoming_dir, exist_ok=True)

        if not self.pfcon_innetwork and self.storage_env == 'zipfile':
            outgoing_dir = os.path.join(self.storebase_mount, output_dir)
            os.makedirs(outgoing_dir, exist_ok=True)
            storage = ZipFileStorage(app.config)
            data_file = request.files['data_file']

            try:
                d_info = storage.store_data(job_id, incoming_dir, data_file)
            except zipfile.BadZipFile as e:
                logger.error(f'Error while decompressing and storing '
                             f'job {job_id} data, detail: {str(e)}')
                abort(400, message='data_file: Bad zip file')

        logger.info(f'Successfully stored job {job_id} input data')
        return input_dir, output_dir, d_info

    def _process_compute(self, args, job_id, input_dir, output_dir):
        if app.config.get('ENABLE_HOME_WORKAROUND'):
            args.env.append('HOME=/tmp')

        cmd = _build_app_cmd(args.args, args.args_path_flags,
                             args.entrypoint, args.type,
                             self.str_app_container_inputdir,
                             self.str_app_container_outputdir)

        resources_dict = {
            'number_of_workers': args.number_of_workers,
            'cpu_limit': args.cpu_limit,
            'memory_limit': args.memory_limit,
            'gpu_limit': args.gpu_limit,
        }
        mounts_dict = {
            'inputdir_source': '',
            'inputdir_target': self.str_app_container_inputdir,
            'outputdir_source': '',
            'outputdir_target': self.str_app_container_outputdir,
        }

        if self.compute_volume_type in ('host', 'docker_local_volume'):
            storebase = app.config.get('STOREBASE')
            mounts_dict['inputdir_source'] = os.path.join(storebase,
                                                          input_dir)
            mounts_dict['outputdir_source'] = os.path.join(storebase,
                                                           output_dir)
        elif self.compute_volume_type == 'kubernetes_pvc':
            mounts_dict['inputdir_source'] = input_dir
            mounts_dict['outputdir_source'] = output_dir

        _, d_compute = self._schedule_container(
            args.image, cmd, job_id, resources_dict, args.env, mounts_dict)

        return d_compute

    def _validate_data(self, args):
        if self.pfcon_innetwork:
            # For fslink/swift the plugin POST never reads input_dirs from args
            # (data was already staged by the copy worker into key-<jid>/incoming/).
            # For filesystem storage args.input_dirs[0] is used directly, so it
            # must be present and non-empty.
            if self.storage_env not in ('fslink', 'swift'):
                if not args.input_dirs:
                    abort(400, message='input_dirs: field is required')
            if args.output_dir is None:
                abort(400, message='output_dir: field is required')
        else:
            if request.files['data_file'] is None:
                abort(400, message='data_file: field is required')

        if len(args.entrypoint) == 0:
            abort(400, message='entrypoint: cannot be empty')

        for s in args.env:
            if len(s.split('=', 1)) != 2:
                abort(400, message='env: must be a list of "key=value" strings')


class PluginJob(BaseJob):
    """
    Resource for checking status of and deleting a single plugin job.
    """

    def get(self, job_id):
        return self._get_job_status(job_id)

    def delete(self, job_id):
        self._remove_job(job_id)
        return '', 204


class PluginJobFile(Resource):
    """
    Resource for retrieving plugin job output data.
    Does NOT schedule upload containers — client manages that separately.
    """

    def __init__(self):
        super().__init__()

        self.storage_env = app.config.get('STORAGE_ENV')
        self.pfcon_innetwork = app.config.get('PFCON_INNETWORK')
        self.storebase_mount = app.config.get('STOREBASE_MOUNT')

    def get(self, job_id):
        content = b''
        download_name = f'{job_id}.zip'
        mimetype = 'application/zip'

        if self.pfcon_innetwork and self.storage_env in ('filesystem', 'fslink'):
            job_output_path = request.args.get('job_output_path')

            if not job_output_path:
                abort(400, message='job_output_path: query parameter is required')

            job_output_path = job_output_path.strip('/')
            outgoing_dir = os.path.join(self.storebase_mount, job_output_path)

            if not os.path.isdir(outgoing_dir):
                abort(404)

            if self.storage_env == 'filesystem':
                storage = FileSystemStorage(app.config)
            else:
                storage = FSLinkStorage(app.config)

            content = storage.get_data(job_id, outgoing_dir,
                                       job_output_path=job_output_path)
            download_name = f'{job_id}.json'
            mimetype = 'application/json'

        elif self.pfcon_innetwork and self.storage_env == 'swift':
            job_output_path = request.args.get('job_output_path')

            if job_output_path:
                job_output_path = job_output_path.lstrip('/')
                job_dir = os.path.join(self.storebase_mount, 'key-' + job_id)
                outgoing_dir = os.path.join(job_dir, 'outgoing')
                if not os.path.exists(outgoing_dir):
                    os.mkdir(outgoing_dir)

                storage = SwiftStorage(app.config)
                content = storage.get_output_metadata(
                    job_id, outgoing_dir,
                    job_output_path=job_output_path)
                
                download_name = f'{job_id}.json'
                mimetype = 'application/json'
            else:
                job_dir = os.path.join(self.storebase_mount, 'key-' + job_id)
                if not os.path.isdir(job_dir):
                    abort(404)

                outgoing_dir = os.path.join(job_dir, 'outgoing')
                if not os.path.exists(outgoing_dir):
                    os.mkdir(outgoing_dir)

                storage = ZipFileStorage(app.config)
                content = storage.get_data(job_id, outgoing_dir)
        else:
            job_dir = os.path.join(self.storebase_mount, 'key-' + job_id)
            if not os.path.isdir(job_dir):
                abort(404)

            outgoing_dir = os.path.join(job_dir, 'outgoing')
            if not os.path.exists(outgoing_dir):
                os.mkdir(outgoing_dir)

            if self.storage_env == 'zipfile':
                storage = ZipFileStorage(app.config)
                content = storage.get_data(job_id, outgoing_dir)

        logger.info(f'Successfully retrieved job {job_id} output data')

        return send_file(content, download_name=download_name,
                         as_attachment=True, mimetype=mimetype)


# ---------------------------------------------------------------------------
# UploadJobList / UploadJob
# ---------------------------------------------------------------------------

class UploadJobList(BaseJobList):
    """
    Resource for scheduling upload jobs (Swift storage only).
    For non-Swift storage the upload is a no-op.
    Idempotent: if the upload container already exists and hasn't failed,
    the POST returns the existing container's status.
    """

    def get(self):
        return self._get_server_info()

    def post(self):
        args = parser_upload.parse_args()
        job_id = args.jid.lstrip('/')
        job_output_path = args.job_output_path.lstrip('/')

        logger.info(f'Received upload job request for {job_id}')

        # No-op for non-Swift storage
        if not (self.pfcon_innetwork and self.storage_env == 'swift'):
            return {'compute': {
                'jid': job_id,
                'image': '',
                'cmd': '',
                'status': 'finishedSuccessfully',
                'message': 'uploadSkipped',
                'timestamp': '',
                'logs': '',
            }}, 201

        compute_mgr = get_compute_mgr(self.container_env)
        try:
            plugin_job = compute_mgr.get_job(job_id)
            plugin_info = compute_mgr.get_job_info(plugin_job)
            if plugin_info.status not in (JobStatus.finishedSuccessfully, 
                                          JobStatus.finishedWithError):
                abort(409, message=f'Plugin job has not completed yet (status: '
                                   f'{plugin_info.status.value}). The plugin '
                                   f'job must finish before uploading.')
        except ManagerException:
            abort(409, message='No plugin job found. A plugin job must '
                               'complete before scheduling an upload job.')

        upload_name = job_id + '-upload'

        exists, response = self._check_existing_job(upload_name,
                                                     jid_for_response=job_id)
        if exists:
            return response, 201

        # Write upload parameters to disk
        key_dir = os.path.join(self.storebase_mount, 'key-' + job_id)
        params = {
            'jid': job_id,
            'job_output_path': job_output_path,
        }
        params_file = os.path.join(key_dir, 'upload_params.json')
        with open(params_file, 'w') as f:
            json.dump(params, f)

        op_image = self._get_op_image()
        upload_cmd = ['python', '-m', 'pfcon.upload_worker',
                      '/share/outgoing']

        resources_dict = {
            'number_of_workers': 1,
            'cpu_limit': args.cpu_limit,
            'memory_limit': args.memory_limit,
            'gpu_limit': 0,
        }

        mounts_dict = self._build_key_mounts(job_id)
        mounts_dict['inputdir_source'] = ''  # upload worker needs no input mount
        upload_env = self._build_swift_env()

        job, d_compute = self._schedule_container(
            op_image, upload_cmd, upload_name, resources_dict, upload_env,
            mounts_dict, jid_for_response=job_id, pfcon_user=True)

        # For docker: connect to pfcon's network for Swift DNS
        if self.container_env == 'docker':
            connect_to_pfcon_networks(job, app.config.get('PFCON_SELECTOR'))

        return {'compute': d_compute}, 201


class UploadJob(BaseJob):
    """
    Resource for checking status of and deleting a single data upload job.
    """

    def get(self, job_id):
        return self._get_job_status(job_id + '-upload',
                                    jid_for_response=job_id)

    def delete(self, job_id):
        self._remove_job(job_id + '-upload')
        return '', 204


# ---------------------------------------------------------------------------
# DeleteJobList / DeleteJob
# ---------------------------------------------------------------------------

class DeleteJobList(BaseJobList):
    """
    Resource for scheduling async data deletion jobs.
    POST schedules a container that removes the job's storebase data.
    Idempotent: if the delete container already exists and hasn't failed,
    the POST returns the existing container's status.
    """

    def get(self):
        return self._get_server_info()

    def post(self):
        args = parser_delete.parse_args()
        job_id = args.jid.lstrip('/')

        logger.info(f'Received delete job request for {job_id}')

        key_dir = os.path.join(self.storebase_mount, 'key-' + job_id)

        if not os.path.isdir(key_dir):
            # Nothing to delete — return success immediately
            return {'compute': {
                'jid': job_id,
                'image': '',
                'cmd': '',
                'status': 'finishedSuccessfully',
                'message': 'deleteSkipped',
                'timestamp': '',
                'logs': '',
            }}, 201

        # Ensure no sibling jobs are still running
        non_terminal = (JobStatus.started, JobStatus.notStarted)
        compute_mgr = get_compute_mgr(self.container_env)

        for suffix, label in (('-copy', 'copy'), ('', 'plugin'),
                              ('-upload', 'upload')):
            job_name = job_id + suffix
            try:
                sibling = compute_mgr.get_job(job_name)
                sibling_info = compute_mgr.get_job_info(sibling)
                if sibling_info.status in non_terminal:
                    abort(409,
                          message=f'The {label} job is still active '
                                  f'(status: {sibling_info.status.value}). '
                                  f'All jobs must finish before scheduling '
                                  f'a delete job.')
            except ManagerException:
                pass  # job doesn't exist, safe to proceed

        delete_name = job_id + '-delete'

        exists, response = self._check_existing_job(delete_name,
                                                     jid_for_response=job_id)
        if exists:
            return response, 201

        # Write delete parameters for the worker
        params = {'jid': job_id}
        params_file = os.path.join(key_dir, 'delete_params.json')
        with open(params_file, 'w') as f:
            json.dump(params, f)

        op_image = self._get_op_image()
        delete_cmd = ['python', '-m', 'pfcon.delete_worker',
                      self.str_app_container_outputdir]

        resources_dict = {
            'number_of_workers': 1,
            'cpu_limit': args.cpu_limit,
            'memory_limit': args.memory_limit,
            'gpu_limit': 0,
        }

        mounts_dict = self._build_key_mounts(job_id)
        mounts_dict['inputdir_source'] = ''  # delete worker needs no input mount

        _, d_compute = self._schedule_container(
            op_image, delete_cmd, delete_name, resources_dict, [],
            mounts_dict, jid_for_response=job_id, pfcon_user=True)

        return {'compute': d_compute}, 201


class DeleteJob(BaseJob):
    """
    Resource for checking status of and deleting a single data delete job.
    """

    def get(self, job_id):
        response = self._get_job_status(job_id + '-delete',
                                        jid_for_response=job_id)
        if response['compute']['status'] == JobStatus.finishedSuccessfully.value:
            key_dir = os.path.join(self.storebase_mount, 'key-' + job_id)
            try:
                os.rmdir(key_dir)
            except FileNotFoundError:
                pass
            except OSError:
                logger.warning(f'Could not remove key directory {key_dir}; '
                               f'it may not be empty')
        return response

    def delete(self, job_id):
        self._remove_job(job_id + '-delete')
        return '', 204


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_app_cmd(args, args_path_flags, entrypoint, plugin_type,
                   inputdir, outputdir):
    """Build the full command for a plugin container."""
    cmd = list(entrypoint) + localize_path_args(args, args_path_flags,
                                                inputdir)
    if plugin_type == 'ds':
        cmd.append(inputdir)
    cmd.append(outputdir)
    return cmd


def localize_path_args(args: List[str], path_flags: Collection[str],
                       input_dir: str) -> List[str]:
    """
    Replace the strings following path flags with the input directory.

    https://github.com/FNNDSC/CHRIS_docs/blob/7ac85e9ae1070947e6e2cda62747b427028229b0/SPEC.adoc#path-arguments
    """
    if len(args) == 0:
        return args

    if args[0] in path_flags:
        return [args[0], input_dir] + localize_path_args(args[2:], path_flags,
                                                         input_dir)
    return args[0:1] + localize_path_args(args[1:], path_flags, input_dir)
