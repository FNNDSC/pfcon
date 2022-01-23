
import os

from flask import Flask, request
from flask_restful import Api

from .config import DevConfig, ProdConfig
from pfcon.resources import HealthCheck, JobList, Job, JobFile, Auth


def create_app(config_dict=None):
    app_mode = os.environ.get("APPLICATION_MODE", default="production")
    if app_mode == 'production':
        config_obj = ProdConfig()
    else:
        config_obj = DevConfig()

    app = Flask(__name__)
    app.config.from_object(config_obj)
    app.config.update(config_dict or {})

    @app.before_request
    def hook():
        if request.endpoint and request.endpoint not in ('api.auth', 'api.healthcheck'):
            Auth.check_token()

    api = Api(app, prefix='/api/v1/')

    # url mappings
    api.add_resource(HealthCheck, '/health/', endpoint='api.healthcheck')
    api.add_resource(Auth, '/auth-token/', endpoint='api.auth')
    api.add_resource(JobList, '/jobs/', endpoint='api.joblist')
    api.add_resource(Job, '/jobs/<string:job_id>/', endpoint='api.job')
    api.add_resource(JobFile, '/jobs/<string:job_id>/file/', endpoint='api.jobfile')

    return app
