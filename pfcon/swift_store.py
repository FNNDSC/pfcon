"""
Handle Swift File Storage Option
"""

import logging
import zipfile
import configparser
from   keystoneauth1.identity      import v3
from   keystoneauth1               import session
from   swiftclient                 import service as swift_service
from   shutil                      import copyfileobj
import io
import shutil
import base64
import datetime
import os
import yaml
import json
import os
from kubernetes import client as k_client, config
from kubernetes.client.rest import ApiException
import fasteners

logger = logging.getLogger(__name__)


class SwiftStore:

    def __init__(self, config=None):
        self.kube_client = None
        self.kube_v1_batch_client = None
        self.project = os.environ.get('OPENSHIFTMGR_PROJECT') or 'myproject'

        # init the openshift client
        self.init_openshift_client()

    def init_openshift_client(self):
        """
        Method to get a OpenShift client connected to remote or local OpenShift
        """
        kubecfg_path = os.environ.get('KUBECFG_PATH')
        if kubecfg_path is None:
            config.load_kube_config()
        else:
            config.load_kube_config(config_file=kubecfg_path)
        self.kube_client = k_client.CoreV1Api()
        self.kube_v1_batch_client = k_client.BatchV1Api()


    def storeData(self, job_id, job_incoming_dir, input_stream):
        """
        Creates an object of the file and stores it into the container as key-value object 
        """
        
        with zipfile.ZipFile(input_stream, 'r', zipfile.ZIP_DEFLATED) as job_zip:
            filenames = job_zip.namelist()
            nfiles = len(filenames)
            logger.info(f'{nfiles} files to decompress for job {job_id}')
            job_zip.extractall(path=f"/tmp/key-{job_id}/incoming")
        return {
            'jid': job_id,
            'nfiles': nfiles,
            'timestamp': f'{datetime.datetime.now()}',
            'path': job_incoming_dir
        }
        


    def getData(self , job_id, job_outgoing_dir):
        """
        Gets the data from the Swift Storage, zips and/or encodes it and sends it to the client
        """

        memory_zip_file = io.BytesIO()
        nfiles = 0
        with zipfile.ZipFile(memory_zip_file, 'w', zipfile.ZIP_DEFLATED) as job_zip:
            for root, dirs, files in os.walk(f"/tmp/key-{job_id}/outgoing"):
                for filename in files:
                    local_file_path = os.path.join(root, filename)
                    if not os.path.islink(local_file_path):
                        arc_file_path = os.path.relpath(local_file_path, f"/tmp/key-{job_id}/outgoing")
                        try:
                            with open(local_file_path, 'rb') as f:
                                job_zip.writestr(arc_file_path, f.read())
                        except Exception as e:
                            logger.error(f'Failed to read file {local_file_path} for '
                                         f'job {job_id}, detail: {str(e)}')
                        else:
                            nfiles += 1
        memory_zip_file.seek(0)
        logger.info(f'{nfiles} files compressed for job {job_id}')
        return memory_zip_file
        
    def deleteData(self , job_dir):
        shutil.rmtree(job_dir)
      
