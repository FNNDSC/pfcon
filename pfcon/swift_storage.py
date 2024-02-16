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
        self.job_id = job_id
        self.job_output_path = kwargs['job_output_path']

        all_obj_paths = set()

        for swift_path in data:
            obj_paths = set()
            visited_paths = set()

            self._find_all_storage_object_paths(swift_path, obj_paths, visited_paths)

            for obj_path in obj_paths:
                if obj_path not in all_obj_paths:  # download a given file only once
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

                    all_obj_paths.add(obj_path)

        nfiles = len(all_obj_paths)
        logger.info(f'{nfiles} files fetched from swift storage for job {job_id}')

        nlinks = self.process_chrislink_files(job_incoming_dir)
        nfiles -= nlinks

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
        in swift storage.
        """
        swift_output_path = kwargs['job_output_path']
        try:
            files_already_in_swift = set(self.swift_manager.ls(swift_output_path))
        except ClientException as e:
            logger.error(f'Error while listing swift storage files in {swift_output_path} '
                         f'for job {job_id}, detail: {str(e)}')
            raise

        swift_rel_file_paths = []
        for root, dirs, files in os.walk(job_outgoing_dir):
            for filename in files:
                local_file_path = os.path.join(root, filename)

                if not os.path.islink(local_file_path) and not local_file_path.endswith('.chrislink'):
                    rel_file_path = os.path.relpath(local_file_path, job_outgoing_dir)
                    swift_file_path = os.path.join(swift_output_path, rel_file_path)

                    if swift_file_path not in files_already_in_swift:  # ensure GET is idempotent
                        try:
                            with open(local_file_path, 'rb') as f:
                                self.swift_manager.upload_obj(swift_file_path, f.read())
                        except ClientException as e:
                            logger.error(f'Error while uploading file {swift_file_path} '
                                         f'to swift storage for job {job_id},'
                                         f' detail: {str(e)}')
                            raise
                        except Exception as e:
                            logger.error(f'Failed to read file {local_file_path} for '
                                         f'job {job_id}, detail: {str(e)}')
                            raise

                    swift_rel_file_paths.append(rel_file_path)

        data = {'job_output_path': swift_output_path,
                'rel_file_paths': swift_rel_file_paths}
        return io.BytesIO(json.dumps(data).encode())

    def _find_all_storage_object_paths(self, storage_path, obj_paths, visited_paths):
        """
        Find all object storage paths from the passed storage path (prefix) by
        recursively following ChRIS links. The resulting set of object paths is given
        by the obj_paths set argument.
        """
        if not storage_path.startswith(tuple(visited_paths)):  # avoid infinite loops
            visited_paths.add(storage_path)
            job_id = self.job_id
            job_output_path = self.job_output_path

            try:
                l_ls = self.swift_manager.ls(storage_path)
            except Exception as e:
                logger.error(f'Error while listing swift storage files in {storage_path} '
                             f'for job {job_id}, detail: {str(e)}')
                raise

            for obj_path in l_ls:
                if obj_path.endswith('.chrislink'):
                    try:
                        linked_path = self.swift_manager.download_obj(
                            obj_path).decode().strip()
                    except Exception as e:
                        logger.error(f'Error while downloading file {obj_path} from '
                                     f'swift storage for job {job_id}, detail: {str(e)}')
                        raise

                    if f'{job_output_path}/'.startswith(linked_path.rstrip('/') + '/'):
                        # link files are not allowed to point to the job output dir or
                        # any of its ancestors
                        logger.error(f'Found invalid input path {linked_path} for job '
                                     f'{job_id} pointing to an ancestor of the job '
                                     f'output dir: {job_output_path}')
                        raise ValueError(f'Invalid input path: {linked_path}')

                    self._find_all_storage_object_paths(linked_path, obj_paths,
                                                       visited_paths)  # recursive call
                obj_paths.add(obj_path)
