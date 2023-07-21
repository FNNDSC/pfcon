"""
Module containining the base abstract class for handling data storage.
"""

import logging
import abc
import shutil


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
