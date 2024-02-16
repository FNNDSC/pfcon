"""
Module containining the base abstract class for handling data storage.
"""

import logging
import os
import abc
import shutil, errno


logger = logging.getLogger(__name__)


class BaseStorage(abc.ABC):

    def __init__(self, config):

        self.config = config

    @abc.abstractmethod
    def store_data(self, job_id, job_incoming_dir, data, **kwargs):
        """
        Store the files/directories specified in the input data at the specified
        local incoming directory. The data parameter and its interpretation depends on
        the concrete storage subclass.
        """
        ...

    @abc.abstractmethod
    def get_data(self, job_id, job_outgoing_dir, **kwargs):
        """
        Return the data from the local outgoing directory. The returned data and its
        interpretation depends on the concrete storage subclass.
        """
        ...

    def delete_data(self, job_dir):
        """
        Delete job data from the local storage.
        """
        shutil.rmtree(job_dir)

    def process_chrislink_files(self, job_incoming_dir):
        """
        Rearrange the local job incoming directory tree by creating folders that trace
        the source dirs pointed by ChRIS link files.
        """
        linked_paths = set()
        nlinks = 0

        for root, dirs, files in os.walk(job_incoming_dir):
            for filename in files:
                if filename.endswith('.chrislink'):
                    link_file_path = os.path.join(root, filename)

                    with open(link_file_path, 'rb') as f:
                        path = f.read().decode().strip()
                        if os.path.isfile(os.path.join(job_incoming_dir, path)):
                            path = os.path.dirname(path)

                        source_trace_dir = path.replace('/', '_')
                        dst_path = os.path.join(root, source_trace_dir)

                        if not os.path.isdir(dst_path):
                            self.copysrc(os.path.join(job_incoming_dir, path), dst_path)

                        linked_paths.add(path)

                    os.remove(link_file_path)
                    nlinks += 1

        linked_path_top_folders = set()
        for path in linked_paths:
            linked_path_top_folders.add(path.split('/', 1)[0])

        for folder in linked_path_top_folders:
            if folder not in linked_paths:
                self.deletesrc(os.path.join(job_incoming_dir, folder))

        return nlinks

    @staticmethod
    def copysrc(src, dst):
        try:
            shutil.copytree(src, dst)
        except OSError as e:
            if e.errno in (errno.ENOTDIR, errno.EINVAL):
                shutil.copy(src, dst)
            else:
                raise

    @staticmethod
    def deletesrc(src):
        try:
            shutil.rmtree(src)
        except OSError as e:
            if e.errno in (errno.ENOTDIR, errno.EINVAL):
                os.remove(src)
            else:
                raise