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
        
        f = open('/tmp/{}.zip'.format(key), 'wb')
        buf = 16*1024
        while 1:
            chunk = input_stream.read(buf)
            if not chunk:
                break
            f.write(chunk)
        f.close()

        zip_file_contents = open('/tmp/{}.zip'.format(key), mode='rb')
        
       
        

        try:
            success = True
            filePath = "input/data"

            resp_headers, containers = swiftService.get_account()
            listContainers = [d['name'] for d in containers if 'name' in d]

            if key not in listContainers:
                swiftService.put_container(key)
                resp_headers, containers = swiftService.get_account()
                listContainers = [d['name'] for d in containers if 'name' in d]
                if key in listContainers:
                    logger.info('The container was created successfully')
                    
                else:
                    raise Exception('The container was not created successfully')
                
            swiftService.put_object(
                    key,
                    filePath,
                    contents=zip_file_contents,
                    content_type='application/zip'
                    )
            zip_file_contents.close()    
            
            


            # Confirm presence of the object in swift
            response_headers = swiftService.head_object(key, file_path)
            logger.info('The upload was successful')
        except Exception as err:
            logger.error(f'Error, detail: {str(err)}')
            success = False

        #Headers
        return {
            'jid': key,
            'nfiles': 'application/zip',
            'timestamp': f'{datetime.datetime.now()}',
            'path': file_path
        }


    def getData(self, container_name):
        """
        Gets the data from the Swift Storage, zips and/or encodes it and sends it to the client
        """

        b_delete = False
        configPath = "/etc/swift/swift-credentials.cfg"

        

        swiftService = self._createSwiftService(configPath)

        key = "output/data"
        success = True

        response_headers, object_contents = swiftService.get_object(container_name, key)
        
        
        
        return object_contents
      
