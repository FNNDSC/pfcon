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

This repository implements ``pfcon`` -- a controlling service that acts as the interface to a process manager ``pman`` service.

Most simply, a local zip file can be pushed to a remote ``pfcon``, then after unpacking the data some process is run on it in the remote space using the controlled ``pman`` service. The resultant data can then be downloaded back as a zip file to the local space.

It can be used to query and control the following (for example):

- *state*: Is job <XYZ> still running?

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

Currently tested platforms:

* ``Ubuntu 18.04+ and MAC OS X 10.14+ and Fedora 31+`` `Additional instructions for Fedora <https://github.com/mairin/ChRIS_store/wiki/Getting-the-ChRIS-Store-to-work-on-Fedora>`_
* ``Docker 18.06.0+``

Note: On a Linux machine make sure to add your computer user to the ``docker`` group.
Consult this page: https://docs.docker.com/engine/install/linux-postinstall/


Docker Swarm-based development environment
==========================================

Start a local Docker Swarm cluster if not already started
---------------------------------------------------------

.. code-block:: bash

    $> docker swarm init --advertise-addr 127.0.0.1

Start pfcon's development server and backend containers
-------------------------------------------------------

.. code-block:: bash

    $> git clone https://github.com/FNNDSC/pfcon.git
    $> cd pfcon
    $> ./make.sh

Remove pfcon's containers
-------------------------

.. code-block:: bash

    $> cd pfcon
    $> ./unmake.sh

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


Start pfcon's development server and backend containers
-------------------------------------------------------

.. code-block:: bash

    $> git clone https://github.com/FNNDSC/pfcon.git
    $> cd pfcon
    $> ./make.sh -O kubernetes

Remove pfcon's containers
-------------------------

.. code-block:: bash

    $> cd pfcon
    $> ./unmake.sh -O kubernetes


**********************
Production deployments
**********************

Docker Swarm-based deployment
=============================

A single-machine deployment is provided.

Configure pfcon services
------------------------

Modify the ``.env`` files in the ``swarm/prod/secrets`` directory appropriately.

Single-machine deployment
-------------------------

Start production pfcon:

.. code-block:: bash

    $> ./deploy.sh up

Tear down production pfcon:

.. code-block:: bash

    $> ./deploy.sh down

Kubernetes-based deployment
===========================

A single-machine deployment using Kubernetes' "hostPath" storage is provided. In addition
a multi-machine deployment for an external NFS drive is provided using NFS persistent volume.

Configure pfcon services
------------------------

Modify the ``.env`` files in the ``kubernetes/prod/base/secrets`` directory appropriately.

Single-machine deployment
-------------------------

Start production pfcon:

.. code-block:: bash

    $> ./deploy.sh -O kubernetes up

Tear down production pfcon

.. code-block:: bash

    $> ./deploy.sh -O kubernetes down

Multi-machine deployment
-------------------------

Start production pfcon:

.. code-block:: bash

    $> ./deploy.sh -O kubernetes -T nfs -S <NFS export dir> -P <NFS server IP addr> up

Tear down production pfcon

.. code-block:: bash

    $> ./deploy.sh -O kubernetes -T nfs -S <NFS export dir> -P <NFS server IP addr> down

