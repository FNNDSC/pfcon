
import os

from flask import Flask
from flask_restful import Api

from .config import DevConfig, ProdConfig
from pfcon.resources import JobList, Job, JobFile


def create_app(config_dict=None):
    app_mode = os.environ.get("APPLICATION_MODE", default="production")
    if app_mode == 'production':
        config_obj = ProdConfig()
    else:
        config_obj = DevConfig()

    app = Flask(__name__)
    app.config.from_object(config_obj)
    app.config.update(config_dict or {})

    api = Api(app, prefix='/api/v1/')

    # url mappings
    api.add_resource(JobList, '/', endpoint='api.joblist')
    api.add_resource(Job, '/<string:job_id>/', endpoint='api.job')
    api.add_resource(JobFile, '/<string:job_id>/file/', endpoint='api.jobfile')

    return app
