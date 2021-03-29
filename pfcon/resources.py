
import os
import logging
import zipfile

from flask import request, Response, current_app as app
from flask_restful import reqparse, abort, Resource

from .services import PmanService, ServiceException
from .mount_dir import MountDir
from .swift_store import SwiftStore

logger = logging.getLogger(__name__)

parser = reqparse.RequestParser(bundle_errors=True)
parser.add_argument('jid', dest='jid', required=True, location='form')
parser.add_argument('cmd_args', dest='cmd_args', required=True, location='form')
parser.add_argument('cmd_path_flags', dest='cmd_path_flags', location='form')
parser.add_argument('auid', dest='auid', required=True, location='form')
parser.add_argument('number_of_workers', dest='number_of_workers', required=True,
                    location='form')
parser.add_argument('cpu_limit', dest='cpu_limit', required=True, location='form')
parser.add_argument('memory_limit', dest='memory_limit', required=True, location='form')
parser.add_argument('gpu_limit', dest='gpu_limit', required=True, location='form')
parser.add_argument('image', dest='image', required=True, location='form')
parser.add_argument('selfexec', dest='selfexec', required=True, location='form')
parser.add_argument('selfpath', dest='selfpath', required=True, location='form')
parser.add_argument('execshell', dest='execshell', required=True, location='form')
parser.add_argument('type', dest='type', choices=('ds', 'fs', 'ts'), required=True,
                    location='form')
parser.add_argument('data_file', dest='data_file', required=True, location='files')


class JobList(Resource):
    """
    Resource representing the list of jobs running on the compute.
    """

    def __init__(self):
        super(JobList, self).__init__()

        self.store_env = app.config.get('STORE_ENV')

    def get(self):
        return {
            'server_version': app.config.get('SERVER_VERSION'),
        }

    def post(self):
        args = parser.parse_args()
        job_id = args.jid.lstrip('/')

        # process data
        if self.store_env == 'mount':
            storebase = app.config.get('STORE_BASE')
            job_dir = os.path.join(storebase, 'key-' + job_id)
            incoming_dir = os.path.join(job_dir, 'incoming')
            outgoing_dir = os.path.join(job_dir, 'outgoing')
            os.makedirs(incoming_dir, exist_ok=True)
            os.makedirs(outgoing_dir, exist_ok=True)
            mdir = MountDir(app.config)

            logger.info(f'Received job {job_id}')
            try:
                d_info = mdir.store_data(job_id, incoming_dir, request.files['data_file'])
            except zipfile.BadZipFile as e:
                logger.error(f'Error while decompressing and storing job {job_id} data, '
                             f'detail: {str(e)}')
                abort(400, message='data_file: Bad zip file')
                
        if self.store_env == 'swift':
            swift = SwiftStore(app.config)
            d_info = swift.storeData(job_id, 'incoming', request.files['data_file'])
            
        logger.info(f'Successfully stored job {job_id} input data')

        # process compute
        compute_data = {
            'cmd_args': args.cmd_args,
            'cmd_path_flags': args.cmd_path_flags,
            'auid': args.auid,
            'number_of_workers': args.number_of_workers,
            'cpu_limit': args.cpu_limit,
            'memory_limit': args.memory_limit,
            'gpu_limit': args.gpu_limit,
            'image': args.image,
            'selfexec': args.selfexec,
            'selfpath': args.selfpath,
            'execshell': args.execshell,
            'type': args.type,
        }
        pman = PmanService.get_service_obj()
        try:
            d_compute_response = pman.run_job(job_id, compute_data)
        except ServiceException as e:
            abort(e.code, message=str(e))

        return {
            'data': d_info,
            'compute': d_compute_response
        }


class Job(Resource):
    """
    Resource representing a single job running on the compute.
    """
    def get(self, job_id):
        pman = PmanService.get_service_obj()
        try:
            d_compute_response = pman.get_job(job_id)
        except ServiceException as e:
            abort(e.code, message=str(e))
        return {
            'compute': d_compute_response
        }


class JobFile(Resource):
    """
    Resource representing a single job data for a job running on the compute.
    """
    def __init__(self):
        super(JobFile, self).__init__()

        self.store_env = app.config.get('STORE_ENV')

    def get(self, job_id):
        if self.store_env == 'mount':
            storebase = app.config.get('STORE_BASE')
            job_dir = os.path.join(storebase, 'key-' + job_id)
            if not os.path.isdir(job_dir):
                abort(404)
            outgoing_dir = os.path.join(job_dir, 'outgoing')
            if not os.path.exists(outgoing_dir):
                os.mkdir(outgoing_dir)
            mdir = MountDir(app.config)
            logger.info(f'Retrieving job {job_id} output data')
            content = mdir.get_data(job_id, outgoing_dir)
            logger.info(f'Successfully retrieved job {job_id} output data')
        return Response(content, mimetype='application/zip')

    def delete(self, job_id):
        if self.store_env == 'mount':
            storebase = app.config.get('STORE_BASE')
            job_dir = os.path.join(storebase, 'key-' + job_id)
            if not os.path.isdir(job_dir):
                abort(404)
            mdir = MountDir()
            logger.info(f'Deleting job {job_id} data from store')
            mdir.delete_data(job_dir)
            logger.info(f'Successfully removed job {job_id} data from store')
