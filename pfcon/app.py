
import os

from flask import Flask
from flask_restful import Api

from .config import DevConfig, ProdConfig
from pfcon.resources import JobList, Job, JobFile


def create_app(config=None):
    app_mode = os.environ.get("APPLICATION_MODE", default="development")
    app = Flask(__name__)

    if app_mode == 'development':
        app.config.from_object(DevConfig())
    else:
        app.config.from_object(ProdConfig())
    app.config.update(config or {})

    api = Api(app, prefix='/api/v1/')

    # url mappings
    api.add_resource(JobList, '/')
    api.add_resource(Job, '/<string:job_id>/')
    api.add_resource(JobFile, '/<string:job_id>/file/')

    return app
