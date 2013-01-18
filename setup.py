try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup  # NOQA

# patch distutils if it can't cope with the "classifiers" or "download_url"
# keywords (prior to python 2.3.0).
from distutils.dist import DistributionMetadata
if not hasattr(DistributionMetadata, 'classifiers'):
    DistributionMetadata.classifiers = None
if not hasattr(DistributionMetadata, 'download_url'):
    DistributionMetadata.download_url = None

package = ['charade']
script = ['bin/charade']

from charade import __version__

setup(
    name='charade',
    version=__version__,
    description='Universal encoding detector for python 2 and 3',
    long_description='\n\n'.join([open('README.rst').read(),
                                  open('HISTORY.rst').read()]),
    author='Mark Pilgrim',
    author_email='mark@diveintomark.org',
    maintainer='Ian Cordasco',
    maintainer_email='graffatcolmingov@gmail.com',
    url='https://github.com/sigmavirus24/charade',
    license="LGPL",
    keywords=['encoding', 'i18n', 'xml'],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Other Environment",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Library or Lesser General Public"
        " License (LGPL)",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing :: Linguistic",
    ],
    scripts=script,
    packages=package,
)
