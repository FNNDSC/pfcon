"""
Handle MountDir file storage.
"""

import logging
import datetime
import zipfile
import os
import io
import shutil


logger = logging.getLogger(__name__)


class MountDir:

    def __init__(self, config=None):

        self.config = config

    def store_data(self, job_id, job_incoming_dir, input_stream):
        """
        Unpack and store the files/directories in the input zip stream at the specified
        incoming directory.
        """
        with zipfile.ZipFile(input_stream, 'r', zipfile.ZIP_DEFLATED) as job_zip:
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

    def get_data(self, job_id, job_outgoing_dir):
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
                    arc_file_path = os.path.relpath(local_file_path, job_outgoing_dir)
                    with open(local_file_path, 'r') as f:
                        job_zip.writestr(arc_file_path, f.read())
                nfiles += len(files)
        memory_zip_file.seek(0)
        logger.info(f'{nfiles} files compressed for job {job_id}')
        return memory_zip_file

    def delete_data(self, job_dir):
        """
        Delete job data from the store.
        """
        shutil.rmtree(job_dir)
