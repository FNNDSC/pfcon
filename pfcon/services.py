
import logging
import json
from abc import ABC, abstractmethod
import requests
from requests.exceptions import Timeout, RequestException

from flask import g, current_app as app
from werkzeug.utils import secure_filename


logger = logging.getLogger(__name__)


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

    def compute(self, job_id, d_meta_compute, data_share_dir):
        d_msg = {
            "action": "run",
            "meta": d_meta_compute
        }
        d_msg['meta']['container']['manager']['env']['shareDir'] = data_share_dir
        logger.info('sending cmd to pman service at -->%s<--', self.base_url)
        logger.info('message sent: %s', json.dumps(d_msg, indent=4))

        try:
            r = requests.post(self.base_url,
                              data={'payload': json.dumps(d_msg)},
                              timeout=30)
        except (Timeout, RequestException) as e:
            logging.error('fatal error in talking to pman service, detail: %s' % str(e))
            return {"status": False,  "remoteServer": {}}

        d_response = r.json()
        logger.info('response from pman: %s', json.dumps(d_response, indent=4))
        return {"status": True, "remoteServer": d_response}


    @staticmethod
    def get_service_obj():
        if 'pman' not in g:
            g.pman = PmanService(app.config.get('COMPUTE_SERVICE_URL'))
        return g.pman


class PfiohService(Service):
    """
    Class for the pfioh service.
    """
    def get(self):
        super().get()
        print("The enrichment from PfiohService")

    def push_data(self, job_id, file_obj):
        """
        Push zip data file to pfioh.
        """
        fname = secure_filename(file_obj.filename)
        d_msg = {
            "action": "pushPath",
            "meta": {
                "remote": {"key": job_id},
                "local": {"path": fname},
                "specialHandling": {
                    "op": "plugin",
                    "cleanup": True
                },
                "transport": {
                    "mechanism": "compress",
                    "compress": {
                        "archive":  "zip",
                        "unpack": True,
                        "cleanup":  True
                    }
                }
            }
        }
        logger.info('sending data to pfioh service at -->%s<--', self.base_url)
        logger.info('message sent: %s', json.dumps(d_msg, indent=4))

        try:
            r = requests.post(self.base_url,
                              files={'local': file_obj},
                              data={'d_msg': json.dumps(d_msg), 'filename': fname},
                              headers={'Mode': 'file'},
                              timeout=30)
        except (Timeout, RequestException) as e:
            logging.error('fatal error in talking to pfioh service, detail: %s' % str(e))
            return {"status": False,  "remoteServer": {}}

        d_response = r.json()
        logger.info('response from pfioh: %s', json.dumps(d_response, indent=4))
        return {"status": True, "remoteServer": d_response}

    @staticmethod
    def get_service_obj():
        if 'pfioh' not in g:
            g.pfioh = PfiohService(app.config.get('DATA_SERVICE_URL'))
        return g.pfioh
