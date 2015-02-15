import sys

sys.path.insert(0, '..')

from chardet.universaldetector import UniversalDetector

u = UniversalDetector()
with open(sys.argv[1], 'r') as f:
    txt = f.read()
    u.reset()
    u.feed(txt)
    u.close()
    print u.result
