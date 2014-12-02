#!/usr/bin/env python
from setuptools import setup

from chardet import __version__


def readme():
    with open('README.rst') as f:
        return f.read()


def requirements():
    with open(req_path) as f:
        reqs = f.read().splitlines()
    return reqs

setup(name='chardet',
      version=__version__,
      description='Universal encoding detector for Python 2 and 3',
      long_description=readme(),
      author='Mark Pilgrim',
      author_email='mark@diveintomark.org',
      maintainer='Daniel Blanchard',
      maintainer_email='dblanchard@ets.org',
      url='https://github.com/chardet/chardet',
      license="LGPL",
      keywords=['encoding', 'i18n', 'xml'],
      classifiers=["Development Status :: 4 - Beta",
                   "Intended Audience :: Developers",
                   ("License :: OSI Approved :: GNU Library or Lesser General"
                    " Public License (LGPL)"),
                   "Operating System :: OS Independent",
                   "Programming Language :: Python",
                   'Programming Language :: Python :: 2',
                   'Programming Language :: Python :: 2.6',
                   'Programming Language :: Python :: 2.7',
                   'Programming Language :: Python :: 3',
                   'Programming Language :: Python :: 3.2',
                   'Programming Language :: Python :: 3.3',
                   ("Topic :: Software Development :: Libraries :: Python "
                    "Modules"),
                   "Topic :: Text Processing :: Linguistic"],
      packages=['chardet'],
      install_requires=requirements(),
      entry_points={'console_scripts':
                    ['chardetect = chardet.chardetect:main']})
