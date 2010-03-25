"""unit tests for module cubicweb.server.sources.storages

:organization: Logilab
:copyright: 2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from logilab.common.testlib import unittest_main
from cubicweb.devtools.testlib import CubicWebTC

import os.path as osp
import shutil
import tempfile

from cubicweb import Binary, QueryError
from cubicweb.selectors import implements
from cubicweb.server.sources import storages
from cubicweb.server.hook import Hook, Operation

class DummyBeforeHook(Hook):
    __regid__ = 'dummy-before-hook'
    __select__ = Hook.__select__ & implements('File')
    events = ('before_add_entity',)

    def __call__(self):
        self._cw.transaction_data['orig_file_value'] = self.entity.data.getvalue()


class DummyAfterHook(Hook):
    __regid__ = 'dummy-after-hook'
    __select__ = Hook.__select__ & implements('File')
    events = ('after_add_entity',)

    def __call__(self):
        # new value of entity.data should be the same as before
        oldvalue = self._cw.transaction_data['orig_file_value']
        assert oldvalue == self.entity.data.getvalue()


class StorageTC(CubicWebTC):

    def setup_database(self):
        self.tempdir = tempfile.mkdtemp()
        bfs_storage = storages.BytesFileSystemStorage(self.tempdir)
        storages.set_attribute_storage(self.repo, 'File', 'data', bfs_storage)

    def tearDown(self):
        super(CubicWebTC, self).tearDown()
        storages.unset_attribute_storage(self.repo, 'File', 'data')
        shutil.rmtree(self.tempdir)


    def create_file(self, content='the-data'):
        req = self.request()
        return req.create_entity('File', data=Binary(content),
                                 data_format=u'text/plain', data_name=u'foo')

    def test_bfss_storage(self):
        f1 = self.create_file()
        expected_filepath = osp.join(self.tempdir, '%s_data' % f1.eid)
        self.failUnless(osp.isfile(expected_filepath))
        self.assertEquals(file(expected_filepath).read(), 'the-data')
        self.rollback()
        self.failIf(osp.isfile(expected_filepath))
        f1 = self.create_file()
        self.commit()
        self.assertEquals(file(expected_filepath).read(), 'the-data')
        f1.set_attributes(data=Binary('the new data'))
        self.rollback()
        self.assertEquals(file(expected_filepath).read(), 'the-data')
        f1.delete()
        self.failUnless(osp.isfile(expected_filepath))
        self.rollback()
        self.failUnless(osp.isfile(expected_filepath))
        f1.delete()
        self.commit()
        self.failIf(osp.isfile(expected_filepath))

    def test_bfss_sqlite_fspath(self):
        f1 = self.create_file()
        expected_filepath = osp.join(self.tempdir, '%s_data' % f1.eid)
        fspath = self.execute('Any fspath(D) WHERE F eid %(f)s, F data D',
                              {'f': f1.eid})[0][0]
        self.assertEquals(fspath.getvalue(), expected_filepath)

    def test_bfss_fs_importing_doesnt_touch_path(self):
        self.session.transaction_data['fs_importing'] = True
        f1 = self.session.create_entity('File', data=Binary('/the/path'),
                                        data_format=u'text/plain', data_name=u'foo')
        fspath = self.execute('Any fspath(D) WHERE F eid %(f)s, F data D',
                              {'f': f1.eid})[0][0]
        self.assertEquals(fspath.getvalue(), '/the/path')

    def test_source_storage_transparency(self):
        self.vreg._loadedmods[__name__] = {}
        self.vreg.register(DummyBeforeHook)
        self.vreg.register(DummyAfterHook)
        try:
            self.create_file()
        finally:
            self.vreg.unregister(DummyBeforeHook)
            self.vreg.unregister(DummyAfterHook)

    def test_source_mapped_attribute_error_cases(self):
        ex = self.assertRaises(QueryError, self.execute,
                               'Any X WHERE X data ~= "hop", X is File')
        self.assertEquals(str(ex), 'can\'t use File.data (X data ILIKE "hop") in restriction')
        ex = self.assertRaises(QueryError, self.execute,
                               'Any X, Y WHERE X data D, Y data D, '
                               'NOT X identity Y, X is File, Y is File')
        self.assertEquals(str(ex), "can't use D as a restriction variable")
        # query returning mix of mapped / regular attributes (only file.data
        # mapped, not image.data for instance)
        ex = self.assertRaises(QueryError, self.execute,
                               'Any X WITH X BEING ('
                               ' (Any NULL)'
                               '  UNION '
                               ' (Any D WHERE X data D, X is File)'
                               ')')
        self.assertEquals(str(ex), 'query fetch some source mapped attribute, some not')
        ex = self.assertRaises(QueryError, self.execute,
                               '(Any D WHERE X data D, X is File)'
                               ' UNION '
                               '(Any D WHERE X data D, X is Image)')
        self.assertEquals(str(ex), 'query fetch some source mapped attribute, some not')
        ex = self.assertRaises(QueryError,
                               self.execute, 'Any D WHERE X data D')
        self.assertEquals(str(ex), 'query fetch some source mapped attribute, some not')

    def test_source_mapped_attribute_advanced(self):
        f1 = self.create_file()
        rset = self.execute('Any X,D WITH D,X BEING ('
                            ' (Any D, X WHERE X eid %(x)s, X data D)'
                            '  UNION '
                            ' (Any D, X WHERE X eid %(x)s, X data D)'
                            ')', {'x': f1.eid}, 'x')
        self.assertEquals(len(rset), 2)
        self.assertEquals(rset[0][0], f1.eid)
        self.assertEquals(rset[1][0], f1.eid)
        self.assertEquals(rset[0][1].getvalue(), 'the-data')
        self.assertEquals(rset[1][1].getvalue(), 'the-data')
        rset = self.execute('Any X,LENGTH(D) WHERE X eid %(x)s, X data D',
                            {'x': f1.eid}, 'x')
        self.assertEquals(len(rset), 1)
        self.assertEquals(rset[0][0], f1.eid)
        self.assertEquals(rset[0][1], len('the-data'))
        rset = self.execute('Any X,LENGTH(D) WITH D,X BEING ('
                            ' (Any D, X WHERE X eid %(x)s, X data D)'
                            '  UNION '
                            ' (Any D, X WHERE X eid %(x)s, X data D)'
                            ')', {'x': f1.eid}, 'x')
        self.assertEquals(len(rset), 2)
        self.assertEquals(rset[0][0], f1.eid)
        self.assertEquals(rset[1][0], f1.eid)
        self.assertEquals(rset[0][1], len('the-data'))
        self.assertEquals(rset[1][1], len('the-data'))
        ex = self.assertRaises(QueryError, self.execute,
                               'Any X,UPPER(D) WHERE X eid %(x)s, X data D',
                               {'x': f1.eid}, 'x')
        self.assertEquals(str(ex), 'UPPER can not be called on mapped attribute')

if __name__ == '__main__':
    unittest_main()
