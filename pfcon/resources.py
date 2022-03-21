
import os
import logging
import zipfile
from datetime import datetime, timedelta
import jwt

from flask import request, send_file, current_app as app
from flask_restful import reqparse, abort, Resource

from .services import PmanService, ServiceException
from .mount_dir import MountDir
from .swift_store import SwiftStore

logger = logging.getLogger(__name__)

parser = reqparse.RequestParser(bundle_errors=True)
parser.add_argument('jid', dest='jid', required=True, location='form')
parser.add_argument('args', dest='args', required=True, type=str, action='append', location='form')
parser.add_argument('args_path_flags', dest='args_path_flags', type=str, action='append', location='form')
parser.add_argument('auid', dest='auid', required=True, location='form')
parser.add_argument('number_of_workers', dest='number_of_workers', type=int,
                    required=True, location='form')
parser.add_argument('cpu_limit', dest='cpu_limit', type=int, required=True,
                    location='form')
parser.add_argument('memory_limit', dest='memory_limit', type=int, required=True,
                    location='form')
parser.add_argument('gpu_limit', dest='gpu_limit', type=int, required=True,
                    location='form')
parser.add_argument('image', dest='image', required=True, location='form')
parser.add_argument('entrypoint', dest='entrypoint', type=str, required=True, action='append', location='form')
parser.add_argument('type', dest='type', choices=('ds', 'fs', 'ts'), required=True,
                    location='form')
parser.add_argument('data_file', dest='data_file', required=True, location='files')

parser_auth = reqparse.RequestParser(bundle_errors=True)
parser_auth.add_argument('pfcon_user', dest='pfcon_user', required=True)
parser_auth.add_argument('pfcon_password', dest='pfcon_password', required=True)


class JobList(Resource):
    """
    Resource representing the list of jobs running on the compute.
    """

    def __init__(self):
        super(JobList, self).__init__()

        self.store_env = app.config.get('STORE_ENV')

    def get(self):
        return {
            'server_version': app.config.get('SERVER_VERSION')
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
            'args': args.args,
            'args_path_flags': args.args_path_flags,
            'auid': args.auid,
            'number_of_workers': args.number_of_workers,
            'cpu_limit': args.cpu_limit,
            'memory_limit': args.memory_limit,
            'gpu_limit': args.gpu_limit,
            'image': args.image,
            'entrypoint': args.entrypoint,
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
               }, 201


class Job(Resource):
    """
    Resource representing a single job running on the compute.
    """

    def __init__(self):
        super(Job, self).__init__()

        self.store_env = app.config.get('STORE_ENV')

    def get(self, job_id):
        pman = PmanService.get_service_obj()
        try:
            d_compute_response = pman.get_job(job_id)
        except ServiceException as e:
            abort(e.code, message=str(e))
        return {
            'compute': d_compute_response
        }

    def delete(self, job_id):
        if self.store_env == 'mount':
            storebase = app.config.get('STORE_BASE')
            job_dir = os.path.join(storebase, 'key-' + job_id)
            if os.path.isdir(job_dir):
                mdir = MountDir()
                logger.info(f'Deleting job {job_id} data from store')
                mdir.delete_data(job_dir)
                logger.info(f'Successfully removed job {job_id} data from store')
        pman = PmanService.get_service_obj()
        try:
            pman.delete_job(job_id)
        except ServiceException as e:
            abort(e.code, message=str(e))
        logger.info(f'Successfully removed job {job_id} from remote compute')
        return '', 204


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

        if self.store_env == 'swift':
            swift = SwiftStore(app.config)
            content = swift.getData(job_id)

        return send_file(content, attachment_filename=f'{job_id}.zip',
                         as_attachment=True, mimetype='application/zip')


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
