"""
Run chardet on a bunch of documents and see that we get the correct encodings.

:author: Dan Blanchard
:author: Ian Cordasco
"""

from __future__ import with_statement

from os import listdir
from os.path import dirname, isdir, join, realpath, relpath, splitext

from nose.tools import eq_

import chardet

EQUIVALENT_ENCODINGS = {'latin1': 'windows-1252', 'windows-1254': 'iso-8859-9'}
LD_EQUIVALENT_ENCODINGS = {'hungarian': {'iso-8859-2': 'windows-1250'}, 'romanian': {'iso-8859-2': 'windows-1250'}} # Language (alphabet) dependend equivalency
MISSING_ENCODINGS = set(['iso-8859-6', 'windows-1256'])

import re

def check_file_encoding(file_name, encoding, lang_name):
    # Ensure that we detect the encoding for file_name correctly.
    with open(file_name, 'rb') as f:
	result = chardet.detect(f.read())
    encoding = EQUIVALENT_ENCODINGS.get(encoding, encoding)
    if lang_name in LD_EQUIVALENT_ENCODINGS:
	encoding = LD_EQUIVALENT_ENCODINGS[lang_name].get(encoding, encoding)
    eq_(result['encoding'].lower(), encoding, ("Expected %s, but got %s for %s" % (encoding, result['encoding'], file_name)))

def test_encoding_detection():
    base_path = relpath(join(dirname(realpath(__file__)), 'tests'))
    for encoding in listdir(base_path):
        path = join(base_path, encoding)
        # Skip files in tests directory
        if not isdir(path):
            continue
        # Remove language suffixes from encoding if pressent
        encoding = encoding.lower()
        for postfix in ['-arabic', '-bulgarian', '-czech', '-croatian', '-cyrillic', '-greek', '-hebrew', '-hungarian', '-polish', '-romanian', '-slovak', '-slovene', '-turkish']:
            if encoding.endswith(postfix):
                encoding = encoding.rpartition(postfix)[0]
                break
        # Skip directories for encodings we don't handle yet.
        if encoding in MISSING_ENCODINGS:
            continue
        # Test encoding detection for each file we have of encoding for
        for file_name in listdir(path):
            ext = splitext(file_name)[1].lower()
            if ext not in ['.html', '.txt', '.xml', '.srt']:
                continue
            yield check_file_encoding, join(path, file_name), encoding, postfix[1:]
