"""
Standalone worker script that runs inside a container to perform
asynchronous file operations for fslink and swift storage modes.

Subcommands:
    copy   — fetch input files (default when no subcommand given)
    upload — upload output files to Swift
    delete — delete job data from storebase

Usage:
    python -m pfcon.copy_worker /share/outgoing               (copy, default)
    python -m pfcon.copy_worker copy /share/outgoing           (copy, explicit)
    python -m pfcon.copy_worker upload /share/outgoing         (upload)
    python -m pfcon.copy_worker delete /share/outgoing         (delete)

Inside the container:
    /share/incoming  -> shared filesystem root (read-only, fslink copy only)
    /share/outgoing  -> storebase key directory (read-write)

Copy mode reads job parameters from /share/outgoing/job_params.json,
fetches input files into /share/outgoing/incoming/, and exits 0 on success.

Upload mode reads parameters from /share/outgoing/upload_params.json,
uploads output files from /share/outgoing/outgoing/ to Swift, and exits 0.
"""

import json
import os
import sys
import logging

from pfcon.storage.fslink_storage import FSLinkStorage
from pfcon.storage.swift_storage import SwiftStorage
from pfcon.delete_worker import do_delete


logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def _get_swift_config():
    """Build a Swift config dict from environment variables."""
    return {
        'SWIFT_CONTAINER_NAME': os.environ['SWIFT_CONTAINER_NAME'],
        'SWIFT_CONNECTION_PARAMS': {
            'user': os.environ['SWIFT_USERNAME'],
            'key': os.environ['SWIFT_KEY'],
            'authurl': os.environ['SWIFT_AUTH_URL'],
        }
    }


def do_copy(key_dir):
    """Fetch input files into the storebase key directory."""
    params_file = os.path.join(key_dir, 'job_params.json')

    with open(params_file) as f:
        params = json.load(f)

    job_id = params['jid']
    input_dirs = params['input_dirs']
    storage_env = params['storage_env']
    job_output_path = params['output_dir'].strip('/')

    incoming_dir = os.path.join(key_dir, 'incoming')
    os.makedirs(incoming_dir, exist_ok=True)

    logger.info(f'Starting file fetch ({storage_env}) for job {job_id}')

    if storage_env == 'fslink':
        config = {'STOREBASE_MOUNT': '/share/incoming'}
        storage = FSLinkStorage(config)
        d_info = storage.store_data(job_id, incoming_dir, input_dirs,
                                    job_output_path=job_output_path)

    elif storage_env == 'swift':
        config = _get_swift_config()
        storage = SwiftStorage(config)
        d_info = storage.store_data(job_id, incoming_dir, input_dirs,
                                    job_output_path=job_output_path)

        outgoing_dir = os.path.join(key_dir, 'outgoing')
        os.makedirs(outgoing_dir, exist_ok=True)
    else:
        logger.error(f'Unsupported storage_env: {storage_env}')
        sys.exit(1)

    logger.info(f'File fetch completed for job {job_id}: {d_info}')


def do_upload(key_dir):
    """Upload output files from the storebase key directory to Swift."""
    params_file = os.path.join(key_dir, 'upload_params.json')

    with open(params_file) as f:
        params = json.load(f)

    job_id = params['jid']
    job_output_path = params['job_output_path']

    outgoing_dir = os.path.join(key_dir, 'outgoing')

    logger.info(f'Starting Swift upload for job {job_id} to {job_output_path}')

    config = _get_swift_config()
    storage = SwiftStorage(config)
    storage.upload_data(job_id, outgoing_dir, job_output_path=job_output_path)

    logger.info(f'Swift upload completed for job {job_id}')


def main():
    args = sys.argv[1:]

    if not args:
        print(f'Usage: {sys.argv[0]} [copy|upload] <key_dir>', file=sys.stderr)
        sys.exit(1)

    # If first arg is a subcommand, use it; otherwise default to 'copy'
    if args[0] in ('copy', 'upload', 'delete'):
        subcommand = args[0]
        if len(args) < 2:
            print(f'Usage: {sys.argv[0]} {subcommand} <key_dir>',
                  file=sys.stderr)
            sys.exit(1)
        key_dir = args[1]
    else:
        subcommand = 'copy'
        key_dir = args[0]

    if subcommand == 'copy':
        do_copy(key_dir)
    elif subcommand == 'upload':
        do_upload(key_dir)
    elif subcommand == 'delete':
        do_delete(key_dir)


if __name__ == '__main__':
    main()
