
import logging
import json

from flask import request, current_app as app
from flask_restful import reqparse, abort, Resource

from .services import PmanService, PfiohService

import pudb


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
            'status': 'API under construction',
        }

    def post(self):
        d_compute_response = {}
        d_dataRequestProcessPull    = {}
        msg = request.form['msg']
        d_msg = json.loads(msg)
        d_meta_data = d_msg['meta-data']
        d_meta_compute  = d_msg['meta-compute']
        job_id = d_msg['jid']
        f = request.files['data_file']
        pfioh = PfiohService.get_service_obj()
        d_data_push_response = pfioh.push_data(job_id, f)
        if d_data_push_response['status']:
            pman = PmanService.get_service_obj()
            data_share_dir = d_data_push_response['remoteServer']['postop']['shareDir']
            d_compute_response = pman.compute(job_id, d_meta_compute, data_share_dir)


        return {
            'pushData':             d_data_push_response,
            'compute':              d_compute_response,
            'pullData':             d_dataRequestProcessPull,
            'd_jobStatus':          {},
            'd_jobStatusSummary':   {}
        }


class Job(Resource):
    """
    Resource representing a single job running on the compute.
    """
    def get(self, job_id):
        pman = PmanService.get_service_obj()
        try:
            job = pman.get_job(job_id)
        except KeyError:
            abort(404, message="Job {} doesn't exist".format(job_id))
        return job

    def delete(self, job_id):
        pman = PmanService.get_service_obj()
        try:
            pman.delete_job(job_id)
        except KeyError:
            abort(404, message="Job {} doesn't exist".format(job_id))
        return '', 204
