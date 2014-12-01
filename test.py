from __future__ import with_statement

import os
import sys
import unittest

import chardet


class TestCase(unittest.TestCase):
    def __init__(self, file_name, encoding):
        unittest.TestCase.__init__(self)
        self.file_name = file_name
        encoding = encoding.lower()
        for postfix in ['-arabic',
                        '-bulgarian',
                        '-cyrillic',
                        '-greek',
                        '-hebrew',
                        '-hungarian',
                        '-turkish']:
            if encoding.endswith(postfix):
                encoding, _, _ = encoding.rpartition(postfix)
        self.encoding = encoding

    def runTest(self):
        with open(self.file_name, 'rb') as f:
            result = chardet.detect(f.read())
        self.assertEqual(result['encoding'].lower(), self.encoding,
                         "Expected %s, but got %s in %s" %
                         (self.encoding, result['encoding'],
                          self.file_name))


def main():
    suite = unittest.TestSuite()
    if len(sys.argv) > 1:
        base_path = sys.argv[1]
    else:
        base_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'tests')
    for encoding in os.listdir(base_path):
        path = os.path.join(base_path, encoding)
        if not os.path.isdir(path):
            continue
        for file_name in os.listdir(path):
            _, ext = os.path.splitext(file_name)
            if ext not in ['.html', '.txt', '.xml', '.srt']:
                continue
            suite.addTest(TestCase(os.path.join(path, file_name), encoding))
    unittest.TextTestRunner().run(suite)


main()
