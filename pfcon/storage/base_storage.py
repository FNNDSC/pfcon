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
                try:
                    self.deletesrc(os.path.join(job_incoming_dir, folder))
                except FileNotFoundError:
                    pass
        return self._nlinks

    def _process_chrislink_files(self, dir):
        """
        Recursively expand (substitute by actual folders) and remove ChRIS link files.

        Uses os.scandir to snapshot the directory contents before expansion so that
        directories created by copysrc are not walked again by the outer loop — they are
        handled exclusively by the explicit recursive call on dst_path.  This eliminates
        the double-traversal that occurred with os.walk.
        """
        try:
            with os.scandir(dir) as it:
                entries = list(it)
        except (FileNotFoundError, NotADirectoryError):
            return

        subdirs = []
        for entry in entries:
            if entry.is_dir(follow_symlinks=False):
                subdirs.append(entry.path)
                continue

            if not (entry.is_file(follow_symlinks=False) and entry.name.endswith('.chrislink')):
                continue

            link_file_path = entry.path

            if not any(link_file_path.startswith(p) for p in self._already_copied_src_set):  # only expand a link once
                with open(link_file_path, 'rb') as f:
                    rel_path = f.read().decode().strip()
                    abs_path = os.path.join(self.job_incoming_dir, rel_path)

                    if os.path.isfile(abs_path):
                        rel_path = os.path.dirname(rel_path)
                        abs_path = os.path.dirname(abs_path)

                    source_trace_dir = rel_path.replace('/', '_')
                    dst_path = os.path.join(dir, source_trace_dir)

                    if not os.path.isdir(dst_path):  # only copy once to a dest path
                        try:
                            self.copysrc(abs_path, dst_path)
                        except FileNotFoundError:
                            pass
                        self._already_copied_src_set.add(abs_path)
                        self._process_chrislink_files(dst_path)  # recursive call

                    self._linked_paths.add(rel_path)

                os.remove(link_file_path)
                self._nlinks += 1

        for subdir in subdirs:
            self._process_chrislink_files(subdir)

    @staticmethod
    def _link_or_copy(src, dst):
        """Hard-link src to dst; fall back to a data copy if cross-device or unsupported."""
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy(src, dst)

    @staticmethod
    def copysrc(src, dst):
        """
        Copy src (file or directory tree) to dst.

        Prefers hard links over data copies: both source and destination are always
        inside job_incoming_dir (same POSIX filesystem), so os.link is O(1) instead
        of O(bytes).  Falls back to a regular copy on any OSError (e.g. EXDEV).
        """
        try:
            shutil.copytree(src, dst, copy_function=BaseStorage._link_or_copy)
        except OSError as e:
            if e.errno in (errno.ENOTDIR, errno.EINVAL):
                BaseStorage._link_or_copy(src, dst)
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
