from logging.config import dictConfig
from environs import Env


from importlib.metadata import Distribution

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

        self.STORE_ENV = env('STORE_ENV', 'mount')
        if self.STORE_ENV == 'mount':
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
                    'class': 'logging.StreamHandle',
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
