"""
Handle zip file-based storage. This is used when pfcon is out-of-network and
configured to receive a zip file with the data.
"""

import logging
import datetime
import zipfile
import os
import io

from .base_storage import BaseStorage


logger = logging.getLogger(__name__)


class ZipFileStorage(BaseStorage):

    def __init__(self, config):

        super().__init__(config)

    def store_data(self, job_id, job_incoming_dir, data, **kwargs):
        """
        Unpack and store the files/directories in the input zip stream data at the
        specified incoming directory.
        """
        with zipfile.ZipFile(data, 'r', zipfile.ZIP_DEFLATED) as job_zip:
            filenames = job_zip.namelist()
            nfiles = len(filenames)
            logger.info(f'{nfiles} files to decompress for job {job_id}')
            job_zip.extractall(path=job_incoming_dir)

        return {
            'jid': job_id,
            'nfiles': nfiles,
            'timestamp': f'{datetime.datetime.now()}',
            'path': job_incoming_dir
        }

    def get_data(self, job_id, job_outgoing_dir, **kwargs):
        """
        Create job zip file ready for transmission to a remote origin from the
        outgoing directory.
        """
        memory_zip_file = io.BytesIO()
        nfiles = 0

        with zipfile.ZipFile(memory_zip_file, 'w', zipfile.ZIP_DEFLATED) as job_zip:
            for root, dirs, files in os.walk(job_outgoing_dir):
                for filename in files:
                    local_file_path = os.path.join(root, filename)
                    if not os.path.islink(local_file_path):
                        arc_file_path = os.path.relpath(local_file_path, job_outgoing_dir)
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
