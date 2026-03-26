
import os

from flask import Flask, request
from flask_restful import Api

from .config import DevConfig, ProdConfig
from pfcon.resources import (
    HealthCheck, Auth,
    PluginJobList, PluginJob, PluginJobFile,
    CopyJobList, CopyJob,
    UploadJobList, UploadJob,
    DeleteJobList, DeleteJob,
)


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

    # Client-managed job routes
    api.add_resource(PluginJobList, '/pluginjobs/', endpoint='api.pluginjoblist')
    api.add_resource(PluginJob, '/pluginjobs/<string:job_id>/', endpoint='api.pluginjob')
    api.add_resource(PluginJobFile, '/pluginjobs/<string:job_id>/file/', endpoint='api.pluginjobfile')
    api.add_resource(CopyJobList, '/copyjobs/', endpoint='api.copyjoblist')
    api.add_resource(CopyJob, '/copyjobs/<string:job_id>/', endpoint='api.copyjob')
    api.add_resource(UploadJobList, '/uploadjobs/', endpoint='api.uploadjoblist')
    api.add_resource(UploadJob, '/uploadjobs/<string:job_id>/', endpoint='api.uploadjob')
    api.add_resource(DeleteJobList, '/deletejobs/', endpoint='api.deletejoblist')
    api.add_resource(DeleteJob, '/deletejobs/<string:job_id>/', endpoint='api.deletejob')

    return app
