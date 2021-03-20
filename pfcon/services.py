"""
This module implements the communication (API clients) with the coordinated pman service.
"""

import logging
import json
from abc import ABC
import requests
from requests.exceptions import Timeout, RequestException

from flask import g, current_app as app


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
        logger.info(f'Sending RUN job request to {self.NAME} at -->{self.base_url}<-- '
                    f'for job {job_id}')
        logger.info('Payload sent: %s', json.dumps(compute_data, indent=4))
        try:
            r = requests.post(self.base_url, json=compute_data, timeout=100)
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
        d_resp = r.json()
        logger.info(f'Response from {self.NAME}: {json.dumps(d_resp, indent=4)}')
        return d_resp

    def get_job(self, job_id):
        """
        Get job info from the compute environment.
        """
        url = self.base_url + job_id + '/'
        logger.info(f'Sending STATUS job request to {self.NAME} at -->{self.base_url}<-- '
                    f'for job {job_id}')
        try:
            r = requests.get(url, timeout=100)
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
        d_resp = r.json()
        logger.info(f'Response from {self.NAME}: {json.dumps(d_resp, indent=4)}')
        return d_resp

    def delete_job(self, job_id):
        pass

    @classmethod
    def get_service_obj(cls):
        if 'pman' not in g:
            g.pman = cls(app.config.get('COMPUTE_SERVICE_URL'))
        return g.pman
