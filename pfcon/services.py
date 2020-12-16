"""
This module implements the communication (API clients) with the coordinated pfioh and
pman services. Because communication with pman is not based on standard http we need
a pycurl-based hack here. Future pman's implementation should remove the need for pycurl.
"""

import logging
import io
import json
import urllib.parse
from abc import ABC
import pycurl
import requests
from requests.exceptions import Timeout, RequestException

from flask import g, current_app as app
from werkzeug.utils import secure_filename


logger = logging.getLogger(__name__)


class ServiceException(Exception):
    pass


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
    def run_job(self, job_id, compute_data, data_share_dir):
        """
        Run process job on the compute environment ('run' action on pman).
        """
        payload = {
            'action': 'run',
            'meta': {
                    'cmd': compute_data['cmd'],
                    'threaded': True,
                    'auid': compute_data['auid'],
                    'jid': job_id,
                    'number_of_workers': compute_data['number_of_workers'],
                    'cpu_limit': compute_data['cpu_limit'],
                    'memory_limit': compute_data['memory_limit'],
                    'gpu_limit': compute_data['gpu_limit'],
                    'container':
                        {
                            'target':
                                {
                                    'image': compute_data['image'],
                                    'cmdParse': False,
                                    'selfexec': compute_data['selfexec'],
                                    'selfpath': compute_data['selfpath'],
                                    'execshell': compute_data['execshell']
                                },
                            'manager':
                                {
                                    'image': 'fnndsc/swarm',
                                    'app': "swarm.py",
                                    'env':
                                        {
                                            'meta-store': 'key',
                                            'serviceType': 'docker',
                                            'shareDir': '%shareDir',
                                            'serviceName': job_id
                                        }
                                }
                        }
                }
        }
        payload['meta']['container']['manager']['env']['shareDir'] = data_share_dir
        return self.do_POST(payload)

    def get_job(self, job_id):
        """
        Get job info from the compute environment ('status' action on pman).
        """
        payload = {
            'action': 'status',
            'meta': {
                'key': 'jid',
                'value': job_id
            }
        }
        return self.do_POST(payload)

    def delete_job(self, job_id):
        pass

    def do_POST(self, payload):
        logger.info('sending cmd to pman service at -->%s<--', self.base_url)
        logger.info('payload sent: %s', json.dumps(payload, indent=4))

        c = pycurl.Curl()
        c.setopt(pycurl.CONNECTTIMEOUT, 60)
        c.setopt(c.URL, self.base_url)
        buffer = io.BytesIO()
        c.setopt(pycurl.WRITEFUNCTION, buffer.write)
        post_data = json.dumps({'payload': payload})
        # form data must be provided already urlencoded:
        # post_data = urlencode({'payload': json.dumps(d_msg)})
        # but pman (wrongly) does not comply with this.
        # the next sets request method to POST,
        # Content-Type header to application/x-www-form-urlencoded
        # and data to send in request body.
        c.setopt(c.POSTFIELDS, post_data)
        try:
            c.perform()
        except pycurl.error as e:
            error_msg = 'error in talking to pman service, detail: %s' % str(e)
            logging.error(error_msg)
            raise ServiceException(error_msg)
        finally:
            c.close()
        str_resp = buffer.getvalue().decode()

        d_response = json.loads(str_resp)
        logger.info('response from pman: %s', json.dumps(d_response, indent=4))
        return d_response

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
        logger.info('sending PUSH data request to pfioh at -->%s<--', self.base_url)
        logger.info('payload sent: %s', json.dumps(payload, indent=4))
        try:
            r = requests.post(self.base_url,
                              files={'local': file_obj},
                              data={'d_msg': json.dumps(payload), 'filename': fname},
                              headers={'Mode': 'file'},
                              timeout=300)
        except (Timeout, RequestException) as e:
            error_msg = 'error in talking to pfioh service, detail: %s' % str(e)
            logging.error(error_msg)
            raise ServiceException(error_msg)
        d_response = r.json()
        logger.info('response from pfioh: %s', json.dumps(d_response, indent=4))
        return d_response

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
        logger.info('sending PULL data request to pfioh at -->%s<--', self.base_url)
        logger.info('query sent: %s', query)
        try:
            r = requests.get(self.base_url + '?' + query, timeout=720)
        except (Timeout, RequestException) as e:
            error_msg = 'error in talking to pfioh service, detail: %s' % str(e)
            logging.error(error_msg)
            raise ServiceException(error_msg)
        return r.content

    @classmethod
    def get_service_obj(cls):
        if 'pfioh' not in g:
            g.pfioh = cls(app.config.get('DATA_SERVICE_URL'))
        return g.pfioh
