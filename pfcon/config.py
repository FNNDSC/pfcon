
from logging.config import dictConfig
from importlib.metadata import Distribution

from environs import Env

from .storage.swiftmanager import SwiftManager
from .compute.memsize import Memsize
from .compute._helpers import get_storebase_from_docker


pkg = Distribution.from_name(__package__)


class Config:
    """
    Base configuration
    """
    STATIC_FOLDER = 'static'
    DEBUG = False
    TESTING = False
    SERVER_VERSION = pkg.version

    def __init__(self):
        # Environment variables
        env = Env()
        env.read_env()  # also read .env file, if it exists

        self.PFCON_INNETWORK = env.bool('PFCON_INNETWORK', False)

        if self.PFCON_INNETWORK:
            self.STORAGE_ENV = env('STORAGE_ENV', 'swift')
            if self.STORAGE_ENV not in ('swift', 'filesystem', 'fslink'):
                raise ValueError(f"Unsupported value '{self.STORAGE_ENV}' for STORAGE_ENV")
        else:
            self.STORAGE_ENV = env('STORAGE_ENV', 'zipfile')
            if self.STORAGE_ENV != 'zipfile':
                raise ValueError(f"Unsupported value '{self.STORAGE_ENV}' for STORAGE_ENV")

        self.STOREBASE_MOUNT = env('STOREBASE_MOUNT', '/var/local/storeBase')

        self.JOB_LOGS_TAIL = env.int('JOB_LOGS_TAIL', 1000)
        self.JOB_LABELS = env.dict('JOB_LABELS', {})
        self.IGNORE_LIMITS = env.bool('IGNORE_LIMITS', False)
        self.CONTAINER_USER = env('CONTAINER_USER', None)
        self.ENABLE_HOME_WORKAROUND = env.bool('ENABLE_HOME_WORKAROUND', False)
        shm_size = env.int('SHM_SIZE', None)
        self.SHM_SIZE = None if shm_size is None else Memsize(shm_size)

        self.CONTAINER_ENV = env('CONTAINER_ENV', 'docker')
        if self.CONTAINER_ENV == 'podman':  # podman is just an alias for docker
            self.CONTAINER_ENV = 'docker'

        default_cv_type = 'docker_local_volume' if self.CONTAINER_ENV == 'docker' else None
        self.COMPUTE_VOLUME_TYPE = env('COMPUTE_VOLUME_TYPE', default_cv_type)
        self.VOLUME_NAME = env('VOLUME_NAME', None)

        self.REMOVE_JOBS = env.bool('REMOVE_JOBS', True)

        if self.COMPUTE_VOLUME_TYPE == 'host':
            self.STOREBASE = env('STOREBASE')

        if self.COMPUTE_VOLUME_TYPE == 'docker_local_volume':
            pfcon_selector = env('PFCON_SELECTOR', 'org.chrisproject.role=pfcon')
            self.STOREBASE = get_storebase_from_docker(self.STOREBASE_MOUNT,
                                                       pfcon_selector, self.VOLUME_NAME)

        if self.COMPUTE_VOLUME_TYPE == 'kubernetes_pvc':
            if not self.VOLUME_NAME:
                raise ValueError('VOLUME_NAME must be given because '
                                 'COMPUTE_VOLUME_TYPE=kubernetes_pvc')

        if self.CONTAINER_ENV == 'swarm':
            docker_host = env('DOCKER_HOST', '')
            if docker_host:
                self.DOCKER_HOST = docker_host
            docker_tls_verify = env.int('DOCKER_TLS_VERIFY', None)
            if docker_tls_verify is not None:
                self.DOCKER_TLS_VERIFY = docker_tls_verify
            docker_cert_path = env('DOCKER_CERT_PATH', '')
            if docker_cert_path:
                self.DOCKER_CERT_PATH = docker_cert_path

        if self.CONTAINER_ENV == 'kubernetes':
            self.JOB_NAMESPACE = env('JOB_NAMESPACE', 'default')
            self.NODE_SELECTOR = env.dict('NODE_SELECTOR', {})
            image_pull_secrets = env('IMAGE_PULL_SECRETS', '')
            self.IMAGE_PULL_SECRETS = None if not image_pull_secrets else image_pull_secrets.split(',')

        if self.CONTAINER_ENV == 'cromwell':
            self.CROMWELL_URL = env('CROMWELL_URL')
            self.TIMELIMIT_MINUTES = env.int('TIMELIMIT_MINUTES')

        if self.CONTAINER_ENV == 'docker':
            # nothing needs to be done!
            # In the above config code for swarm, docker env variables are intercepted pointlessly.
            # To configure Docker Engine/Podman, use the standard env variables for the Docker client.
            pass

        self.env = env


