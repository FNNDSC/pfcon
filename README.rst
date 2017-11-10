###################
pfcon  v1.3.17.dev0
###################

.. image:: https://badge.fury.io/py/pfcon.svg
    :target: https://badge.fury.io/py/pfcon

.. image:: https://travis-ci.org/FNNDSC/pfcon.svg?branch=master
    :target: https://travis-ci.org/FNNDSC/pfcon

.. image:: https://img.shields.io/badge/python-3.5%2B-blue.svg
    :target: https://badge.fury.io/py/pfcon

.. contents:: Table of Contents

********
Overview
********

This repository provides ``pfcon`` -- a controlling service that speaks to remote ``pman`` and ``pfioh`` services. This is the bleeding edge branch.

pfcon
=====

Most simply, ``pfcon`` pushes local data to a remote location (by talking to a remote ``pfioh`` service), runs some process on this data in the remote space using ``pman``, and then copies the resultant data back to a local target space.

It can be used to query and control the following (for example):

- *state*: Is job <XYZ> still running?
- *result*: What is the stdout (or stderr) from job <XYZ>?
- *control*: Kill job <XYZ>

************
Installation
************

Installation is relatively straightforward, and we recommend using either python virtual environments or docker.

Python Virtual Environment
==========================

On Ubuntu, install the Python virtual environment creator

.. code-block:: bash

  sudo apt install virtualenv

Then, create a directory for your virtual environments e.g.:

.. code-block:: bash

  mkdir ~/python-envs

You might want to add to your .bashrc file these two lines:

.. code-block:: bash

    export WORKON_HOME=~/python-envs
    source /usr/local/bin/virtualenvwrapper.sh

Then you can source your .bashrc and create a new Python3 virtual environment:

.. code-block:: bash

    source .bashrc
    mkvirtualenv --python=python3 python_env

To activate or "enter" the virtual env:

.. code-block:: bash

    workon python_env

To deactivate virtual env:

.. code-block:: bash

    deactivate

Using the ``fnndsc/ubuntu-python3`` dock
========================================

We provide a slim docker image with python3 based off Ubuntu. If you want to play inside this dock and install ``pman`` manually, do

.. code-block:: bash

    docker pull fnndsc/ubuntu-python3

This docker has an entry point ``python3``. To enter the dock at a different entry and install your own stuff:

.. code-block:: bash

   docker run -ti --entrypoint /bin/bash fnndsc/ubuntu-python3
   
Now, install ``pman`` and friends using ``pip``

.. code-block:: bash

   apt update && \
   apt install -y libssl-dev libcurl4-openssl-dev librtmp-dev && \
   pip install pfcon
   
**If you do the above, remember to** ``commit`` **your changes to the docker image otherwise they'll be lost when you remove the dock instance!**

.. code-block:: bash

  docker commit <container-ID> local/ubuntu-python3-pfcon
  
 where ``<container-ID>`` is the ID of the above container.
  

Using the ``fnndsc/pfcon`` dock
===============================

The easiest option however, is to just use the ``fnndsc/pfcon`` dock.

.. code-block:: bash

    docker pull fnndsc/pfcon
    
and then run

.. code-block:: bash

    docker run --name pfcon -v /home:/Users --rm -ti fnndsc/pfcon --forever --httpResponse

*****
Usage
*****

For usage of  ``pfcon``, consult the relevant wiki pages.

``pfcon`` usage
===============

For ``pfcon`` detailed information, see the `pfcon wiki page <https://github.com/FNNDSC/pfcon/wiki/pfcon-overview>`_.




