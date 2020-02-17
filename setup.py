#!/usr/bin/env python

import sys

from setuptools import setup


needs_pytest = {'pytest', 'test', 'ptr'}.intersection(sys.argv)
pytest_runner = ['pytest-runner'] if needs_pytest else []

if __name__ == "__main__":
    setup()
