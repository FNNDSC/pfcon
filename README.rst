################
pfcon  v3.0.0.0
################

.. image:: https://github.com/fnndsc/pfcon/workflows/CI/badge.svg
    :target: https://github.com/fnndsc/pfcon/actions

.. contents:: Table of Contents

********
Overview
********

This repository provides ``pfcon`` -- a controlling service that acts as the interface to remote ``pman`` and ``pfioh`` services.

pfcon
=====

Most simply, local data can be pushed to ``pfcon`` (which is in turn forwarded to the controlled ``pfioh`` service), then some process is run on this data in the remote space using the controlled ``pman`` service. The resultant data can then be downloaded back to a local target space.

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

Using the ``fnndsc/pfcon`` dock
===============================

The easiest option however, is to just use the ``fnndsc/pfcon`` dock.

.. code-block:: bash

    docker pull fnndsc/pfcon:dev
    
and then run

.. code-block:: bash

    docker run --name pfcon -p 5005:5005 --rm -ti fnndsc/pfcon:dev

*****
Usage
*****

For usage of  ``pfcon``, consult the relevant wiki pages.

``pfcon`` usage
===============

For ``pfcon`` detailed information, see the `pfcon wiki page <https://github.com/FNNDSC/pfcon/wiki/pfcon-overview>`_.

.. code-block:: html

        [--ip <IP>]                            

        The IP interface on which to listen. Default %s.

        [--port <port>]
        The port on which to listen. Defaults to '5055'.

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

********
EXAMPLES
********

Start ``pfcon`` in forever mode:

.. code-block:: bash

            pfcon                                                   \\
                --port 5005                                         \\
                --verbosity 1                                       \\
                --ip 127.0.0.1
