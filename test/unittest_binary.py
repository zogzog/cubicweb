from six import PY2

from unittest import TestCase
from tempfile import NamedTemporaryFile
import os.path as osp

from logilab.common.shellutils import tempdir
from cubicweb import Binary


class BinaryTC(TestCase):
    def test_init(self):
        Binary()
        Binary(b'toto')
        Binary(bytearray(b'toto'))
        if PY2:
            Binary(buffer('toto'))
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
            b.write(buffer('toto'))
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


if __name__ == '__main__':
    from unittest import main
    main()
