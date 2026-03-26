
import logging
from typing import Optional

import docker
from docker import DockerClient


logger = logging.getLogger(__name__)


def get_storebase_from_docker(storebase_mount: Optional[str],
                              pfcon_selector: Optional[str],
                              volume_id: Optional[str]) -> str:
    """
    Use docker (or Podman) to automatically identify a local volume to use as store base.

    The volume name can be given by name. Alternatively, it can be found by trying to
    detect the volume name automatically from pfcon.
    """
    d = docker.from_env()

    if volume_id is not None:
        return get_local_volume_by_id(d, volume_id)

    return get_volume_from_pfcon(d, storebase_mount, pfcon_selector)


def get_local_volume_by_id(d: DockerClient, volume_id: str) -> str:
    a = d.volumes.get(volume_id).attrs
    if a['Driver'] != 'local':
        raise ValueError(f'Volume "{a["Name"]}" uses unsupported driver: {a["Driver"]}')
    return a['Mountpoint']


def get_volume_from_pfcon(d: DockerClient, storebase_mount: str,
                          pfcon_selector: str) -> str:
    containers = d.containers.list(filters={'label': pfcon_selector})
    if not containers:
        raise ValueError(f'No container found with label {pfcon_selector}')

    container = containers[0]
    mounts = container.attrs['Mounts']
    mountpoints = (v['Source'] for v in mounts if v['Destination'] == storebase_mount)
    mountpoint = next(mountpoints, None)
    if mountpoint is None:
        raise ValueError(f'Container {container.id} does not have a mount '
                         f'to {storebase_mount}')
    return mountpoint


def connect_to_pfcon_networks(container, pfcon_selector: Optional[str]) -> None:
    """
    Connect a Docker container to the same networks as the running pfcon container.

    This is required for copy containers that must reach services only accessible
    within pfcon's Docker network (e.g. swift_service for Swift storage).
    """
    d = docker.from_env()
    pfcon_containers = d.containers.list(filters={'label': pfcon_selector})
    if not pfcon_containers:
        logger.warning('connect_to_pfcon_networks: no pfcon container found '
                       'with selector %s', pfcon_selector)
        return
    pfcon_networks = pfcon_containers[0].attrs['NetworkSettings']['Networks']
    for net_name in pfcon_networks:
        try:
            d.networks.get(net_name).connect(container)
        except docker.errors.APIError as e:
            logger.debug('Could not connect copy container to network %s: %s',
                         net_name, e)


def get_image_from_pfcon(pfcon_selector: Optional[str]) -> str:
    """
    Auto-detect the pfcon container image by finding the running pfcon container
    using its label selector and reading its image name.
    """
    d = docker.from_env()
    containers = d.containers.list(filters={'label': pfcon_selector})
    if not containers:
        raise ValueError(f'No container found with label {pfcon_selector}')

    container = containers[0]
    return container.attrs['Config']['Image']
