"""
S3-compatible storage manager module.

Supports any S3-compatible backend: AWS S3, MinIO, Ceph RGW, SeaweedFS, or
Azure Blob Storage via S3Proxy gateway.

NOTE on boto3 >= 1.36.0 (January 2025): AWS enabled automatic CRC checksums on
PutObject and checksum validation on GetObject by default. This breaks all
S3-compatible services (MinIO, Ceph, S3Proxy, etc.) because their ETags are not
MD5 hashes. We disable this via botocore.config.Config below.
"""

import logging
import os
import time
from typing import AnyStr

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)


# boto3 config for S3-compatible backends:
# - path addressing: required for non-AWS endpoints (no virtual-hosted bucket DNS)
# - checksum disabled: boto3 >= 1.36.0 auto-CRC breaks non-AWS S3 implementations
_S3_CLIENT_CONFIG = Config(
    s3={'addressing_style': 'path'},
    request_checksum_calculation='when_required',
    response_checksum_validation='when_required',
)


class S3Manager(object):

    def __init__(self, bucket_name: str, conn_params: dict):
        self.bucket_name = bucket_name
        self.conn_params = conn_params
        self._client = None

    def get_client(self):
        """
        Connect to S3-compatible storage and return the client object.
        """
        if self._client is not None:
            return self._client
        for i in range(5):
            try:
                self._client = boto3.client(
                    's3',
                    endpoint_url=self.conn_params.get('endpoint_url'),
                    aws_access_key_id=self.conn_params.get('access_key'),
                    aws_secret_access_key=self.conn_params.get('secret_key'),
                    region_name=self.conn_params.get('region_name', 'us-east-1'),
                    config=_S3_CLIENT_CONFIG,
                )
            except ClientError as e:
                logger.error(str(e))
                if i == 4:
                    raise
                time.sleep(0.4)
            else:
                return self._client

    def create_container(self) -> None:
        """
        Create the S3 bucket if it does not already exist.
        """
        client = self.get_client()
        try:
            client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                create_kwargs = {'Bucket': self.bucket_name}
                region = self.conn_params.get('region_name')
                if region and region != 'us-east-1':
                    create_kwargs['CreateBucketConfiguration'] = {
                        'LocationConstraint': region
                    }
                client.create_bucket(**create_kwargs)
            else:
                logger.error(str(e))
                raise

    def ls(self, path: str) -> list[str]:
        """
        Return a list of object keys in the bucket with the given path as prefix.
        """
        l_ls = []
        if not path:
            return l_ls
        client = self.get_client()
        for i in range(5):
            try:
                paginator = client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=self.bucket_name, Prefix=path)
                for page in pages:
                    for obj in page.get('Contents', []):
                        l_ls.append(obj['Key'])
            except ClientError as e:
                logger.error(str(e))
                if i == 4:
                    raise
                time.sleep(0.4)
            else:
                break
        return l_ls

    def path_exists(self, path: str) -> bool:
        """
        Return True if any objects exist under the given path prefix.
        """
        client = self.get_client()
        for i in range(5):
            try:
                resp = client.list_objects_v2(
                    Bucket=self.bucket_name, Prefix=path, MaxKeys=1
                )
                return resp.get('KeyCount', 0) > 0
            except ClientError as e:
                logger.error(str(e))
                if i == 4:
                    raise
                time.sleep(0.4)

    def obj_exists(self, file_path: str) -> bool:
        """
        Return True if an object exists at the exact key.
        """
        client = self.get_client()
        for i in range(5):
            try:
                client.head_object(Bucket=self.bucket_name, Key=file_path)
            except ClientError as e:
                if e.response['Error']['Code'] == '404':
                    return False
                logger.error(str(e))
                if i == 4:
                    raise
                time.sleep(0.4)
            else:
                return True

    def upload_obj(self, file_path: str, contents: AnyStr,
                   content_type: str | None = None) -> None:
        """
        Upload data to S3 at the given key.
        """
        if isinstance(contents, str):
            contents = contents.encode('utf-8')
        client = self.get_client()
        put_kwargs = {
            'Bucket': self.bucket_name,
            'Key': file_path,
            'Body': contents,
        }
        if content_type:
            put_kwargs['ContentType'] = content_type
        for i in range(5):
            try:
                client.put_object(**put_kwargs)
            except ClientError as e:
                logger.error(str(e))
                if i == 4:
                    raise
                time.sleep(0.4)
            else:
                break

    def download_obj(self, file_path: str) -> bytes:
        """
        Download object data from S3.
        """
        client = self.get_client()
        for i in range(5):
            try:
                resp = client.get_object(Bucket=self.bucket_name, Key=file_path)
                return resp['Body'].read()
            except ClientError as e:
                logger.error(str(e))
                if i == 4:
                    raise
                time.sleep(0.4)

    def copy_obj(self, src: str, dst: str) -> None:
        """
        Copy an object within the same bucket.
        """
        client = self.get_client()
        copy_source = {'Bucket': self.bucket_name, 'Key': src}
        for i in range(5):
            try:
                client.copy_object(
                    Bucket=self.bucket_name,
                    Key=dst,
                    CopySource=copy_source,
                )
            except ClientError as e:
                logger.error(str(e))
                if i == 4:
                    raise
                time.sleep(0.4)
            else:
                break

    def delete_obj(self, file_path: str) -> None:
        """
        Delete an object from S3.
        """
        client = self.get_client()
        for i in range(5):
            try:
                client.delete_object(Bucket=self.bucket_name, Key=file_path)
            except ClientError as e:
                logger.error(str(e))
                if i == 4:
                    raise
                time.sleep(0.4)
            else:
                break
