
import logging

from flask import request, Response, current_app as app
from flask_restful import reqparse, abort, Resource

from .services import PmanService, PfiohService, ServiceException


logger = logging.getLogger(__name__)

parser = reqparse.RequestParser()
parser.add_argument('jid')


class JobList(Resource):
    """
    Resource representing the list of jobs running on the compute.
    """
    def get(self):
        return {
            'server_version': app.config.get('ver'),
        }

    def post(self):
        job_id = request.form['jid']
        compute_data = {
            'cmd': request.form.get('cmd'),
            'auid': request.form.get('auid'),
            'number_of_workers': request.form.get('number_of_workers'),
            'cpu_limit': request.form.get('cpu_limit'),
            'memory_limit': request.form.get('memory_limit'),
            'gpu_limit': request.form.get('gpu_limit'),
            'image': request.form.get('image'),
            'selfexec': request.form.get('selfexec'),
            'selfpath': request.form.get('selfpath'),
            'execshell': request.form.get('execshell'),
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
