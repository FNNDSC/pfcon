
import pytest
from docker import DockerClient
from docker.models.volumes import Volume
import pfcon.compute._helpers as helpers

from contextlib import contextmanager


STOREBASE_MOUNT = '/var/local/storeBase'


def test_podman_storebase_volume_name(podman_client):
    storebase_volume_name_helper(podman_client)


def test_docker_storebase_volume_name(docker_client):
    storebase_volume_name_helper(docker_client)


def test_podman_storebase_from_pfcon(podman_client):
    storebase_from_pfcon_helper(podman_client, STOREBASE_MOUNT)


def test_docker_storebase_from_pfcon(docker_client):
    storebase_from_pfcon_helper(docker_client, STOREBASE_MOUNT)


def storebase_from_pfcon_helper(d: DockerClient, storebase_mount):
    with create_volume(d) as v:
        _pfcon = d.containers.run(
            image='alpine',
            command=['sleep', '100'],
            detach=True,
            volumes={v.name: {'bind': storebase_mount}},
            labels={'org.chrisproject.role': 'dummy-pfcon'}
        )

        actual = helpers.get_volume_from_pfcon(d,
                                               storebase_mount,
                                               'org.chrisproject.role=dummy-pfcon')
        expected = v.attrs['Mountpoint']
    assert actual == expected


def storebase_volume_name_helper(d: DockerClient):
    with create_volume(d) as v:
        actual = helpers.get_local_volume_by_id(d, v.name)
        expected = v.attrs['Mountpoint']
    assert actual == expected


@contextmanager
def create_volume(d: DockerClient) -> Volume:
    v = d.volumes.create()
    try:
        yield v
    finally:
        for c in d.containers.list(filters={'volume': v.name}):
            c.kill()
            c.remove(force=True)
        v.remove(force=True)
