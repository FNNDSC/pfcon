############
pfcon v3.2.0
############

.. image:: https://github.com/fnndsc/pfcon/workflows/CI/badge.svg
    :target: https://github.com/fnndsc/pfcon/actions

.. contents:: Table of Contents


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

Note: On a Linux machine make sure to add your computer user to the ``docker`` group
Consult this page https://docs.docker.com/engine/install/linux-postinstall/


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

On MAC OS Docker Desktop includes a standalone Kubernetes server and client. Consult this page https://docs.docker.com/desktop/kubernetes/

On Linux there is a simple MicroK8s installation. Consult this page https://microk8s.io
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

``pfcon`` usage
===============

.. code-block:: html

        [--ip <IP>]                            

        The IP interface on which to listen. Default %s.

        [--port <port>]
        The port on which to listen. Defaults to '5055'.

        [--storeBase <storagePath>]
        A file system location in the network space accessible to ``pfcon``
        that is used to unpack received files and also store results of
        processing.

        [--enableTokenAuth]
        Enables token based authorization and can be configured to look for a .ini
        file or an openshift secret.

        [--tokenPath <tokenPath>]
        Specify the absolute path to the token in the file system.
        By default, this looks for the pfconConfig.ini file in the current working directory.

        [--man <manpage>]
        Internal man page with more detail on specific calls.

        [-x|--desc]                                     
        Provide an overview help page.

        [-y|--synopsis]
        Provide a synopsis help summary.

        [--version]
        Print internal version number and exit.

        [-v|--verbosity <level>]
        Set the verbosity level. "0" typically means no/minimal output. Allows for
        more fine tuned output control as opposed to '--quiet' that effectively
        silences everything.
