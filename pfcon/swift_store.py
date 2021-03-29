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

import base64
import datetime
import os

logger = logging.getLogger(__name__)


class SwiftStore:

    def __init__(self, config=None):

        self.config = config

    def _createSwiftService(self, configPath):
        config = configparser.ConfigParser()
        f = open(configPath, 'r')
        config.readfp(f)
        f.close()

        options = {
            'os_auth_url':          config['AUTHORIZATION']['osAuthUrl'],
            'application_id':       config['SECRET']['applicationId'],
            'application_secret':   config['SECRET']['applicationSecret'],
        }

        auth_swift = v3.application_credential.ApplicationCredential(
            options['os_auth_url'],
            application_credential_id=options['application_id'],
            application_credential_secret=options['application_secret']
        )

        session_client = session.Session(auth=auth_swift)
        service = swift_service.Connection(session=session_client)
        return service

    def storeData(self, key, file_path, input_stream):
        """
        Creates an object of the file and stores it into the container as key-value object 
        """

        configPath = "/etc/swift/swift-credentials.cfg"


        swiftService = self._createSwiftService(configPath)
        
       
        

        try:
            success = True
            filePath = "input/data"

            resp_headers, containers = swiftService.get_account()
            listContainers = [d['name'] for d in containers if 'name' in d]

            if key not in listContainers:
                swiftService.put_container(key)
                resp_headers, containers = swiftService.get_account()
                listContainers = [d['name'] for d in containers if 'name' in d]
                if str_containerName in listContainers:
                    logger.info('The container was created successfully')
                else:
                    raise Exception('The container was not created successfully')
                    
            with zipfile.ZipFile(input_stream, 'w', zipfile.ZIP_DEFLATED) as job_zip:
                


                swiftService.put_object(
                    key,
                    filePath,
                    contents=job_zip,
                    content_type='application/zip'
                )


            # Confirm presence of the object in swift
            response_headers = swiftService.head_object(key, file_path)
            logger.info('The upload was successful')
        except Exception as err:
            logger.error(f'Error, detail: {str(err)}')
            success = False

        #Headers
        return {
            'jid': key,
            'nfiles': input_stream,
            'timestamp': f'{datetime.datetime.now()}',
            'path': file_path
        }


    def getData(self, **kwargs):
        """
        Gets the data from the Swift Storage, zips and/or encodes it and sends it to the client
        """

        b_delete = False
        configPath = "/etc/swift/swift-credentials.cfg"

        for k,v in kwargs.items():
            if k== 'path': containerName = v
            if k== 'is_zip': b_zip = v
            if k== 'cleanup': b_cleanup = v
            if k== 'd_ret': d_ret = v
            if k == 'configPath': configPath = v
            if k == 'delete': b_delete = v

        swiftService = self._createSwiftService(configPath)

        key = "output/data"
        success = True

        response_headers, object_contents = swiftService.get_object(containerName, key)

        # Download the object
        try:
            downloaded_file = open('/tmp/incomingData.zip', mode='wb')
            downloaded_file.write(object_contents)
            downloaded_file.close()
            logger.info('Download results generated')
        except Exception as e:
            success = False
            logger.error(f'Error, detail: {str(e)}')

        if success:
            logger.info('Download successful')
            if b_delete:
                try:
                    swiftService.delete_object(containerName, key)
                except Exception as e:
                    success = False
                    logger.error(f'Error, detail: {str(e)}')
                if success:
                    logger.info(f'Deleted object with key {key}')
                else:
                    logger.info('Deletion unsuccessful')
        else:
            logger.info('Download unsuccessful')

        if success:
            d_ret['status'] = True
            d_ret['msg'] = 'File/Directory downloaded'
            self.buffered_response('/tmp/incomingData.zip')
        else:
            d_ret['status'] = False
            d_ret['msg'] = 'File/Directory downloaded'

        #Unzipping
        if not b_zip:
            raise NotImplementedError('Please use the zip option')

        return d_ret
