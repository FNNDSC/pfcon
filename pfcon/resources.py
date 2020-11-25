
import logging

from flask import request, Response, current_app as app
from flask_restful import reqparse, abort, Resource

from .services import PmanService, PfiohService, ServiceException


logger = logging.getLogger(__name__)

parser = reqparse.RequestParser(bundle_errors=True)
parser.add_argument('jid', dest='jid', required=True, location='form')
parser.add_argument('cmd', dest='cmd', required=True, location='form')
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


class JobList(Resource):
    """
    Resource representing the list of jobs running on the compute.
    """
    def get(self):
        logger.info('got GET request')
        return {
            'server_version': app.config.get('SERVER_VERSION'),
        }

    def post(self):
        args = parser.parse_args()
        job_id = args.jid
        compute_data = {
            'cmd': args.cmd,
            'auid': args.auid,
            'number_of_workers': args.number_of_workers,
            'cpu_limit': args.cpu_limit,
            'memory_limit': args.memory_limit,
            'gpu_limit': args.gpu_limit,
            'image': args.image,
            'selfexec': args.selfexec,
            'selfpath': args.selfpath,
            'execshell': args.execshell,
        }
        f = request.files['data_file']
        pfioh = PfiohService.get_service_obj()
        try:
            d_data_push_response = pfioh.push_data(job_id, f)
        except ServiceException as e:
            abort(503, message=str(e))  # 503 Service Unavailable (pfioh)
        pman = PmanService.get_service_obj()
        data_share_dir = d_data_push_response['postop']['shareDir']
        try:
            d_compute_response = pman.run_job(job_id, compute_data, data_share_dir)
        except ServiceException as e:
            abort(503, message=str(e))  # 503 Service Unavailable (pman)
        return {
            'pushData': d_data_push_response,
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
            abort(503, message=str(e))  # 503 Service Unavailable (pman)
        if not d_compute_response['status']:
            abort(404, message="Not found.")  # 404 Not Found (job not found)
        return {
            'compute': d_compute_response
        }


class JobFile(Resource):
    """
    Resource representing a job's data file.
    """
    def get(self, job_id):
        pfioh = PfiohService.get_service_obj()
        try:
            data_pull_content = pfioh.pull_data(job_id)
        except ServiceException as e:
            abort(404, message=str(e))  # 404 Not Found (job file not found)
        return Response(
            data_pull_content,
            mimetype='application/zip'
        )
