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
        self.job_incoming_dir = job_incoming_dir
        self._linked_paths = set()
        self._nlinks = 0
        self._already_copied_src_set = set()

        self._process_chrislink_files(job_incoming_dir)

        linked_path_top_folders = set()
        for path in self._linked_paths:
            linked_path_top_folders.add(path.split('/', 1)[0])

        for folder in linked_path_top_folders:
            if folder not in self._linked_paths:
                self.deletesrc(os.path.join(job_incoming_dir, folder))

        return self._nlinks

    def _process_chrislink_files(self, dir):
        """
        Recursively expand (substitute by actual folders) and remove ChRIS link files.
        """
        for root, dirs, files in os.walk(dir):
            for filename in files:
                if filename.endswith('.chrislink'):
                    link_file_path = os.path.join(root, filename)

                    if not link_file_path.startswith(tuple(self._already_copied_src_set)):  # only expand a link once
                        with open(link_file_path, 'rb') as f:
                            rel_path = f.read().decode().strip()
                            abs_path = os.path.join(self.job_incoming_dir, rel_path)

                            if os.path.isfile(abs_path):
                                rel_path = os.path.dirname(rel_path)
                                abs_path = os.path.dirname(abs_path)

                            source_trace_dir = rel_path.replace('/', '_')
                            dst_path = os.path.join(root, source_trace_dir)

                            if not os.path.isdir(dst_path):  # only copy once to a dest path
                                self.copysrc(abs_path, dst_path)
                                self._already_copied_src_set.add(abs_path)
                                self._process_chrislink_files(dst_path)  # recursive call

                            self._linked_paths.add(rel_path)

                        os.remove(link_file_path)
                        self._nlinks += 1

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
