
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, NewType, Optional, TypedDict, AnyStr, List
from dataclasses import dataclass
from enum import Enum


class ManagerException(Exception):
    def __init__(self, msg, **kwargs):
        self.status_code = kwargs.get('status_code')
        super().__init__(msg)


class JobStatus(Enum):
    notStarted = 'notStarted'
    started = 'started'
    finishedSuccessfully = 'finishedSuccessfully'
    finishedWithError = 'finishedWithError'
    undefined = 'undefined'


JobName = NewType('JobName', str)
"""An identifying string which ``pfcon`` can be queried for to retrieve a submitted job."""
Image = NewType('Image', str)
"""An OCI container image tag, e.g. ``docker.io/fnndsc/pl-simpledsapp:2.0.1``"""
TimeStamp = NewType('TimeStamp', str)
"""A time and date in ISO format."""

J = TypeVar('J')
"""
``J`` is an object representing a job. Its real type depends
on what is returned by the client library for the specific backend.

Jobs must at least be identifiable by name from the engine.
"""


@dataclass(frozen=True)
class JobInfo:
    name: JobName
    """A name which ``pfcon`` can be queried for to retrieve this job."""
    image: Image
    cmd: str
    timestamp: TimeStamp
    """Time of completion."""
    message: str
    status: JobStatus


class ResourcesDict(TypedDict):
    number_of_workers: int
    """
    Number of workers for multi-node parallelism.
    """
    cpu_limit: int
    """
    CPU resource in millicores.
    
    For example, 1000 represents "1000m" or 1.0 CPU cores.
    
    https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/#meaning-of-cpu
    """
    memory_limit: int
    """
    Memory requirement in mebibytes.
    
    For example, 1000 represents "1000Mi" = "1049M" = 1.049e+9 bytes
    """
    gpu_limit: int
    """
    GPU requirement in number of GPUs.
    """


class MountsDict(TypedDict):
    inputdir_source: Optional[str]
    """
    Source input directory for the input mount.

    - ``None``: no input mount.
    - ``''`` (empty string): mount the whole volume root (Kubernetes PVC);
      not valid for host/volume-based Docker bind mounts.
    - non-empty string: absolute path (host/docker) or sub-path (k8s PVC).
    """
    inputdir_target: str
    """
    Absolute path to the target input directory (within the container).
    """
    outputdir_source: str
    """
    Absolute path to the source output directory or otherwise a volume name.
    """
    outputdir_target: str
    """
    Absolute path to the target output directory (within the container).
    """


class AbstractManager(ABC, Generic[J]):
    """
    An ``AbstractManager`` is an API to a service which can schedule
    (and eventually run) *ChRIS* plugin instances, and maintains persistent
    information about previously scheduled plugin instances.
    """

    # Map from semantic label name (as emitted by pfcon resources) to the
    # concrete label key used on this backend. Subclasses override with the
    # key format idiomatic to their engine (reverse-DNS for Docker,
    # prefix/name for Kubernetes).
    LABEL_KEYS: dict = {}

    def __init__(self, config_dict: dict = None):
        super().__init__()

        self.config = config_dict

    def translate_labels(self, labels: Optional[dict]) -> dict:
        """
        Translate a dict of semantic labels (e.g. ``{'job_type': 'plugin'}``)
        into the concrete label keys for this backend. Unknown keys are
        passed through unchanged.
        """
        if not labels:
            return {}
        return {self.LABEL_KEYS.get(k, k): v for k, v in labels.items()}

    @abstractmethod
    def schedule_job(self, image: Image, command: List[str], name: JobName,
                     resources_dict: ResourcesDict, env: List[str],
                     uid: Optional[int], gid: Optional[int],
                     mounts_dict: MountsDict,
                     extra_labels: Optional[dict] = None) -> J:
        """
        Schedule a new job and return the job object.
        """
        ...

    @abstractmethod
    def get_job(self, name: JobName) -> J:
        """
        Get a previously scheduled job object.
        """
        ...

    @abstractmethod
    def get_job_logs(self, job: J, tail: int) -> AnyStr:
        """
        Get the logs (combined stdout+stdin) from a previously scheduled job object.

        :param job: the job which to get the logs for
        :param tail: how many bytes to read from the end of the logs.
        """
        ...

    @abstractmethod
    def get_job_info(self, job: J) -> JobInfo:
        """
        Get the job's info dictionary for a previously scheduled job object.
        """
        ...

    @abstractmethod
    def remove_job(self, job: J):
        """
        Remove a previously scheduled job.
        """
        ...
