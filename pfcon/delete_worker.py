"""
Standalone delete worker script that runs inside a container to perform
asynchronous deletion of job data from the storebase.

Usage:
    python -m pfcon.delete_worker /share/outgoing

Inside the container:
    /share/outgoing  -> storebase key directory (read-write)

The script reads delete parameters from /share/outgoing/delete_params.json,
removes the incoming/ and outgoing/ subdirectories and any leftover param
files, and exits with 0 on success or non-zero on failure.
"""

import json
import os
import sys
import logging


logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def _rmtree(path):
    """
    Remove a directory tree using full absolute paths.

    Python 3.13's shutil.rmtree uses dir_fd-based operations (unlinkat syscall)
    which can fail on Docker bind mounts. This implementation avoids that by
    using os.unlink/os.rmdir with full paths.
    """
    for dirpath, dirnames, filenames in os.walk(path, topdown=False):
        for name in filenames:
            os.unlink(os.path.join(dirpath, name))
        for name in dirnames:
            os.rmdir(os.path.join(dirpath, name))
    os.rmdir(path)


def do_delete(key_dir):
    """Delete job data from the storebase key directory."""
    params_file = os.path.join(key_dir, 'delete_params.json')

    with open(params_file) as f:
        params = json.load(f)

    job_id = params['jid']

    logger.info(f'Starting data deletion for job {job_id}')

    for subdir in ('incoming', 'outgoing'):
        path = os.path.join(key_dir, subdir)
        if os.path.isdir(path):
            _rmtree(path)
            logger.info(f'Removed {subdir}/ for job {job_id}')

    # Remove leftover param files
    for fname in ('job_params.json', 'job_params.json.consumed',
                   'upload_params.json', 'delete_params.json'):
        fpath = os.path.join(key_dir, fname)
        if os.path.isfile(fpath):
            os.remove(fpath)

    logger.info(f'Data deletion completed for job {job_id}')


def main():
    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} <key_dir>', file=sys.stderr)
        sys.exit(1)

    key_dir = sys.argv[1]
    do_delete(key_dir)


if __name__ == '__main__':
    main()
