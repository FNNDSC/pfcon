"""
Standalone upload worker script that runs inside a container to perform the
object storage upload operation asynchronously (Swift or S3).

Usage:
    python -m pfcon.upload_worker /share/outgoing

Inside the container:
    /share/outgoing  -> storebase key directory (read-write)

The script reads upload parameters from /share/outgoing/upload_params.json,
uploads output files from /share/outgoing/outgoing/ to object storage,
and exits with 0 on success or non-zero on failure.
"""

import json
import os
import sys
import logging

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
    storage_env = params.get('storage_env', 'swift')

    outgoing_dir = os.path.join(key_dir, 'outgoing')

    logger.info(f'Starting {storage_env} upload for job {job_id} to '
                f'{job_output_path}')

    if storage_env == 's3':
        config = {
            'S3_BUCKET_NAME': os.environ['S3_BUCKET_NAME'],
            'S3_CONNECTION_PARAMS': {
                'endpoint_url': os.environ['S3_ENDPOINT_URL'],
                'access_key': os.environ['S3_ACCESS_KEY'],
                'secret_key': os.environ['S3_SECRET_KEY'],
                'region_name': os.environ.get('S3_REGION_NAME', 'us-east-1'),
            }
        }
        from pfcon.storage.s3_storage import S3Storage

        storage = S3Storage(config)
    else:
        config = {
            'SWIFT_CONTAINER_NAME': os.environ['SWIFT_CONTAINER_NAME'],
            'SWIFT_CONNECTION_PARAMS': {
                'user': os.environ['SWIFT_USERNAME'],
                'key': os.environ['SWIFT_KEY'],
                'authurl': os.environ['SWIFT_AUTH_URL'],
            }
        }
        from pfcon.storage.swift_storage import SwiftStorage

        storage = SwiftStorage(config)

    storage.upload_data(job_id, outgoing_dir, job_output_path=job_output_path)

    logger.info(f'{storage_env} upload completed for job {job_id}')


if __name__ == '__main__':
    main()
