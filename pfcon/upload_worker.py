"""
Standalone upload worker script that runs inside a container to perform the
Swift upload operation asynchronously.

Usage:
    python -m pfcon.upload_worker /share/outgoing

Inside the container:
    /share/outgoing  -> storebase key directory (read-write)

The script reads upload parameters from /share/outgoing/upload_params.json,
uploads output files from /share/outgoing/outgoing/ to Swift object storage,
and exits with 0 on success or non-zero on failure.
"""

import json
import os
import sys
import logging

from pfcon.storage.swift_storage import SwiftStorage


logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def main():
    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} <key_dir>', file=sys.stderr)
        sys.exit(1)

    key_dir = sys.argv[1]  # /share/outgoing
    params_file = os.path.join(key_dir, 'upload_params.json')

    with open(params_file) as f:
        params = json.load(f)

    job_id = params['jid']
    job_output_path = params['job_output_path']

    outgoing_dir = os.path.join(key_dir, 'outgoing')

    logger.info(f'Starting Swift upload for job {job_id} to {job_output_path}')

    config = {
        'SWIFT_CONTAINER_NAME': os.environ['SWIFT_CONTAINER_NAME'],
        'SWIFT_CONNECTION_PARAMS': {
            'user': os.environ['SWIFT_USERNAME'],
            'key': os.environ['SWIFT_KEY'],
            'authurl': os.environ['SWIFT_AUTH_URL'],
        }
    }
    storage = SwiftStorage(config)
    storage.upload_data(job_id, outgoing_dir, job_output_path=job_output_path)

    logger.info(f'Swift upload completed for job {job_id}')


if __name__ == '__main__':
    main()
