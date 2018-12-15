#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import re
import io
from shutil import rmtree

from setuptools import setup, find_packages, Command

here = os.path.abspath(os.path.dirname(__file__))


NAME = 'lru-cache'
DESCRIPTION = 'LRU cache data structure.'
URL = 'https://github.com/vpaliy/lru-cache'
EMAIL = 'vpaliy97@gmail.com'
AUTHOR = 'Vasyl Paliy'
REQUIRES_PYTHON = '>=2.7',
VERSION = None

with io.open(os.path.join(here, 'lru', '__init__.py'), encoding='utf-8') as fp:
  VERSION = re.compile(r".*__version__ = '(.*?)'", re.S).match(fp.read()).group(1)

try:
  with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = '\n' + f.read()
except IOError:
    long_description = str()


class UploadCommand(Command):
  """Support setup.py upload."""

  description = 'Build and publish the package.'
  user_options = []

  @staticmethod
  def status(s):
    """Prints things in bold."""
    print('\033[1m{0}\033[0m'.format(s))

  def initialize_options(self):
    pass

  def finalize_options(self):
    pass

  def run(self):
    try:
      self.status('Removing previous builds…')
      rmtree(os.path.join(here, 'dist'))
    except OSError:
      pass

    self.status('Building Source and Wheel (universal) distribution…')
    os.system('{0} setup.py sdist bdist_wheel --universal'.format(sys.executable))

    self.status('Uploading the package to PyPI via Twine…')
    os.system('twine upload dist/*')

    sys.exit()


setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type='text/markdown',
    author=AUTHOR,
    author_email=EMAIL,
    url=URL,
    license='MIT',
    package_data={
      '': ['*.txt', '*.rst']
    },
    python_requires=REQUIRES_PYTHON,
    packages=find_packages(exclude=('tests',)),
    use_2to3=True,
    include_package_data=True,
    classifiers=[
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'
    ],
    cmdclass={
      'upload': UploadCommand,
    },
)
