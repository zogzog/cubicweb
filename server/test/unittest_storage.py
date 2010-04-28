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
"""unit tests for module cubicweb.server.sources.storages

"""

from __future__ import with_statement

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
                                 data_format=u'text/plain', data_name=u'foo.pdf')

    def fspath(self, entity):
        fspath = self.execute('Any fspath(D) WHERE F eid %(f)s, F data D',
                              {'f': entity.eid})[0][0]
        return fspath.getvalue()

    def test_bfss_storage(self):
        f1 = self.create_file()
        expected_filepath = osp.join(self.tempdir, '%s_data_%s' %
                                     (f1.eid, f1.data_name))
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
        expected_filepath = osp.join(self.tempdir, '%s_data_%s' % (f1.eid, f1.data_name))
        self.assertEquals(self.fspath(f1), expected_filepath)

    def test_bfss_fs_importing_doesnt_touch_path(self):
        self.session.transaction_data['fs_importing'] = True
        filepath = osp.abspath(__file__)
        f1 = self.session.create_entity('File', data=Binary(filepath),
                                        data_format=u'text/plain', data_name=u'foo')
        self.assertEquals(self.fspath(f1), filepath)

    def test_source_storage_transparency(self):
        with self.temporary_appobjects(DummyBeforeHook, DummyAfterHook):
            self.create_file()

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
                            ')', {'x': f1.eid})
        self.assertEquals(len(rset), 2)
        self.assertEquals(rset[0][0], f1.eid)
        self.assertEquals(rset[1][0], f1.eid)
        self.assertEquals(rset[0][1].getvalue(), 'the-data')
        self.assertEquals(rset[1][1].getvalue(), 'the-data')
        rset = self.execute('Any X,LENGTH(D) WHERE X eid %(x)s, X data D',
                            {'x': f1.eid})
        self.assertEquals(len(rset), 1)
        self.assertEquals(rset[0][0], f1.eid)
        self.assertEquals(rset[0][1], len('the-data'))
        rset = self.execute('Any X,LENGTH(D) WITH D,X BEING ('
                            ' (Any D, X WHERE X eid %(x)s, X data D)'
                            '  UNION '
                            ' (Any D, X WHERE X eid %(x)s, X data D)'
                            ')', {'x': f1.eid})
        self.assertEquals(len(rset), 2)
        self.assertEquals(rset[0][0], f1.eid)
        self.assertEquals(rset[1][0], f1.eid)
        self.assertEquals(rset[0][1], len('the-data'))
        self.assertEquals(rset[1][1], len('the-data'))
        ex = self.assertRaises(QueryError, self.execute,
                               'Any X,UPPER(D) WHERE X eid %(x)s, X data D',
                               {'x': f1.eid})
        self.assertEquals(str(ex), 'UPPER can not be called on mapped attribute')


    def test_bfss_fs_importing_transparency(self):
        self.session.transaction_data['fs_importing'] = True
        filepath = osp.abspath(__file__)
        f1 = self.session.create_entity('File', data=Binary(filepath),
                                        data_format=u'text/plain', data_name=u'foo')
        self.assertEquals(f1.data.getvalue(), file(filepath).read(),
                          'files content differ')


    def test_bfss_update_with_existing_data(self):
        # use self.session to use server-side cache
        f1 = self.session.create_entity('File', data=Binary('some data'),
                                        data_format=u'text/plain', data_name=u'foo')
        # NOTE: do not use set_attributes() which would automatically
        #       update f1's local dict. We want the pure rql version to work
        self.execute('SET F data %(d)s WHERE F eid %(f)s',
                     {'d': Binary('some other data'), 'f': f1.eid})
        self.assertEquals(f1.data.getvalue(), 'some other data')
        self.commit()
        f2 = self.execute('Any F WHERE F eid %(f)s, F is File', {'f': f1.eid}).get_entity(0, 0)
        self.assertEquals(f2.data.getvalue(), 'some other data')


    def test_bfss_update_with_fs_importing(self):
        # use self.session to use server-side cache
        f1 = self.session.create_entity('File', data=Binary('some data'),
                                        data_format=u'text/plain', data_name=u'foo')
        old_fspath = self.fspath(f1)
        self.session.transaction_data['fs_importing'] = True
        new_fspath = osp.join(self.tempdir, 'newfile.txt')
        file(new_fspath, 'w').write('the new data')
        self.execute('SET F data %(d)s WHERE F eid %(f)s',
                     {'d': Binary(new_fspath), 'f': f1.eid})
        self.commit()
        self.assertEquals(f1.data.getvalue(), 'the new data')
        self.assertEquals(self.fspath(f1), new_fspath)
        self.failIf(osp.isfile(old_fspath))


if __name__ == '__main__':
    unittest_main()
