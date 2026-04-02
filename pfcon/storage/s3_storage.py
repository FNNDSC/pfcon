"""
Handle s3-based storage. This is used when pfcon is in-network and
configured to directly download the data from s3 object storage.
"""

import logging
import datetime
import os
import json
import io

from botocore.exceptions import ClientError

from .base_storage import BaseStorage
from .s3manager import S3Manager


logger = logging.getLogger(__name__)


class S3Storage(BaseStorage):

    def __init__(self, config):

        super().__init__(config)

        self.s3_manager = S3Manager(config.get('S3_BUCKET_NAME'),
                                    config.get('S3_CONNECTION_PARAMS'))

    def store_data(self, job_id, job_incoming_dir, data, **kwargs):
        """
        Fetch the files with prefixes in the data list from s3 storage into the
        specified incoming directory.
        """
        self.job_id = job_id
        self.job_output_path = kwargs['job_output_path']

        all_obj_paths = set()

        for s3_path in data:
            s3_path = s3_path.strip('/')
            obj_paths = set()
            visited_paths = set()

            self._find_all_storage_object_paths(s3_path, obj_paths, visited_paths)

            for obj_path in obj_paths:
                if obj_path not in all_obj_paths:  # download a given file only once
                    try:
                        contents = self.s3_manager.download_obj(obj_path)
                    except ClientError as e:
                        logger.error(f'Error while downloading file {obj_path} from s3 '
                                     f'storage for job {job_id}, detail: {str(e)}')
                        raise

                    local_file_path = obj_path.replace(s3_path, '', 1).lstrip('/')
                    local_file_path = os.path.join(job_incoming_dir, local_file_path)

                    try:
                        with open(local_file_path, 'wb') as f:
                            f.write(contents)
                    except FileNotFoundError:
                        os.makedirs(os.path.dirname(local_file_path))
                        with open(local_file_path, 'wb') as f:
                            f.write(contents)

                    all_obj_paths.add(obj_path)

        nfiles = len(all_obj_paths)
        logger.info(f'{nfiles} files fetched from s3 storage for job {job_id}')

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
        Upload output files from the specified outgoing directory into s3 storage
        with the prefix specified by job_output_path keyword argument.
        Then create job json file ready for transmission to a remote origin. The json
        file contains the job_output_path prefix and the list of relative file paths
        in s3 storage.
        """
        self.upload_data(job_id, job_outgoing_dir, **kwargs)
        return self.get_output_metadata(job_id, job_outgoing_dir, **kwargs)

    def get_output_metadata(self, job_id, job_outgoing_dir, **kwargs):
        """
        Walk the local outgoing directory and return a BytesIO JSON object
        containing the job_output_path and the list of relative file paths.
        No network I/O is performed.
        """
        s3_output_path = kwargs['job_output_path']

        s3_rel_file_paths = []
        for root, dirs, files in os.walk(job_outgoing_dir):
            for filename in files:
                local_file_path = os.path.join(root, filename)

                if not os.path.islink(local_file_path) and not local_file_path.endswith('.chrislink'):
                    rel_file_path = os.path.relpath(local_file_path, job_outgoing_dir)
                    s3_rel_file_paths.append(rel_file_path)

        data = {'job_output_path': s3_output_path,
                'rel_file_paths': s3_rel_file_paths}
        return io.BytesIO(json.dumps(data).encode())

    def upload_data(self, job_id, job_outgoing_dir, **kwargs):
        """
        Upload output files from the specified outgoing directory into s3
        storage with the prefix specified by job_output_path keyword argument.
        Already-uploaded files are skipped to ensure idempotency.
        """
        s3_output_path = kwargs['job_output_path']
        try:
            files_already_in_s3 = set(self.s3_manager.ls(s3_output_path))
        except ClientError as e:
            logger.error(f'Error while listing s3 storage files in {s3_output_path} '
                         f'for job {job_id}, detail: {str(e)}')
            raise

        for root, dirs, files in os.walk(job_outgoing_dir):
            for filename in files:
                local_file_path = os.path.join(root, filename)

                if not os.path.islink(local_file_path) and not local_file_path.endswith('.chrislink'):
                    rel_file_path = os.path.relpath(local_file_path, job_outgoing_dir)
                    s3_file_path = os.path.join(s3_output_path, rel_file_path)

                    if s3_file_path not in files_already_in_s3:
                        try:
                            with open(local_file_path, 'rb') as f:
                                self.s3_manager.upload_obj(s3_file_path, f.read())
                        except ClientError as e:
                            logger.error(f'Error while uploading file {s3_file_path} '
                                         f'to s3 storage for job {job_id},'
                                         f' detail: {str(e)}')
                            raise
                        except Exception as e:
                            logger.error(f'Failed to read file {local_file_path} for '
                                         f'job {job_id}, detail: {str(e)}')
                            raise

    def _find_all_storage_object_paths(self, storage_path, obj_paths, visited_paths):
        """
        Find all object storage paths under the passed storage path (prefix) by
        recursively following ChRIS links. The resulting set of object paths is given
        by the obj_paths set argument.
        """
        if not any(storage_path.startswith(p) for p in visited_paths):  # avoid infinite loops
            visited_paths.add(storage_path)
            job_id = self.job_id
            job_output_path = self.job_output_path

            try:
                l_ls = self.s3_manager.ls(storage_path)
            except Exception as e:
                logger.error(f'Error while listing s3 storage files in {storage_path} '
                             f'for job {job_id}, detail: {str(e)}')
                raise

            for obj_path in l_ls:
                if obj_path.endswith('.chrislink'):
                    try:
                        linked_path = self.s3_manager.download_obj(
                            obj_path).decode().strip()
                    except Exception as e:
                        logger.error(f'Error while downloading file {obj_path} from '
                                     f's3 storage for job {job_id}, detail: {str(e)}')
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
