
from logging.config import dictConfig
from environs import Env

from importlib.metadata import Distribution
from .swiftmanager import SwiftManager


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
            if self.STORAGE_ENV != 'swift':
                raise ValueError(f"Unsupported value '{self.STORAGE_ENV}' for STORAGE_ENV")
        else:
            self.STORAGE_ENV = env('STORAGE_ENV', 'zipfile')
            if self.STORAGE_ENV != 'zipfile':
                raise ValueError(f"Unsupported value '{self.STORAGE_ENV}' for STORAGE_ENV")

        self.STORE_BASE = env('STOREBASE', '/var/local/storeBase')
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
                'file': {
                    'level': 'DEBUG',
                    'class': 'logging.FileHandler',
                    'filename': '/tmp/debug.log',
                    'formatter': 'simple'
                }
            },
            'loggers': {
                '': {  # root logger
                    'level': 'INFO',
                    'handlers': ['console_simple'],
                },
                'pfcon': {  # pfcon package logger
                    'level': 'INFO',
                    'handlers': ['file'],
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
