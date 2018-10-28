"""
Run chardet on a bunch of documents and see that we get the correct encodings.

:author: Dan Blanchard
:author: Ian Cordasco
"""

from __future__ import with_statement

import textwrap
from difflib import ndiff
from io import open
from os import listdir
from os.path import dirname, isdir, join, realpath, relpath, splitext

import pytest
import hypothesis.strategies as st
from hypothesis import given, reject, settings, HealthCheck

import chardet


# TODO: Restore Hungarian encodings (iso-8859-2 and windows-1250) after we
#       retrain model.
MISSING_ENCODINGS = {'iso-8859-2', 'iso-8859-6', 'windows-1250',
                     'windows-1254', 'windows-1256'}
EXPECTED_FAILURES = {'tests/iso-8859-7-greek/disabled.gr.xml',
                     'tests/iso-8859-9-turkish/divxplanet.com.xml',
                     'tests/iso-8859-9-turkish/subtitle.srt',
                     'tests/iso-8859-9-turkish/wikitop_tr_ISO-8859-9.txt'}

def gen_test_params():
    """Yields tuples of paths and encodings to use for test_encoding_detection"""
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
        # Skip directories for encodings we don't handle yet.
        if encoding in MISSING_ENCODINGS:
            continue
        # Test encoding detection for each file we have of encoding for
        for file_name in listdir(path):
            ext = splitext(file_name)[1].lower()
            if ext not in ['.html', '.txt', '.xml', '.srt']:
                continue
            full_path = join(path, file_name)
            test_case = full_path, encoding
            if full_path in EXPECTED_FAILURES:
                test_case = pytest.mark.xfail(test_case)
            yield test_case


@pytest.mark.parametrize ('file_name, encoding', gen_test_params())
def test_encoding_detection(file_name, encoding):
    with open(file_name, 'rb') as f:
        input_bytes = f.read()
        result = chardet.detect(input_bytes)
        try:
            expected_unicode = input_bytes.decode(encoding)
        except LookupError:
            expected_unicode = ''
        try:
            detected_unicode = input_bytes.decode(result['encoding'])
        except (LookupError, UnicodeDecodeError, TypeError):
            detected_unicode = ''
    if result:
        encoding_match = (result['encoding'] or '').lower() == encoding
    else:
        encoding_match = False
    # Only care about mismatches that would actually result in different
    # behavior when decoding
    if not encoding_match and expected_unicode != detected_unicode:
        wrapped_expected = '\n'.join(textwrap.wrap(expected_unicode, 100)) + '\n'
        wrapped_detected = '\n'.join(textwrap.wrap(detected_unicode, 100)) + '\n'
        diff = ''.join(ndiff(wrapped_expected.splitlines(True),
                             wrapped_detected.splitlines(True)))
    else:
        diff = ''
        encoding_match = True
    assert encoding_match, ("Expected %s, but got %s for %s.  Character "
                            "differences: \n%s" % (encoding,
                                                   result,
                                                   file_name,
                                                   diff))


@pytest.mark.parametrize('enc', [
    'ascii', 'utf-8', 'utf-16', 'utf-32',
    'iso-8859-7', 'iso-8859-8', 'windows-1255',
])
@settings(suppress_health_check=[HealthCheck.filter_too_much])
@given(txt=st.text(min_size=1))
def test_detect_all_and_detect_one_always_agree(enc, txt):
    try:
        data = txt.encode(enc)
    except UnicodeEncodeError:
        reject()
    result = chardet.detect(data)
    results = chardet.detect_all(data)
    assert result['encoding'] == results[0]['encoding'], \
        '%s != %s[0]' % (result, results)
