
from logging.config import dictConfig
from environs import Env
import os


class Config:
    """
    Base configuration
    """
    STATIC_FOLDER = 'static'
    DEBUG = False
    TESTING = False
    SERVER_VERSION = "3.2.0"

    def __init__(self):
        # Environment variables
        env = Env()
        env.read_env()  # also read .env file, if it exists

        self.STORE_ENV = env('STORE_ENV', 'mount') or os.environ.get('STORE_ENV')
        if self.STORE_ENV == 'mount':
            self.STORE_BASE = '/home/localuser/storeBase'

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
                    'level': 'DEBUG',
                    'handlers': ['console_simple', 'file'],
                    'propagate': False
                    # required to avoid double logging with root logger
                },
            }
        })

        # EXTERNAL SERVICES
        self.COMPUTE_SERVICE_URL = os.environ.get('COMPUTE_SERVICE_URL') if os.environ.get('COMPUTE_SERVICE_URL') is not None \
                                   else 'http://pman-test-moc.k-apps.osh.massopen.cloud/api/v1/'
        


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

        # EXTERNAL SERVICES
        self.COMPUTE_SERVICE_URL = env('COMPUTE_SERVICE_URL')
