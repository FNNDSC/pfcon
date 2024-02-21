"""
Handle filesystem-based storage. This is used when pfcon is in-network and configured
to directly access the data from a ChRIS shared filesystem. It assumes that both the
input (read-only)and the output (read-write) directories in the shared storage are
directly mounted into the plugin container.
"""

import logging
import datetime
import os
import json
import io


from .base_storage import BaseStorage


logger = logging.getLogger(__name__)


class FileSystemStorage(BaseStorage):

    def __init__(self, config):

        super().__init__(config)

        self.fs_mount_base_dir = config.get('STOREBASE_MOUNT')

    def store_data(self, job_id, job_incoming_dir, data, **kwargs):
        """
        Count the number of files in the specified job incoming directory.
        """
        nfiles = 0
        for root, dirs, files in os.walk(job_incoming_dir):
            nfiles += len(files)

        logger.info(f'{nfiles} files found in file system for job {job_id}')
        return {
            'jid': job_id,
            'nfiles': nfiles,
            'timestamp': f'{datetime.datetime.now()}',
            'path': job_incoming_dir
        }

    def get_data(self, job_id, job_outgoing_dir, **kwargs):
        """
        List the output files' relative paths from the folder specified by
        the job_output_path keyword argument which in turn is relative to the filesystem
        base directory (assumed to be the storebase mount directory).
        Then create job json file ready for transmission to a remote origin. The json
        file contains the job_output_path prefix and the list of relative file paths.
        """
        fs_rel_file_paths = []
        job_output_path = kwargs['job_output_path']
        abs_path = os.path.join(self.fs_mount_base_dir, job_output_path)

        for root, dirs, files in os.walk(abs_path):
            rel_path = os.path.relpath(root, abs_path)
            if rel_path == '.':
                rel_path = ''

            for filename in files:
                local_file_path = os.path.join(root, filename)
                if not os.path.islink(local_file_path):
                    fs_rel_file_paths.append(os.path.join(rel_path, filename))

        data = {'job_output_path': kwargs['job_output_path'],
                'rel_file_paths': fs_rel_file_paths}
        return io.BytesIO(json.dumps(data).encode())

    def delete_data(self, job_dir):
        """
        Delete job data from the local storage.
        """
        pass
