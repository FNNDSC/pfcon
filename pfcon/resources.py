
import logging

from flask import request, current_app as app
from flask_restful import reqparse, abort, Resource

import  pudb
import  pfurl


logger = logging.getLogger(__name__)


JOBS = {
    'chris-jid-1': {
        'id': 'chris-jid-1',
        'status': 'API under construction'
    },
    'chris-jid-2': {
        'id': 'chris-jid-2',
        'status': 'API under construction'
    },
}


def abort_if_job_doesnt_exist(job_id):
    if job_id not in JOBS:
        abort(404, message="Job {} doesn't exist".format(job_id))


parser = reqparse.RequestParser()
parser.add_argument('cmd')


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
        logger.info('request: %s', str(request))
        return {
            'server_version': app.config.get('ver'),
            'status': 'API under construction',
        }


class Job(Resource):
    """
    Resource representing a single job running on the compute.
    """
    def get(self, job_id):
        abort_if_job_doesnt_exist(job_id)
        return JOBS[job_id]

    def delete(self, job_id):
        abort_if_job_doesnt_exist(job_id)
        del JOBS[job_id]
        return '', 204
