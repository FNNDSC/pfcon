"""
Handle swift-based storage. This is used when pfcon is in-network and
configured to directly download the data from swift object storage.
"""

import logging
import datetime
import os
import json
import io

from swiftclient.exceptions import ClientException

from .base_storage import BaseStorage
from .swiftmanager import SwiftManager


logger = logging.getLogger(__name__)


class SwiftStorage(BaseStorage):

    def __init__(self, config):

        super().__init__(config)

        self.swift_manager = SwiftManager(config.get('SWIFT_CONTAINER_NAME'),
                                          config.get('SWIFT_CONNECTION_PARAMS'))

    def store_data(self, job_id, job_incoming_dir, data, **kwargs):
        """
        Fetch the files with prefixes in the data list from swift storage into the
        specified incoming directory.
        """
        nfiles = 0
        for swift_path in data:
            try:
                l_ls = self.swift_manager.ls(swift_path)
            except ClientException as e:
                logger.error(f'Error while listing swift storage files in {swift_path} '
                             f'for job {job_id}, detail: {str(e)}')
                raise
            for obj_path in l_ls:
                try:
                    contents = self.swift_manager.download_obj(obj_path)
                except ClientException as e:
                    logger.error(f'Error while downloading file {obj_path} from swift '
                                 f'storage for job {job_id}, detail: {str(e)}')
                    raise

                local_file_path = obj_path.replace(swift_path, '', 1).lstrip('/')
                local_file_path = os.path.join(job_incoming_dir, local_file_path)
                os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
                with open(local_file_path, 'wb') as f:
                    f.write(contents)
                nfiles += 1

        logger.info(f'{nfiles} files fetched from swift storage for job {job_id}')
        return {
            'jid': job_id,
            'nfiles': nfiles,
            'timestamp': f'{datetime.datetime.now()}',
            'path': job_incoming_dir
        }

    def get_data(self, job_id, job_outgoing_dir, **kwargs):
        """
        Upload output files from the specified outgoing directory into swift storage
        with the prefix specified by job_output_path keyword argument.
        Then create job json file ready for transmission to a remote origin. The json
        file contains the job_output_path prefix and the list of relative file paths
        created in swift storage.
        """
        swift_output_path = kwargs['job_output_path']
        swift_rel_file_paths = []

        for root, dirs, files in os.walk(job_outgoing_dir):
            for filename in files:
                local_file_path = os.path.join(root, filename)
                if not os.path.islink(local_file_path):
                    rel_file_path = os.path.relpath(local_file_path, job_outgoing_dir)
                    swift_file_path = os.path.join(swift_output_path, rel_file_path)
                    try:
                        if not self.swift_manager.obj_exists(swift_file_path):
                            with open(local_file_path, 'rb') as f:
                                self.swift_manager.upload_obj(swift_file_path, f.read())
                    except ClientException as e:
                        logger.error(f'Error while uploading file {swift_file_path} to '
                                     f'swift storage for job {job_id}, detail: {str(e)}')
                        raise
                    except Exception as e:
                        logger.error(f'Failed to read file {local_file_path} for '
                                     f'job {job_id}, detail: {str(e)}')
                        raise
                    swift_rel_file_paths.append(rel_file_path)

        data = {'job_output_path': swift_output_path,
                'rel_file_paths': swift_rel_file_paths}
        return io.BytesIO(json.dumps(data).encode())
