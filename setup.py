import os
from setuptools import setup, find_packages

setup(
      name             =   'pfcon',
      version          =   os.getenv('BUILD_VERSION', 'unknown'),
      description      =   'ChRIS compute resource Process and File CONtroller',
      author           =   'FNNDSC',
      author_email     =   'dev@babymri.org',
      url              =   'https://github.com/FNNDSC/pfcon',
      packages         =   find_packages(),
      install_requires =   ['Flask', 'Flask_RESTful', 'environs',
                            'requests', 'keystoneauth1', 'python-keystoneclient',
                            'python-swiftclient', 'PyJWT'],
      license          =   'MIT',
      zip_safe         =   False,
      python_requires  =   '>=3.10.2'
     )
