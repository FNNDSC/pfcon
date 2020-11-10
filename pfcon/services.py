
import logging
import json
import urllib.parse
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


class PmanService(Service):
    """
    Class for the pman service.
    """

    def run_job(self, job_id, d_meta_compute, data_share_dir):
        """
        Run process job on the compute environment ('run' action on pman).
        """
        d_msg = {
            "action": "run",
            "meta": d_meta_compute
        }
        d_msg['meta']['container']['manager']['env']['shareDir'] = data_share_dir
        logger.info('sending cmd to pman service at -->%s<--', self.base_url)
        logger.info('message sent: %s', json.dumps(d_msg, indent=4))

        headers = {
            'Mode': 'control',
            'Authorization': 'bearer password'
        }
        try:
            r = requests.post(self.base_url,
                              headers=headers,
                              data=json.dumps({'payload': d_msg}),
                              timeout=30)
        except (Timeout, RequestException) as e:
            logging.error('fatal error in talking to pman service, detail: %s' % str(e))
            return {"status": False}

        d_response = r.json()
        logger.info('response from pman: %s', json.dumps(d_response, indent=4))
        return {"status": True, "remoteServer": d_response}

    def get_job(self, job_id):
        """
        Get job info from the compute environment ('status' action on pman).
        """
        d_msg = {
            "action": "status",
            "meta": {
                "key": "jid",
                "value": job_id
            }
        }
        logger.info('sending cmd to pman service at -->%s<--', self.base_url)
        logger.info('message sent: %s', json.dumps(d_msg, indent=4))

        headers = {
            'Mode': 'control',
            'Authorization': 'bearer password'
        }
        try:
            r = requests.post(self.base_url,
                              headers=headers,
                              data=json.dumps({'payload': d_msg}),
                              timeout=30)
        except (Timeout, RequestException) as e:
            logging.error('fatal error in talking to pman service, detail: %s' % str(e))
            return {"status": False}

        d_response = r.json()
        logger.info('response from pman: %s', json.dumps(d_response, indent=4))
        return {"status": True, "remoteServer": d_response}

    def delete_job(self, job_id):
        pass

    @classmethod
    def get_service_obj(cls):
        if 'pman' not in g:
            g.pman = cls(app.config.get('COMPUTE_SERVICE_URL'))
        return g.pman


class PfiohService(Service):
    """
    Class for the pfioh service.
    """

    def push_data(self, job_id, file_obj):
        """
        Push zip data file to pfioh ('pushPath' action on pfioh).
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
        logger.info('sending PUSH data request to pfioh at -->%s<--', self.base_url)
        logger.info('message sent: %s', json.dumps(d_msg, indent=4))

        try:
            r = requests.post(self.base_url,
                              files={'local': file_obj},
                              data={'d_msg': json.dumps(d_msg), 'filename': fname},
                              headers={'Mode': 'file'},
                              timeout=30)
        except (Timeout, RequestException) as e:
            logging.error('fatal error in talking to pfioh service, detail: %s' % str(e))
            return {"status": False}

        d_response = r.json()
        logger.info('response from pfioh: %s', json.dumps(d_response, indent=4))
        return {"status": True, "remoteServer": d_response}

    def pull_data(self, job_id):
        """
        Pull zip data file from pfioh ('pullPath' action on pfioh).
        """
        d_msg = {
            "action": "pullPath",
            "meta": {
                "remote": {"key": job_id},
                "local": {
                    "path": "/tmp/sbin/%s" % job_id,
                    "createDir": True
                },
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
        query = urllib.parse.urlencode(d_msg)

        logger.info('sending PULL data request to pfioh at -->%s<--', self.base_url)
        logger.info('message query sent: %s', query)

        try:
            r = requests.get(self.base_url + '?' + query, timeout=30)
        except (Timeout, RequestException) as e:
            logging.error('fatal error in talking to pfioh service, detail: %s' % str(e))
            return {"status": False}

        return {"status": True, "remoteServer": r.content}

    @classmethod
    def get_service_obj(cls):
        if 'pfioh' not in g:
            g.pfioh = cls(app.config.get('DATA_SERVICE_URL'))
        return g.pfioh
