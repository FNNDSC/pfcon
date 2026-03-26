"""
Shared base classes for pfcon API resources.

Provides common initialization, container scheduling, status querying,
and container removal logic that all job-type resources reuse.
"""

import os
import logging

from flask import current_app as app
from flask_restful import abort, Resource

from .compute.abstractmgr import ManagerException, JobStatus
from .compute.container_user import ContainerUser
from .compute.dockermgr import DockerManager
from .compute.kubernetesmgr import KubernetesManager
from .compute.swarmmgr import SwarmManager


logger = logging.getLogger(__name__)


def get_compute_mgr(container_env):
    if container_env in ('docker', 'podman'):
        return DockerManager(app.config)
    elif container_env == 'swarm':
        return SwarmManager(app.config)
    elif container_env in ('kubernetes', 'openshift'):
        return KubernetesManager(app.config)
    elif container_env == 'cromwell':
        raise ValueError('cromwell not supported')
    return None


class BaseJobList(Resource):
    """
    Base class for job-list resources that schedule containers.
    Provides shared __init__, mount building, swift env building,
    and container scheduling.
    """

    def __init__(self):
        super().__init__()

        self.storage_env = app.config.get('STORAGE_ENV')
        self.pfcon_innetwork = app.config.get('PFCON_INNETWORK')
        self.storebase_mount = app.config.get('STOREBASE_MOUNT')
        self.container_env = app.config.get('CONTAINER_ENV')
        self.compute_volume_type = app.config.get('COMPUTE_VOLUME_TYPE')
        self.user = ContainerUser.parse(app.config.get('CONTAINER_USER'))

        self.job_logs_tail = app.config.get('JOB_LOGS_TAIL')
        self.str_app_container_inputdir = '/share/incoming'
        self.str_app_container_outputdir = '/share/outgoing'

    def _get_server_info(self):
        """Return server metadata dict (reused by GET on all list resources)."""
        response = {
            'server_version': app.config.get('SERVER_VERSION'),
            'pfcon_innetwork': self.pfcon_innetwork,
            'storage_env': self.storage_env,
            'requires_copy_job': False,
            'requires_upload_job': False,
            'container_env': self.container_env,
            'compute_volume_type': self.compute_volume_type,
        }
        if self.pfcon_innetwork and self.storage_env in ('fslink', 'swift'):
            response['requires_copy_job'] = True
        
        if self.pfcon_innetwork and self.storage_env == 'swift':
            response['requires_upload_job'] = True
            response['swift_auth_url'] = (
                app.config['SWIFT_CONNECTION_PARAMS']['authurl'])
        return response

    def _build_key_mounts(self, job_id, inputdir_source_override=None):
        """
        Build a mounts_dict for containers that mount the storebase key
        directory. Handles host, docker_local_volume, and kubernetes_pvc
        volume types.

        If inputdir_source_override is given it replaces the default
        inputdir_source (used e.g. for fslink copy where inputdir is the
        storebase root).
        """
        mounts_dict = {
            'inputdir_source': '',
            'inputdir_target': self.str_app_container_inputdir,
            'outputdir_source': '',
            'outputdir_target': self.str_app_container_outputdir,
        }
        key_subpath = 'key-' + job_id

        if self.compute_volume_type in ('host', 'docker_local_volume'):
            storebase = app.config.get('STOREBASE')
            if inputdir_source_override is not None:
                mounts_dict['inputdir_source'] = inputdir_source_override
            else:
                mounts_dict['inputdir_source'] = os.path.join(storebase,
                                                              key_subpath)
            mounts_dict['outputdir_source'] = os.path.join(storebase,
                                                           key_subpath)
        elif self.compute_volume_type == 'kubernetes_pvc':
            if inputdir_source_override is not None:
                mounts_dict['inputdir_source'] = inputdir_source_override
            else:
                mounts_dict['inputdir_source'] = key_subpath
            mounts_dict['outputdir_source'] = key_subpath

        return mounts_dict

    def _build_swift_env(self):
        """Return env var list with Swift credentials for op containers."""
        swift_params = app.config.get('SWIFT_CONNECTION_PARAMS')
        swift_container = app.config.get('SWIFT_CONTAINER_NAME')
        return [
            f'SWIFT_AUTH_URL={swift_params["authurl"]}',
            f'SWIFT_USERNAME={swift_params["user"]}',
            f'SWIFT_KEY={swift_params["key"]}',
            f'SWIFT_CONTAINER_NAME={swift_container}',
        ]

    def _schedule_container(self, image, cmd, job_name, resources_dict,
                            env_vars, mounts_dict, jid_for_response=None,
                            pfcon_user=False):
        """
        Schedule a container on the compute cluster and return the standard
        response dict.

        If pfcon_user is True the container runs as the same uid/gid as the
        pfcon process itself (useful for the delete worker so that it has the
        same filesystem permissions as the process that created the data).
        """
        jid = jid_for_response or job_name

        logger.info(f'Scheduling job {job_name} on the '
                    f'{self.container_env} cluster')

        if pfcon_user:
            uid = os.getuid()
            gid = os.getgid()
        else:
            uid = self.user.get_uid()
            gid = self.user.get_gid()

        compute_mgr = get_compute_mgr(self.container_env)
        try:
            job = compute_mgr.schedule_job(image, cmd, job_name,
                                           resources_dict, env_vars,
                                           uid, gid, mounts_dict)
        except ManagerException as e:
            logger.error(f'Error from {self.container_env} while scheduling '
                         f'job {job_name}, detail: {str(e)}')
            abort(e.status_code, message=str(e))

        job_info = compute_mgr.get_job_info(job)

        logger.info(f'Successful job {job_name} schedule response from '
                    f'{self.container_env}: {job_info}')

        return job, {
            'jid': jid,
            'image': job_info.image,
            'cmd': job_info.cmd,
            'status': job_info.status.value,
            'message': job_info.message,
            'timestamp': job_info.timestamp,
            'logs': ''
        }

    def _get_op_image(self):
        """Get the PFCON_OP_IMAGE, aborting with 500 if not configured."""
        op_image = app.config.get('PFCON_OP_IMAGE')
        if not op_image:
            abort(500, message='PFCON_OP_IMAGE must be configured for '
                               'async operation jobs')
        return op_image


    def _check_existing_job(self, job_name, jid_for_response=None):
        """
        Idempotency check: if a container with job_name already exists,
        return (True, response_dict) for running/succeeded jobs, or
        remove it and return (False, None) for failed jobs.
        Returns (False, None) if the job doesn't exist.
        """
        jid = jid_for_response or job_name
        compute_mgr = get_compute_mgr(self.container_env)

        try:
            job = compute_mgr.get_job(job_name)
            job_info = compute_mgr.get_job_info(job)

            if job_info.status in (JobStatus.finishedWithError,
                                   JobStatus.undefined):
                compute_mgr.remove_job(job)
                logger.info(f'Removed failed job {job_name}, '
                            f'will re-schedule')
                return False, None

            logger.info(f'Job {job_name} already exists '
                        f'(status: {job_info.status.value})')
            job_logs = compute_mgr.get_job_logs(job, self.job_logs_tail)
            if isinstance(job_logs, bytes):
                job_logs = job_logs.decode(encoding='utf-8',
                                           errors='replace')

            return True, {'compute': {
                'jid': jid,
                'image': job_info.image,
                'cmd': job_info.cmd,
                'status': job_info.status.value,
                'message': job_info.message,
                'timestamp': job_info.timestamp,
                'logs': job_logs,
            }}
        except ManagerException:
            return False, None


