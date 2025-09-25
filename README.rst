##################
pfcon |ChRIS logo|
##################

.. |ChRIS logo| image:: https://github.com/FNNDSC/ChRIS_ultron_backEnd/blob/master/docs/assets/logo_chris.png

.. image:: https://img.shields.io/docker/v/fnndsc/pfcon?sort=semver
    :alt: Docker Image Version
    :target: https://hub.docker.com/r/fnndsc/pfcon
.. image:: https://img.shields.io/github/license/fnndsc/pfcon
    :alt: MIT License
    :target: https://github.com/FNNDSC/pfcon/blob/master/LICENSE
.. image:: https://github.com/fnndsc/pfcon/workflows/CI/badge.svg
    :alt: Github Actions
    :target: https://github.com/fnndsc/pfcon/actions
.. image:: https://img.shields.io/github/last-commit/fnndsc/pfcon.svg
    :alt: Last Commit  
    

.. contents:: Table of Contents
    :depth: 2


********
Overview
********

This repository implements a `Flask`_ application called ``pfcon`` -- a controlling service that provides
a unified web API to run containerized jobs on diverse compute environments/schedulers, e.g. Docker, Podman,
Swarm, Kubernetes and SLURM.

.. _`Flask`: https://flask-restful.readthedocs.io/

Primarily, ``pfcon`` provides "compute resource" services to a ChRIS backend. When ``pfcon`` is deployed
in the so called "in-network" mode it has direct access to the ChRIS's storage environment (currently either
Swift object storage or a POSIX filesystem). This speeds up and makes more efficent the management of data/files
provided  to the compute cluster as the input to a scheduled job. Otherwise when ``pfcon`` is not deployed in
"in-network" mode it can accept a zip file (as part of a multipart POST request) containing all the input files
for the job. In this case the output data from the job can then be downloaded back as a zip file after the job
is finished.

After submitting a job ``pfcon``'s API can then be used to query and control the following (for example):

- *state*: Is job <job_id> still running?

Visit the `pfcon http API call examples`_ wiki page to see examples of http calls accepted by ``pfcon`` server.

.. _`pfcon http API call examples`: https://github.com/FNNDSC/pfcon/wiki/pfcon-http-API-call-examples

Additionally a Python3 client for this server's web API is provided here: https://github.com/FNNDSC/python-pfconclient


***********************
Development and testing
***********************

Preconditions
=============

Install latest docker
---------------------

Tested platforms:

* ``Ubuntu 18.04+ and MAC OS X 10.14+ and Fedora 31+`` `Additional instructions for Fedora <https://github.com/mairin/ChRIS_store/wiki/Getting-the-ChRIS-Store-to-work-on-Fedora>`_
* ``Docker 18.06.0+``

Note: On a Linux machine make sure to add your computer user to the ``docker`` group.
Consult this page: https://docs.docker.com/engine/install/linux-postinstall/

Currently a ``make.sh`` bash script is provided in the root of the repo to facilitate developing and testing the server under the
different compute and storage environments. The currently supported storage options are:

- ``swift`` -- "in-network" Swift Object Storage
- ``filesystem`` -- "in-network" POSIX filesystem (the most efficient but unlike the others does not support ChRIS link files or multiple input dirs for the job)
- ``fslink`` -- "in-network" POSIX filesystem
- ``zipfile`` -- "out-of-network" zip file as part of a multipart POST request (default)

Below are some examples of how to start the different dev environments. Consult the header of the ``make.sh`` script for more
information on the different command line flags combinations supported by the script.

Docker-based development environment (default)
==============================================

Start pfcon's dev server with ``zipfile`` storage
-------------------------------------------------

.. code-block:: bash

    $> git clone https://github.com/FNNDSC/pfcon.git
    $> cd pfcon
    $> ./make.sh

Remove pfcon's container
------------------------

.. code-block:: bash

    $> cd pfcon
    $> ./unmake.sh

Start pfcon's dev server operating in-network with ``fslink`` storage
---------------------------------------------------------------------

.. code-block:: bash

    $> cd pfcon
    $> ./make.sh -N -F fslink

Remove pfcon's container
------------------------

.. code-block:: bash

    $> cd pfcon
    $> ./unmake.sh -N -F fslink


Podman-based development environment
====================================

Alternatively Podman can be used with the same above commands. In this case ``pfcon`` must be able to schedule
containers by communicating to the Podman socket:

