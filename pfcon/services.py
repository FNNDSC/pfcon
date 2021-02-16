"""
This module implements the communication (API clients) with the coordinated pfioh and
pman services.
"""

import logging
import json
import urllib.parse
from abc import ABC
import requests
from requests.exceptions import Timeout, RequestException

from flask import g, current_app as app
from werkzeug.utils import secure_filename


logger = logging.getLogger(__name__)


class ServiceException(Exception):
    def __init__(self, msg, **kwargs):
        self.code = kwargs.get('code')
        super().__init__(msg)


class Service(ABC):
    """
    Abstract base class for the coordinated services.
    """
    NAME = 'abstract'

    def __init__(self, base_url):
        super().__init__()

        # base url of the service
        self.base_url = base_url


class PmanService(Service):
    """
    Class for the pman service.
    """
    NAME = 'pman'

    def run_job(self, job_id, compute_data):
        """
        Run job on the compute environment.
        """
        compute_data['jid'] = job_id
        try:
            r = requests.post(self.base_url, json=compute_data, timeout=1000)
        except (Timeout, RequestException) as e:
            msg = f'Error in talking to {self.NAME} service while submitting job ' \
                  f'{job_id}, detail: {str(e)} '
            logger.error(msg)
            raise ServiceException(msg, code=503)
        if r.status_code != 200:
            msg = f'Error response from {self.NAME} service while submitting job ' \
                  f'{job_id}, detail: {r.text}'
            logger.error(msg)
            raise ServiceException(msg, code=r.status_code)
        return r.json()

    def get_job(self, job_id):
        """
        Get job info from the compute environment.
        """
        url = self.base_url + job_id + '/'
        try:
            r = requests.get(url, timeout=1000)
        except (Timeout, RequestException) as e:
            msg = f'Error in talking to {self.NAME} service while getting job ' \
                  f'{job_id} status, detail: {str(e)} '
            logger.error(msg)
            raise ServiceException(msg, code=503)
        if r.status_code != 200:
            msg = f'Error response from {self.NAME} service while getting job ' \
                  f'{job_id} status, detail: {r.text}'
            logger.error(msg)
            raise ServiceException(msg, code=r.status_code)
        return r.json()

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
    NAME = 'pfioh'

    def push_data(self, job_id, file_obj):
        """
        Push zip data file to pfioh ('pushPath' action on pfioh).
        """
        fname = secure_filename(file_obj.filename)
        payload = {
            'action': 'pushPath',
            'meta': {
                'remote': {'key': job_id},
                'local': {'path': fname},  # deprecated field
                'specialHandling': {
                    'op': 'plugin',
                    'cleanup': True
                },
                'transport': {
                    'mechanism': 'compress',
                    'compress': {
                        'archive':  'zip',
                        'unpack': True,
                        'cleanup':  True
                    }
                }
            }
        }
        logger.info(f'Sending PUSH data request to {self.NAME} at -->{self.base_url}<-- '
                    f'for job {job_id}')
        logger.info('Payload sent: %s', json.dumps(payload, indent=4))
        try:
            r = requests.post(self.base_url,
                              files={'local': file_obj},
                              data={'d_msg': json.dumps(payload), 'filename': fname},
                              headers={'Mode': 'file'},
                              timeout=300)
        except (Timeout, RequestException) as e:
            msg = f'Error in talking to {self.NAME} service while sending PUSH data ' \
                  f'request for job {job_id}, detail: {str(e)} '
            logger.error(msg)
            raise ServiceException(msg, code=503)
        d_resp = r.json()
        logger.info(f'Response from {self.NAME}: {json.dumps(d_resp, indent=4)}')
        return d_resp

    def pull_data(self, job_id):
        """
        Pull zip data file from pfioh ('pullPath' action on pfioh).
        """
        d_query = {
            'action': 'pullPath',
            'meta': {
                'remote': {'key': job_id},
                'local': {
                    'path': job_id,  # deprecated field
                    'createDir': True
                },
                'specialHandling': {
                    'op': "plugin",
                    'cleanup': True
                },
                'transport': {
                    'mechanism': 'compress',
                    'compress': {
                        'archive':  'zip',
                        'unpack': True,
                        'cleanup':  True
                    }
                }
            }
        }
        query = urllib.parse.urlencode(d_query)
        logger.info(f'Sending PULL data request to {self.NAME} at -->{self.base_url}<-- '
                    f'for job {job_id}')
        logger.info('Query sent: %s', query)
        try:
            r = requests.get(self.base_url + '?' + query, timeout=720)
        except (Timeout, RequestException) as e:
            msg = f'Error in talking to {self.NAME} service while sending PULL data ' \
                  f'request for job {job_id}, detail: {str(e)} '
            logger.error(msg)
            raise ServiceException(msg, code=503)
        return r.content

    @classmethod
    def get_service_obj(cls):
        if 'pfioh' not in g:
            g.pfioh = cls(app.config.get('DATA_SERVICE_URL'))
        return g.pfioh