class BaseJob(Resource):
    """
    Base class for single-job resources that check status and remove
    containers.
    """

    def __init__(self):
        super().__init__()

        self.storage_env = app.config.get('STORAGE_ENV')
        self.pfcon_innetwork = app.config.get('PFCON_INNETWORK')
        self.storebase_mount = app.config.get('STOREBASE_MOUNT')
        self.container_env = app.config.get('CONTAINER_ENV')
        self.compute_mgr = get_compute_mgr(self.container_env)
        self.job_logs_tail = app.config.get('JOB_LOGS_TAIL')

    def _get_job_status(self, job_name, jid_for_response=None):
        """
        Query the compute manager for a container's status and return
        the standard response dict: {'compute': {...}}.
        """
        jid = jid_for_response or job_name

        logger.info(f'Getting job {job_name} status from the '
                    f'{self.container_env} cluster')
        try:
            job = self.compute_mgr.get_job(job_name)
        except ManagerException as e:
            abort(e.status_code, message=str(e))

        job_info = self.compute_mgr.get_job_info(job)

        logger.info(f'Successful job {job_name} status response from '
                    f'{self.container_env}: {job_info}')

        job_logs = self.compute_mgr.get_job_logs(job, self.job_logs_tail)
        if isinstance(job_logs, bytes):
            job_logs = job_logs.decode(encoding='utf-8', errors='replace')

        return {'compute': {
            'jid': jid,
            'image': job_info.image,
            'cmd': job_info.cmd,
            'status': job_info.status.value,
            'message': job_info.message,
            'timestamp': job_info.timestamp,
            'logs': job_logs,
        }}

    def _remove_job(self, job_name):
        """
        Remove a container by name from the compute cluster.
        Silently ignores if the container doesn't exist.
        Returns True if removed, False if not found.
        """
        if not app.config.get('REMOVE_JOBS'):
            logger.info(f'Not deleting job {job_name} from '
                        f'{self.container_env} because '
                        f'config.REMOVE_JOBS=no')
            return False

        try:
            job = self.compute_mgr.get_job(job_name)
            self.compute_mgr.remove_job(job)
            logger.info(f'Successfully removed job {job_name} from '
                        f'remote compute')
            return True
        except ManagerException:
            return False
