# copyright 2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from unittest import TestCase
import os.path as osp
import pickle

from six import PY2

from logilab.common.shellutils import tempdir

from cubicweb import Binary


class BinaryTC(TestCase):
    def test_init(self):
        Binary()
        Binary(b'toto')
        Binary(bytearray(b'toto'))
        if PY2:
            Binary(buffer('toto'))  # noqa: F821
        else:
            Binary(memoryview(b'toto'))
        with self.assertRaises((AssertionError, TypeError)):
            # TypeError is raised by BytesIO if python runs with -O
            Binary(u'toto')

    def test_write(self):
        b = Binary()
        b.write(b'toto')
        b.write(bytearray(b'toto'))
        if PY2:
            b.write(buffer('toto'))  # noqa: F821
        else:
            b.write(memoryview(b'toto'))
        with self.assertRaises((AssertionError, TypeError)):
            # TypeError is raised by BytesIO if python runs with -O
            b.write(u'toto')

    def test_gzpickle_roundtrip(self):
        old = (u'foo', b'bar', 42, {})
        new = Binary.zpickle(old).unzpickle()
        self.assertEqual(old, new)
        self.assertIsNot(old, new)

    def test_from_file_to_file(self):
        with tempdir() as dpath:
            fpath = osp.join(dpath, 'binary.bin')
            with open(fpath, 'wb') as fobj:
                Binary(b'binaryblob').to_file(fobj)

            bobj = Binary.from_file(fpath)
            self.assertEqual(bobj.getvalue(), b'binaryblob')

    def test_pickleable(self):
        b = Binary(b'toto')
        bb = pickle.loads(pickle.dumps(b))
        self.assertEqual(b, bb)


if __name__ == '__main__':
    from unittest import main
    main()
