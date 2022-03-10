
from os import path
from setuptools import find_packages, setup


with open(path.join(path.dirname(path.abspath(__file__)), 'README.rst')) as f:
    readme = f.read()

setup(
      name             =   'pfcon',
      version          =   '4.0.2',
      description      =   'ChRIS compute resource Process and File CONtroller',
      long_description =   readme,
      author           =   'FNNDSC',
      author_email     =   'dev@babymri.org',
      url              =   'https://github.com/FNNDSC/pfcon',
      packages         =   find_packages(),
      install_requires =   ['Flask', 'Flask_RESTful', 'environs',
                            'requests', 'keystoneauth1', 'python-keystoneclient',
                            'python-swiftclient'],
      test_suite       =   'nose.collector',
      tests_require    =   ['nose'],
      scripts          =   ['bin/pfcon'],
      license          =   'MIT',
      zip_safe         =   False,
      python_requires  =   '>=3.8'
     )
