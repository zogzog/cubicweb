"""pytest configuration file: we need this to properly remove ressources
cached on test classes, at least until we've proper support for teardown_class
"""
import sys
from os.path import split, splitext
from logilab.common.pytest import PyTester

from cubicweb.etwist.server import _gc_debug

class CustomPyTester(PyTester):
    def testfile(self, filename, batchmode=False):
        try:
            return super(CustomPyTester, self).testfile(filename, batchmode)
        finally:
            modname = splitext(split(filename)[1])[0]
            for cls in vars(sys.modules[modname]).values():
                if getattr(cls, '__module__', None) != modname:
                    continue
                clean_repo_test_cls(cls)
            #_gc_debug()

def clean_repo_test_cls(cls):
    if 'repo' in cls.__dict__:
        if cls.repo._shutting_down:
            cls.repo.shutdown()
        del cls.repo
    for clsattr in ('cnx', '_orig_cnx', 'config', '_config', 'vreg', 'schema'):
        if clsattr in cls.__dict__:
            delattr(cls, clsattr)
