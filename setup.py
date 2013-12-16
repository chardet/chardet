#!/usr/bin/env python
from setuptools import setup

from chardet import __version__


def readme():
    with open('README.rst') as f:
        return f.read()


setup(name='chardet',
      version=__version__,
      description='Universal encoding detector for Python 2 and 3',
      long_description=readme(),
      author='Mark Pilgrim',
      author_email='mark@diveintomark.org',
      maintainer='Ian Cordasco',
      maintainer_email='graffatcolmingov@gmail.com',
      url='https://github.com/erikrose/chardet',
      license="LGPL",
      keywords=['encoding', 'i18n', 'xml'],
      classifiers=["Development Status :: 4 - Beta",
                   "Intended Audience :: Developers",
                   ("License :: OSI Approved :: GNU Library or Lesser General" +
                    " Public License (LGPL)"),
                   "Operating System :: OS Independent",
                   "Programming Language :: Python",
                   ("Topic :: Software Development :: Libraries :: Python " +
                    "Modules"),
                   "Topic :: Text Processing :: Linguistic"],
      scripts=['bin/chardetect'],
      packages=['chardet'],
      entry_points={'console_scripts': ['chardetect = chardet.chardetect:main']})