class DevConfig(Config):
    """
    Development configuration
    """
    ENV = 'development'
    DEBUG = True
    TESTING = True

    def __init__(self):
        super().__init__()

        # DEV LOGGING CONFIGURATION
        dictConfig({
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'simple': {
                    'format': '[%(asctime)s] [%(levelname)s]'
                              '[%(module)s:%(lineno)d %(process)d %(thread)d] %(message)s'
                },
            },
            'handlers': {
                'console_simple': {
                    'level': 'INFO',
                    'class': 'logging.StreamHandler',
                    'formatter': 'simple',
                },
                'console_stdout': {
                    'level': 'DEBUG',
                    'class': 'logging.StreamHandler',
                    'stream': 'ext://sys.stdout',
                    'formatter': 'simple'
                }
            },
            'loggers': {
                '': {  # root logger
                    'level': 'INFO',
                    'handlers': ['console_simple'],
                },
                'pfcon': {  # pfcon package logger
                    'level': 'DEBUG',
                    'handlers': ['console_simple', 'console_stdout'],
                    'propagate': False
                    # required to avoid double logging with root logger
                },
            }
        })

        self.SECRET_KEY = 'DevConfig.SECRET_KEY'
        self.PFCON_USER = 'pfcon'
        self.PFCON_PASSWORD = 'pfcon1234'

        # EXTERNAL SERVICES
        self.COMPUTE_SERVICE_URL = self.env('COMPUTE_SERVICE_URL', 'http://pman:5010/api/v1/')

        if self.STORAGE_ENV == 'swift':
            SWIFT_AUTH_URL = self.env('SWIFT_AUTH_URL',
                                      'http://swift_service:8080/auth/v1.0')
            SWIFT_USERNAME = 'chris:chris1234'
            SWIFT_KEY = 'testing'
            self.SWIFT_CONTAINER_NAME = 'users'
            self.SWIFT_CONNECTION_PARAMS = {'user': SWIFT_USERNAME,
                                            'key': SWIFT_KEY,
                                            'authurl': SWIFT_AUTH_URL}
            SwiftManager(self.SWIFT_CONTAINER_NAME,
                         self.SWIFT_CONNECTION_PARAMS).create_container()


class ProdConfig(Config):
    """
    Production configuration
    """
    ENV = 'production'

    def __init__(self):
        super().__init__()

        # PROD LOGGING CONFIGURATION
        dictConfig({
            'version': 1,
            'disable_existing_loggers': False,
            'formatters': {
                'simple': {
                    'format': '[%(asctime)s] [%(levelname)s]'
                              '[%(module)s:%(lineno)d %(process)d %(thread)d] %(message)s'
                },
            },
            'handlers': {
                'console_simple': {
                    'level': 'INFO',
                    'class': 'logging.StreamHandler',
                    'formatter': 'simple',
                },
            },
            'loggers': {
                '': {  # root logger
                    'level': 'INFO',
                    'handlers': ['console_simple'],
                },
                'pfcon': {  # pfcon package logger
                    'level': 'INFO',
                    'handlers': ['console_simple'],
                    'propagate': False
                },
            }
        })

        # Environment variables-based secrets
        # SECURITY WARNING: keep the secret key used in production secret!
        env = self.env
        self.SECRET_KEY = env('SECRET_KEY')
        self.PFCON_USER = env('PFCON_USER')
        self.PFCON_PASSWORD = env('PFCON_PASSWORD')

        # EXTERNAL SERVICES
        self.COMPUTE_SERVICE_URL = env('COMPUTE_SERVICE_URL')

        if self.STORAGE_ENV == 'swift':
            SWIFT_AUTH_URL = env('SWIFT_AUTH_URL')
            SWIFT_USERNAME = env('SWIFT_USERNAME')
            SWIFT_KEY = env('SWIFT_KEY')
            self.SWIFT_CONTAINER_NAME = env('SWIFT_CONTAINER_NAME')
            self.SWIFT_CONNECTION_PARAMS = {'user': SWIFT_USERNAME,
                                            'key': SWIFT_KEY,
                                            'authurl': SWIFT_AUTH_URL}
