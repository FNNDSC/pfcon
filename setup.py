import sys
import os
# Make sure we are running python3.5+
if 10 * sys.version_info[0]  + sys.version_info[1] < 35:
    sys.exit("Sorry, only Python 3.5+ is supported.")

from setuptools import setup


def readme():
    print("Current dir = %s" % os.getcwd())
    print(os.listdir())
    with open('README.rst') as f:
        return f.read()

setup(
      name             =   'pfcon',
      version          =   '2.2.0.2',
      description      =   '(Python) Process and File Controller',
      long_description =   readme(),
      author           =   'Rudolph Pienaar',
      author_email     =   'rudolph.pienaar@gmail.com',
      url              =   'https://github.com/FNNDSC/pfcon',
      packages         =   ['pfcon'],
      install_requires =   ['pycurl', 'pyzmq', 'webob', 'pudb', 'psutil', 'pfurl', 'pfmisc', 'python-swiftclient'],
      test_suite       =   'nose.collector',
      tests_require    =   ['nose'],
      scripts          =   ['bin/pfcon'],
      license          =   'MIT',
      zip_safe         =   False
     )
