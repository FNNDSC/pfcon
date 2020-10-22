
import logging

from flask import request, current_app as app
from flask_restful import reqparse, abort, Resource

import  pudb
import  pfurl


logger = logging.getLogger(__name__)


class JobList(Resource):
    def get(self):
        return {'status': 'API under construction'}

    def post(self):
        logger.info('request: %s', str(request))
