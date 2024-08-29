
import os
import logging
import zipfile
from datetime import datetime, timedelta
import jwt

from flask import request, send_file, current_app as app
from flask_restful import reqparse, abort, Resource
from swiftclient.exceptions import ClientException

from .services import PmanService, ServiceException
from .zip_file_storage import ZipFileStorage
from .swift_storage import SwiftStorage
from .filesystem_storage import FileSystemStorage
from .fslink_storage import FSLinkStorage


logger = logging.getLogger(__name__)

parser = reqparse.RequestParser(bundle_errors=True)
parser.add_argument('jid', dest='jid', required=True, location='form')
parser.add_argument('args', dest='args', required=True, type=str, action='append',
                    location='form', default=[])
parser.add_argument('args_path_flags', dest='args_path_flags', type=str, action='append',
                    location='form', default=[])
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
parser.add_argument('entrypoint', dest='entrypoint', type=str, required=True,
                    action='append', location='form')
parser.add_argument('type', dest='type', choices=('ds', 'fs', 'ts'), required=True,
                    location='form')
parser.add_argument('env', dest='env', type=str, action='append', location='form',
                    default=[])

parser.add_argument('input_dirs', dest='input_dirs', required=False, type=str,
                    action='append', location='form')
parser.add_argument('output_dir', dest='output_dir', required=False, location='form')
parser.add_argument('data_file', dest='data_file', required=False, location='files')

parser_auth = reqparse.RequestParser(bundle_errors=True)
parser_auth.add_argument('pfcon_user', dest='pfcon_user', required=True)
parser_auth.add_argument('pfcon_password', dest='pfcon_password', required=True)


class JobList(Resource):
    """
    Resource representing the list of jobs running on the compute environment.
    """

    def __init__(self):
        super(JobList, self).__init__()

        self.storage_env = app.config.get('STORAGE_ENV')
        self.pfcon_innetwork = app.config.get('PFCON_INNETWORK')
        self.storebase_mount = app.config.get('STOREBASE_MOUNT')

    def get(self):
        response = {
            'server_version': app.config.get('SERVER_VERSION'),
            'pfcon_innetwork': self.pfcon_innetwork,
            'storage_env': self.storage_env
        }
        if self.pfcon_innetwork:
            if self.storage_env == 'swift':
                auth_url =  app.config['SWIFT_CONNECTION_PARAMS']['authurl']
                response['swift_auth_url'] = auth_url
        return response

    def post(self):
        args = parser.parse_args()

        if self.pfcon_innetwork:
            if args.input_dirs is None:
                abort(400, message='input_dirs: field is required')
            if args.output_dir is None:
                abort(400, message='output_dir: field is required')
        else:
            if request.files['data_file'] is None:
                abort(400, message='data_file: field is required')

        job_id = args.jid.lstrip('/')
        logger.info(f'Received job {job_id}')

        # process data

        input_dir = 'key-' + job_id + '/incoming'
        output_dir = 'key-' + job_id + '/outgoing'

        if self.pfcon_innetwork and self.storage_env == 'filesystem':
            # only the first input dir is considered here
            input_dir = args.input_dirs[0].strip('/')
            output_dir = args.output_dir.strip('/')
            incoming_dir = os.path.join(self.storebase_mount, input_dir)

            storage = FileSystemStorage(app.config)
            try:
                d_info = storage.store_data(job_id, incoming_dir, None)
            except Exception as e:
                logger.error(f'Error while accessing files from shared filesystem '
                             f'for job {job_id}, detail: {str(e)}')
                abort(400,
                      message='input_dirs: Error accessing files from shared filesystem')
        else:
            incoming_dir = os.path.join(self.storebase_mount, input_dir)
            os.makedirs(incoming_dir, exist_ok=True)

            if self.pfcon_innetwork:
                if self.storage_env == 'swift':
                    outgoing_dir = os.path.join(self.storebase_mount, output_dir)
                    os.makedirs(outgoing_dir, exist_ok=True)

                    storage = SwiftStorage(app.config)
                    try:
                        d_info = storage.store_data(job_id, incoming_dir, args.input_dirs,
                                                    job_output_path=args.output_dir.strip('/'))
                    except ClientException as e:
                        logger.error(f'Error while fetching files from swift and '
                                     f'storing job {job_id} data, detail: {str(e)}')
                        abort(400,
                              message='input_dirs: Error fetching files from swift')

                elif self.storage_env == 'fslink':
                    output_dir = args.output_dir.strip('/')
                    storage = FSLinkStorage(app.config)
                    try:
                        d_info = storage.store_data(job_id, incoming_dir, args.input_dirs,
                                                    job_output_path=output_dir)
                    except Exception as e:
                        logger.error(f'Error while accessing files from shared filesystem '
                                     f'and storing job {job_id} data, detail: {str(e)}')
                        abort(400,
                              message='input_dirs: Error copying files from shared filesystem')
            else:
                if self.storage_env == 'zipfile':
                    outgoing_dir = os.path.join(self.storebase_mount, output_dir)
                    os.makedirs(outgoing_dir, exist_ok=True)

                    storage = ZipFileStorage(app.config)
                    data_file = request.files['data_file']
                    try:
                        d_info = storage.store_data(job_id, incoming_dir, data_file)
                    except zipfile.BadZipFile as e:
                        logger.error(f'Error while decompressing and storing job {job_id} '
                                     f'data, detail: {str(e)}')
                        abort(400, message='data_file: Bad zip file')

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
            'env': args.env,
            'input_dir': input_dir,
            'output_dir': output_dir,
        }
        pman = PmanService.get_service_obj()
        try:
            d_compute_response = pman.run_job(job_id, compute_data)
        except ServiceException as e:
            abort(e.code, message=str(e))

        return {'data': d_info, 'compute': d_compute_response}, 201


