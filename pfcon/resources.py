
import logging
import os

from werkzeug.utils import secure_filename
from flask import request, current_app as app
from flask_restful import reqparse, abort, Resource

from .services import PmanService, PfiohService

import  pudb
import  pfurl


logger = logging.getLogger(__name__)

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
        d_dataRequestProcessPush    = {}
        d_computeRequestProcess     = {}
        d_dataRequestProcessPull    = {}
        d_metaData                  = request.form['meta-data']
        d_metaCompute               = request.form['meta-compute']

        f = request.files['data_file']
        fname = secure_filename(f.filename)
        logger.info('Received file = %s', fname)
        pfioh = PfiohService.get_service_obj()
        f.save(os.path.join(pfioh.data_dir, fname))

        return {
            'pushData':             d_dataRequestProcessPush,
            'compute':              d_computeRequestProcess,
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