.. code-block:: bash

    $> systemctl --user start podman.service
    $> export DOCKER_HOST="$(podman info --format '{{ .Host.RemoteSocket.Path }}')"


Docker Swarm-based development environment
==========================================

Start a local Docker Swarm cluster if not already started
---------------------------------------------------------

.. code-block:: bash

    $> docker swarm init --advertise-addr 127.0.0.1

Start pfcon's dev server with ``zipfile`` storage
-------------------------------------------------

.. code-block:: bash

    $> git clone https://github.com/FNNDSC/pfcon.git
    $> cd pfcon
    $> ./make.sh -O swarm

Remove pfcon's container
------------------------

.. code-block:: bash

    $> cd pfcon
    $> ./unmake.sh -O swarm

Remove the local Docker Swarm cluster if desired
------------------------------------------------

.. code-block:: bash

    $> docker swarm leave --force


Kubernetes-based development environment
========================================

Install single-node Kubernetes cluster
--------------------------------------

On MAC OS Docker Desktop includes a standalone Kubernetes server and client.
Consult this page: https://docs.docker.com/desktop/kubernetes/

On Linux there is a simple MicroK8s installation. Consult this page: https://microk8s.io

Then create the required alias:

.. code-block:: bash

    $> snap alias microk8s.kubectl kubectl
    $> microk8s.kubectl config view --raw > $HOME/.kube/config


Start pfcon's dev server with ``zipfile`` storage
-------------------------------------------------

.. code-block:: bash

    $> git clone https://github.com/FNNDSC/pfcon.git
    $> cd pfcon
    $> ./make.sh -O kubernetes

Remove pfcon's container
------------------------

.. code-block:: bash

    $> cd pfcon
    $> ./unmake.sh -O kubernetes


*************
Configuration
*************

``pfcon`` is configured by environment variables.
Refer to the source code in ``pfcon/config.py`` for exactly how it works.


How Storage Works
=================

``pfcon`` manages data in a directory known as "storeBase".
The "storeBase" is a storage space visible to every node in your compute cluster.

For single-machine deployments using Docker and Podman, the best solution is to use a local volume mounted
by ``pfcon`` at the location given by the ``STOREBASE_MOUNT`` env variable.
``pfcon`` should be configured with ``COMPUTE_VOLUME_TYPE=docker_local_volume``, ``VOLUME_NAME=...``.

On Kubernetes, a single PersistentVolumeClaim should be used. It is mounted by ``pfcon`` at the location
given by the ``STOREBASE_MOUNT`` env variable.
``pfcon`` should be configured with ``COMPUTE_VOLUME_TYPE=kubernetes_pvc``, ``VOLUME_NAME=...``.

SLURM has no concept of volumes, though SLURM clusters typically use a NFS share mounted to the same path
on every node.
``pfcon`` should be configured with ``COMPUTE_VOLUME_TYPE=host``, ``STOREBASE=...``, specify the share mount point
as ``STOREBASE``.


``Swarm`` v.s. ``Docker``
=========================

Originally, ``pfcon`` interfaced with the Docker Swarm API for the sake of supporting multi-node clusters.
However, more often than not, ``pfcon`` is run on a single-machine. Such is the case for developer
environments, "host" compute resources for our single-machine production deployments of CUBE,
and production deployments of CUBE on our Power9 supercomputers. ``Swarm`` mode is mostly an annoyance
and its multi-node ability is poorly tested. Furthermore, multi-node functionality is
better provided by ``CONTAINER_ENV=kubernetes``.


Podman Support
==============

``CONTAINER_ENV=docker`` is compatible with Podman.

Podman version 3 or 4 are known to work.

Rootless Podman
---------------

Configure the user to be able to set resource limits.

https://github.com/containers/podman/blob/main/troubleshooting.md#symptom-23


Environment Variables
=====================

