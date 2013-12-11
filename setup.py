from setuptools import setup

# Patch distutils if it can't cope with the "classifiers"
# keyword (prior to python 2.3.0):
from distutils.dist import DistributionMetadata
if not hasattr(DistributionMetadata, 'classifiers'):
    DistributionMetadata.classifiers = None

def readme():
    with open('README.rst') as f:
        return f.read()

setup(
    name='chardet',
    version='2.1.1',
    description='Universal encoding detector',
    long_description=readme(),
    author='Mark Pilgrim',
    author_email='mark@diveintomark.org',
    url='https://github.com/bsidhom/python-chardet',
    license="LGPL",
    platforms=['POSIX', 'Windows'],
    keywords=['encoding', 'i18n', 'xml'],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Other Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing :: Linguistic",
        ],
    scripts=['bin/chardetect.py'],
    packages=['chardet']
    )
