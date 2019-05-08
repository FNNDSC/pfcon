###############
pfcon  v2.2.0.0
###############

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

This repository provides ``pfcon`` -- a controlling service that speaks to remote ``pman`` and ``pfioh`` services.

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

.. code-block:: html

        [--ip <IP>]                            

        The IP interface on which to listen. Default %s.

        [--port <port>]
        The port on which to listen. Defaults to '5055'.

        [--man <manpage>]
        Internal man page with more detail on specific calls.

        [--forever]
        Start service and do not terminate.

        [--httpResponse]
        Send return strings as HTTP formatted replies with content-type html.

        [--cordBlockSeconds <blockSeconds>]
        The number of seconds to block/wait internally in the coordination loop.
        This is the time between ``pfioh`` has indicated successful unpack of file
        data and the call to ``pman`` to start processing.

        [--configFileLoad <file>]
        Load configuration information from the JSON formatted <file>.

        [--configFileSave <file>]
        Save configuration information to the JSON formatted <file>.

        [-x|--desc]                                     
        Provide an overview help page.

        [-y|--synopsis]
        Provide a synopsis help summary.

        [--version]
        Print internal version number and exit.

        [--debugToDir <dir>]
        A directory to contain various debugging output -- these are typically
        JSON object strings capturing internal state. If empty string (default)
        then no debugging outputs are captured/generated. If specified, then
        ``pfcon`` will check for dir existence and attempt to create if
        needed.

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
                --forever                                           \\
                --port 5005                                         \\
                --httpResponse                                      \\
                --verbosity 1                                       \\
                --debugToDir /tmp                                   \\
                --ip 127.0.0.1


