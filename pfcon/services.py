
import logging
import os
from abc import ABC, abstractmethod

from flask import g, current_app as app


class Service(ABC):
    """
    Abstract base class for the coordinated services.
    """
    def __init__(self, base_url):
        super().__init__()

        # base url of the service
        self.base_url = base_url

    @abstractmethod
    def get(self):
        pass


class PmanService(Service):
    """
    Class for the pman service.
    """
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

    def get(self):
        super().get()
        print("The enrichment from PmanService")

    def get_jobs(self):
        return self.JOBS

    def get_job(self, job_id):
        return self.JOBS[job_id]

    def delete_job(self, job_id):
        del self.JOBS[job_id]

    @staticmethod
    def get_service_obj():
        if 'pman' not in g:
            g.pman = PmanService(app.config.get('COMPUTE_SERVICE_URL'))
        return g.pman


class PfiohService(Service):
    """
    Class for the pfioh service.
    """
    def __init__(self, base_url):
        super().__init__(base_url)

        # local data dir to store zip files before transmitting to the remote
        self.data_dir = os.path.join(os.path.expanduser("~"), 'data')

    def get(self):
        super().get()
        print("The enrichment from PfiohService")

    @staticmethod
    def get_service_obj():
        if 'pfioh' not in g:
            g.pfioh = PfiohService(app.config.get('DATA_SERVICE_URL'))
        return g.pfioh
