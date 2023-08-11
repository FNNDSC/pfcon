"""
Handle filesystem-based (eg. mount directory) storage. This is used when pfcon is
in-network and configured to directly copy the data from a filesystem.
"""

import logging
import datetime
import os
import json
import io
import shutil


from .base_storage import BaseStorage


logger = logging.getLogger(__name__)


class FileSystemStorage(BaseStorage):

    def __init__(self, config):

        super().__init__(config)

        self.base_dir = config.get('FILESYSTEM_BASEDIR')


    def store_data(self, job_id, job_incoming_dir, data, **kwargs):
        """
        Copy all the files/folders under each input folder in the specified data list
        into the specified incoming directory.
        """
        nfiles = 0
        for rel_path in data:
            abs_path = os.path.join(self.base_dir, rel_path.strip('/'))

            for root, dirs, files in os.walk(abs_path):
                local_path = root.replace(abs_path, job_incoming_dir, 1)
                os.makedirs(local_path, exist_ok=True)

                for filename in files:
                    fs_file_path = os.path.join(root, filename)
                    try:
                        shutil.copy(fs_file_path, local_path)
                    except Exception as e:
                        logger.error(f'Failed to copy file {fs_file_path} for '
                                     f'job {job_id}, detail: {str(e)}')
                        raise
                    nfiles += 1

        logger.info(f'{nfiles} files copied from file system for job {job_id}')
        return {
            'jid': job_id,
            'nfiles': nfiles,
            'timestamp': f'{datetime.datetime.now()}',
            'path': job_incoming_dir
        }

    def get_data(self, job_id, job_outgoing_dir, **kwargs):
        """
        Copy output files/folders from the specified outgoing directory into the folder
        specified by job_output_path keyword argument (relative to the FS base dir).
        Then create job json file ready for transmission to a remote origin. The json
        file contains the job_output_path prefix and the list of relative file paths.
        """
        job_output_path = kwargs['job_output_path']
        fs_output_path = os.path.join(self.base_dir, job_output_path)
        fs_rel_file_paths = []

        for root, dirs, files in os.walk(job_outgoing_dir):
            rel_path = os.path.relpath(root, job_outgoing_dir)
            if rel_path == '.':
                rel_path = ''
            fs_path = os.path.join(fs_output_path, rel_path)
            os.makedirs(fs_path, exist_ok=True)

            for filename in files:
                local_file_path = os.path.join(root, filename)
                if not os.path.islink(local_file_path):
                    try:
                        shutil.copy(local_file_path, fs_path)
                    except Exception as e:
                        logger.error(f'Failed to copy file {local_file_path} for '
                                     f'job {job_id}, detail: {str(e)}')
                        raise
                    fs_rel_file_paths.append(os.path.join(rel_path, filename))

        data = {'job_output_path': job_output_path,
                'rel_file_paths': fs_rel_file_paths}
        return io.BytesIO(json.dumps(data).encode())