============================== ===========================================================
Environment Variable           Description
============================== ===========================================================
``SECRET_KEY``                 `Flask secret key`_
``PFCON_USER``                  ``pfcon`` auth user
``PFCON_PASSWORD``              ``pfcon`` auth user's password
``PFCON_INNETWORK``             (bool) whether the server was deployed "in-network" mode
``STORAGE_ENV``                 one of: "swift", "filesystem", "fslink", "zipfile"
``CONTAINER_ENV``               one of: "swarm", "kubernetes", "cromwell", "docker"
``COMPUTE_VOLUME_TYPE``         | one of: "host", "docker_local_volume", "kubernetes_pvc"
``STOREBASE``                   where job data is stored, valid when ``COMPUTE_VOLUME_TYPE=host``, conflicts with ``VOLUME_NAME``
``VOLUME_NAME``                 name of data volume, valid when ``COMPUTE_VOLUME_TYPE=docker_local_volume`` or ``COMPUTE_VOLUME_TYPE=kubernetes_pvc`
``PFCON_SELECTOR``              label on the pfcon container, may be specified for pman to self-discover ``VOLUME_NAME`` (default: ``org.chrisproject.role=pfcon`
``CONTAINER_USER``              Set job container user in the form ``UID:GID``, may be a range for random values
``ENABLE_HOME_WORKAROUND``      If set to "yes" then set job environment variable ``HOME=/tmp``
``SHM_SIZE``                    Size of ``/dev/shm`` in mebibytes. (Supported only in Docker, Podman, and Kubernetes.)
``JOB_LABELS``                  CSV list of key=value pairs, labels to apply to container jobs
``JOB_LOGS_TAIL``               (int) maximum size of job logs
``IGNORE_LIMITS``               If set to "yes" then do not set resource limits on container jobs (for making things work without effort)
``REMOVE_JOBS``                 If set to "no" then pman will not delete jobs (for debugging)
============================== ===========================================================

.. _`Flask secret key`: https://flask.palletsprojects.com/en/2.1.x/config/#SECRET_KEY


``COMPUTE_VOLUME_TYPE=host``
----------------------------

When ``COMPUTE_VOLUME_TYPE=host``, then specify ``STOREBASE`` as a mount point path on the host(s).

``COMPUTE_VOLUME_TYPE=docker_local_volume``
-------------------------------------------

For single-machine instances, use a Docker/Podman local volume as the "storeBase."
The volume should exist prior to the start of ``pfcon``. It can be identified one of two ways:

- Manually, by passing the volume name to the variable ``VOLUME_NAME``
- Automatically: ``pfcon`` inspects a container with the label ``org.chrisproject.role=pfcon``
  and selects the mountpoint of the bind to the ``STOREBASE_MOUNT`` env variable

``COMPUTE_VOLUME_TYPE=kubernetes_pvc``
--------------------------------------

When ``COMPUTE_VOLUME_TYPE=kubernetes_pvc``, then ``VOLUME_NAME`` must be the name of a
``PersistentVolumeClaim`` configured as ``ReadWriteMany``.

In cases where the volume is only writable to a specific UNIX user,
such as a NFS-backed volume, ``CONTAINER_USER`` can be used as a workaround.

Kubernetes-Specific Options
===========================

Applicable when ``CONTAINER_ENV=kubernetes``

============================== ===========================================================
Environment Variable           Description
============================== ===========================================================
``JOB_NAMESPACE``              Kubernetes namespace for created jobs
``NODE_SELECTOR``              Pod ``nodeSelector``
============================== ===========================================================


SLURM-Specific Options
======================

Applicable when ``CONTAINER_ENV=cromwell``

============================== ===========================================================
Environment Variable           Description
============================== ===========================================================
``CROMWELL_URL``               Cromwell URL
``TIMELIMIT_MINUTES``          SLURM job time limit
============================== ===========================================================

For how it works, see https://github.com/FNNDSC/pman/wiki/Cromwell


Container User Security
=======================

Setting an arbitrary container user, e.g. with ``CONTAINER_USER=123456:123456``,
increases security but will cause (unsafely written) ChRIS plugins to fail.
In some cases, ``ENABLE_HOME_WORKAROUND=yes`` can get the plugin to work without having to change its code.

It is possible to use a random container user with ``CONTAINER_USER=1000000000-2147483647:1000000000-2147483647``
however considering that ``pfcon``'s UID never changes, this will cause everything to break.


Missing Features
================

``pfcon``'s configuration has gotten messy over the years because it attempts to provide an interface
across vastly different systems. Some mixing-and-matching of options are unsupported:

- ``IGNORE_LIMITS=yes`` only works with ``CONTAINER_ENV=docker`` (or podman).
- ``JOB_LABELS=...`` only works with ``CONTAINER_ENV=docker`` (or podman) and ``CONTAINER_ENV=kubernetes``.
- ``CONTAINER_USER`` does not work with ``CONTAINER_ENV=cromwell``
- ``CONTAINER_ENV=cromwell`` does not forward environment variables.
- ``COMPUTE_VOLUME_TYPE=host`` is not supported for Kubernetes


TODO
====

- [ ] Dev environment and testing for Kubernetes and SLURM.