class Job(Resource):
    """
    Resource representing a single job running on the compute environment.
    """

    def __init__(self):
        super(Job, self).__init__()

        self.storage_env = app.config.get('STORAGE_ENV')
        self.pfcon_innetwork = app.config.get('PFCON_INNETWORK')
        self.storebase_mount = app.config.get('STOREBASE_MOUNT')

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
        storage = None

        if self.pfcon_innetwork:
            if self.storage_env == 'filesystem':
                storage = FileSystemStorage(app.config)

            elif self.storage_env == 'swift':
                storage = SwiftStorage(app.config)

            elif self.storage_env == 'fslink':
                storage = FSLinkStorage(app.config)
        else:
            if self.storage_env == 'zipfile':
                storage = ZipFileStorage(app.config)

        job_dir = os.path.join(self.storebase_mount, 'key-' + job_id)
        if os.path.isdir(job_dir):
            logger.info(f'Deleting job {job_id} data from store')
            storage.delete_data(job_dir)
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
    Resource representing a single job data for a job running on the compute environment.
    """

    def __init__(self):
        super(JobFile, self).__init__()

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

        else:
            job_dir = os.path.join(self.storebase_mount, 'key-' + job_id)
            if not os.path.isdir(job_dir):
                abort(404)
            outgoing_dir = os.path.join(job_dir, 'outgoing')
            if not os.path.exists(outgoing_dir):
                os.mkdir(outgoing_dir)

            logger.info(f'Retrieving job {job_id} output data')

            if self.pfcon_innetwork:
                job_output_path = request.args.get('job_output_path')

                if job_output_path:
                    job_output_path = job_output_path.lstrip('/')

                    if self.storage_env == 'swift':
                        storage = SwiftStorage(app.config)
                        content = storage.get_data(job_id, outgoing_dir,
                                                   job_output_path=job_output_path)
                        download_name = f'{job_id}.json'
                        mimetype = 'application/json'
                else:
                    # if no query parameter passed then the job's zip file is returned
                    storage = ZipFileStorage(app.config)
                    content = storage.get_data(job_id, outgoing_dir)
            else:
                if self.storage_env == 'zipfile':
                    storage = ZipFileStorage(app.config)
                    content = storage.get_data(job_id, outgoing_dir)

            logger.info(f'Successfully retrieved job {job_id} output data')

        return send_file(content, download_name=download_name, as_attachment=True,
                         mimetype=mimetype)


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
