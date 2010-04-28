# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""pytest configuration file: we need this to properly remove ressources
cached on test classes, at least until we've proper support for teardown_class
"""
import sys
from os.path import split, splitext
from logilab.common.pytest import PyTester

class CustomPyTester(PyTester):
    def testfile(self, filename, batchmode=False):
        try:
            return super(CustomPyTester, self).testfile(filename, batchmode)
        finally:
            modname = splitext(split(filename)[1])[0]
            try:
                module = sys.modules[modname]
            except KeyError:
                # error during test module import
                return
            for cls in vars(module).values():
                if getattr(cls, '__module__', None) != modname:
                    continue
                clean_repo_test_cls(cls)

def clean_repo_test_cls(cls):
    if 'repo' in cls.__dict__:
        if not cls.repo._shutting_down:
            cls.repo.shutdown()
        del cls.repo
    for clsattr in ('cnx', '_orig_cnx', 'config', '_config', 'vreg', 'schema'):
        if clsattr in cls.__dict__:
            delattr(cls, clsattr)
