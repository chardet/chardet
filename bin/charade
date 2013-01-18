#!/usr/bin/env python
"""
Script which takes one or more file paths and reports on their detected
encodings

Example::

    % chardetect.py somefile someotherfile
    somefile: windows-1252 with confidence 0.5
    someotherfile: ascii with confidence 1.0

"""
from sys import argv

from charade.universaldetector import UniversalDetector


def description_of(path):
    """Return a string describing the probable encoding of a file."""
    u = UniversalDetector()
    for line in open(path, 'rb'):
        u.feed(line)
    u.close()
    result = u.result
    if result['encoding']:
        return '%s: %s with confidence %s' % (path,
                                              result['encoding'],
                                              result['confidence'])
    else:
        return '%s: no result' % path


def main():
    for path in argv[1:]:
        print(description_of(path))


if __name__ == '__main__':
    main()
