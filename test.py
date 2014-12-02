"""
Run chardet on a bunch of documents and see that we get the correct encodings.

:author: Dan Blanchard
:author: Ian Cordasco
"""

from __future__ import with_statement

import sys
import unittest
from os import listdir
from os.path import dirname, isdir, join, realpath, relpath, splitext

from nose.tools import eq_

import chardet


def check_file_encoding(file_name, encoding):
    """ Ensure that we detect the encoding for file_name correctly. """
    with open(file_name, 'rb') as f:
        result = chardet.detect(f.read())
    eq_(result['encoding'].lower(), encoding, ("Expected %s, but got %s for "
                                               "%s" % (encoding,
                                                       result['encoding'],
                                                       file_name)))


def test_encoding_detection():
    base_path = relpath(join(dirname(realpath(__file__)), 'tests'))
    for encoding in listdir(base_path):
        path = join(base_path, encoding)
        # Skip files in tests directory
        if not isdir(path):
            continue
        # Remove language suffixes from encoding if pressent
        encoding = encoding.lower()
        for postfix in ['-arabic', '-bulgarian', '-cyrillic', '-greek',
                        '-hebrew', '-hungarian', '-turkish']:
            if encoding.endswith(postfix):
                encoding = encoding.rpartition(postfix)[0]
                break
        # Test encoding detection for each file we have of encoding for
        for file_name in listdir(path):
            ext = splitext(file_name)[1].lower()
            if ext not in ['.html', '.txt', '.xml', '.srt']:
                continue
            yield check_file_encoding, join(path, file_name), encoding
