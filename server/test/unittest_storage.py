# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unit tests for module cubicweb.server.sources.storages"""

from logilab.common.testlib import unittest_main, tag, Tags
from cubicweb.devtools.testlib import CubicWebTC

import os
import os.path as osp
import shutil
import tempfile

from cubicweb import Binary, QueryError
from cubicweb.predicates import is_instance
from cubicweb.server.sources import storages
from cubicweb.server.hook import Hook, Operation

class DummyBeforeHook(Hook):
    __regid__ = 'dummy-before-hook'
    __select__ = Hook.__select__ & is_instance('File')
    events = ('before_add_entity',)

    def __call__(self):
        self._cw.transaction_data['orig_file_value'] = self.entity.data.getvalue()


class DummyAfterHook(Hook):
    __regid__ = 'dummy-after-hook'
    __select__ = Hook.__select__ & is_instance('File')
    events = ('after_add_entity',)

    def __call__(self):
        # new value of entity.data should be the same as before
        oldvalue = self._cw.transaction_data['orig_file_value']
        assert oldvalue == self.entity.data.getvalue()

class StorageTC(CubicWebTC):

    tags = CubicWebTC.tags | Tags('Storage', 'BFSS')

    def setup_database(self):
        self.tempdir = tempfile.mkdtemp()
        bfs_storage = storages.BytesFileSystemStorage(self.tempdir)
        storages.set_attribute_storage(self.repo, 'File', 'data', bfs_storage)
        storages.set_attribute_storage(self.repo, 'BFSSTestable', 'opt_attr', bfs_storage)

    def tearDown(self):
        super(StorageTC, self).tearDown()
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

    def test_bfss_wrong_fspath_usage(self):
        f1 = self.create_file()
        self.execute('Any fspath(D) WHERE F eid %(f)s, F data D', {'f': f1.eid})
        with self.assertRaises(NotImplementedError) as cm:
            self.execute('Any fspath(F) WHERE F eid %(f)s', {'f': f1.eid})
        self.assertEqual(str(cm.exception),
                         'This callback is only available for BytesFileSystemStorage '
                         'managed attribute. Is FSPATH() argument BFSS managed?')

    def test_bfss_storage(self):
        f1 = self.create_file()
        expected_filepath = osp.join(self.tempdir, '%s_data_%s' %
                                     (f1.eid, f1.data_name))
        self.assertTrue(osp.isfile(expected_filepath))
        # file should be read only
        self.assertFalse(os.access(expected_filepath, os.W_OK))
        self.assertEqual(file(expected_filepath).read(), 'the-data')
        self.rollback()
        self.assertFalse(osp.isfile(expected_filepath))
        f1 = self.create_file()
        self.commit()
        self.assertEqual(file(expected_filepath).read(), 'the-data')
        f1.cw_set(data=Binary('the new data'))
        self.rollback()
        self.assertEqual(file(expected_filepath).read(), 'the-data')
        f1.cw_delete()
        self.assertTrue(osp.isfile(expected_filepath))
        self.rollback()
        self.assertTrue(osp.isfile(expected_filepath))
        f1.cw_delete()
        self.commit()
        self.assertFalse(osp.isfile(expected_filepath))

    def test_bfss_sqlite_fspath(self):
        f1 = self.create_file()
        expected_filepath = osp.join(self.tempdir, '%s_data_%s' % (f1.eid, f1.data_name))
        self.assertEqual(self.fspath(f1), expected_filepath)

    def test_bfss_fs_importing_doesnt_touch_path(self):
        self.session.transaction_data['fs_importing'] = True
        filepath = osp.abspath(__file__)
        f1 = self.request().create_entity('File', data=Binary(filepath),
                                        data_format=u'text/plain', data_name=u'foo')
        self.assertEqual(self.fspath(f1), filepath)

    def test_source_storage_transparency(self):
        with self.temporary_appobjects(DummyBeforeHook, DummyAfterHook):
            self.create_file()

    def test_source_mapped_attribute_error_cases(self):
        with self.assertRaises(QueryError) as cm:
            self.execute('Any X WHERE X data ~= "hop", X is File')
        self.assertEqual(str(cm.exception), 'can\'t use File.data (X data ILIKE "hop") in restriction')
        with self.assertRaises(QueryError) as cm:
            self.execute('Any X, Y WHERE X data D, Y data D, '
                         'NOT X identity Y, X is File, Y is File')
        self.assertEqual(str(cm.exception), "can't use D as a restriction variable")
        # query returning mix of mapped / regular attributes (only file.data
        # mapped, not image.data for instance)
        with self.assertRaises(QueryError) as cm:
            self.execute('Any X WITH X BEING ('
                         ' (Any NULL)'
                         '  UNION '
                         ' (Any D WHERE X data D, X is File)'
                         ')')
        self.assertEqual(str(cm.exception), 'query fetch some source mapped attribute, some not')
        with self.assertRaises(QueryError) as cm:
            self.execute('(Any D WHERE X data D, X is File)'
                         ' UNION '
                         '(Any D WHERE X title D, X is Bookmark)')
        self.assertEqual(str(cm.exception), 'query fetch some source mapped attribute, some not')

        storages.set_attribute_storage(self.repo, 'State', 'name',
                                       storages.BytesFileSystemStorage(self.tempdir))
        try:
            with self.assertRaises(QueryError) as cm:
                self.execute('Any D WHERE X name D, X is IN (State, Transition)')
            self.assertEqual(str(cm.exception), 'query fetch some source mapped attribute, some not')
        finally:
            storages.unset_attribute_storage(self.repo, 'State', 'name')

    def test_source_mapped_attribute_advanced(self):
        f1 = self.create_file()
        rset = self.execute('Any X,D WITH D,X BEING ('
                            ' (Any D, X WHERE X eid %(x)s, X data D)'
                            '  UNION '
                            ' (Any D, X WHERE X eid %(x)s, X data D)'
                            ')', {'x': f1.eid})
        self.assertEqual(len(rset), 2)
        self.assertEqual(rset[0][0], f1.eid)
        self.assertEqual(rset[1][0], f1.eid)
        self.assertEqual(rset[0][1].getvalue(), 'the-data')
        self.assertEqual(rset[1][1].getvalue(), 'the-data')
        rset = self.execute('Any X,LENGTH(D) WHERE X eid %(x)s, X data D',
                            {'x': f1.eid})
        self.assertEqual(len(rset), 1)
        self.assertEqual(rset[0][0], f1.eid)
        self.assertEqual(rset[0][1], len('the-data'))
        rset = self.execute('Any X,LENGTH(D) WITH D,X BEING ('
                            ' (Any D, X WHERE X eid %(x)s, X data D)'
                            '  UNION '
                            ' (Any D, X WHERE X eid %(x)s, X data D)'
                            ')', {'x': f1.eid})
        self.assertEqual(len(rset), 2)
        self.assertEqual(rset[0][0], f1.eid)
        self.assertEqual(rset[1][0], f1.eid)
        self.assertEqual(rset[0][1], len('the-data'))
        self.assertEqual(rset[1][1], len('the-data'))
        with self.assertRaises(QueryError) as cm:
            self.execute('Any X,UPPER(D) WHERE X eid %(x)s, X data D',
                         {'x': f1.eid})
        self.assertEqual(str(cm.exception), 'UPPER can not be called on mapped attribute')


    def test_bfss_fs_importing_transparency(self):
        self.session.transaction_data['fs_importing'] = True
        filepath = osp.abspath(__file__)
        f1 = self.session.create_entity('File', data=Binary(filepath),
                                        data_format=u'text/plain', data_name=u'foo')
        cw_value = f1.data.getvalue()
        fs_value = file(filepath).read()
        if cw_value != fs_value:
            self.fail('cw value %r is different from file content' % cw_value)


    @tag('update')
    def test_bfss_update_with_existing_data(self):
        # use self.session to use server-side cache
        f1 = self.session.create_entity('File', data=Binary('some data'),
                                        data_format=u'text/plain', data_name=u'foo')
        # NOTE: do not use cw_set() which would automatically
        #       update f1's local dict. We want the pure rql version to work
        self.execute('SET F data %(d)s WHERE F eid %(f)s',
                     {'d': Binary('some other data'), 'f': f1.eid})
        self.assertEqual(f1.data.getvalue(), 'some other data')
        self.commit()
        f2 = self.execute('Any F WHERE F eid %(f)s, F is File', {'f': f1.eid}).get_entity(0, 0)
        self.assertEqual(f2.data.getvalue(), 'some other data')

    @tag('update', 'extension', 'commit')
    def test_bfss_update_with_different_extension_commited(self):
        # use self.session to use server-side cache
        f1 = self.session.create_entity('File', data=Binary('some data'),
                                        data_format=u'text/plain', data_name=u'foo.txt')
        # NOTE: do not use cw_set() which would automatically
        #       update f1's local dict. We want the pure rql version to work
        self.commit()
        old_path = self.fspath(f1)
        self.assertTrue(osp.isfile(old_path))
        self.assertEqual(osp.splitext(old_path)[1], '.txt')
        self.execute('SET F data %(d)s, F data_name %(dn)s, F data_format %(df)s WHERE F eid %(f)s',
                     {'d': Binary('some other data'), 'f': f1.eid, 'dn': u'bar.jpg', 'df': u'image/jpeg'})
        self.commit()
        # the new file exists with correct extension
        # the old file is dead
        f2 = self.execute('Any F WHERE F eid %(f)s, F is File', {'f': f1.eid}).get_entity(0, 0)
        new_path = self.fspath(f2)
        self.assertFalse(osp.isfile(old_path))
        self.assertTrue(osp.isfile(new_path))
        self.assertEqual(osp.splitext(new_path)[1], '.jpg')

    @tag('update', 'extension', 'rollback')
    def test_bfss_update_with_different_extension_rolled_back(self):
        # use self.session to use server-side cache
        f1 = self.session.create_entity('File', data=Binary('some data'),
                                        data_format=u'text/plain', data_name=u'foo.txt')
        # NOTE: do not use cw_set() which would automatically
        #       update f1's local dict. We want the pure rql version to work
        self.commit()
        old_path = self.fspath(f1)
        old_data = f1.data.getvalue()
        self.assertTrue(osp.isfile(old_path))
        self.assertEqual(osp.splitext(old_path)[1], '.txt')
        self.execute('SET F data %(d)s, F data_name %(dn)s, F data_format %(df)s WHERE F eid %(f)s',
                     {'d': Binary('some other data'), 'f': f1.eid, 'dn': u'bar.jpg', 'df': u'image/jpeg'})
        self.rollback()
        # the new file exists with correct extension
        # the old file is dead
        f2 = self.execute('Any F WHERE F eid %(f)s, F is File', {'f': f1.eid}).get_entity(0, 0)
        new_path = self.fspath(f2)
        new_data = f2.data.getvalue()
        self.assertTrue(osp.isfile(new_path))
        self.assertEqual(osp.splitext(new_path)[1], '.txt')
        self.assertEqual(old_path, new_path)
        self.assertEqual(old_data, new_data)

    @tag('update', 'NULL')
    def test_bfss_update_to_None(self):
        f = self.session.create_entity('Affaire', opt_attr=Binary('toto'))
        self.session.commit()
        self.session.set_cnxset()
        f.cw_set(opt_attr=None)
        self.session.commit()

    @tag('fs_importing', 'update')
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
        self.assertEqual(f1.data.getvalue(), 'the new data')
        self.assertEqual(self.fspath(f1), new_fspath)
        self.assertFalse(osp.isfile(old_fspath))

    @tag('fsimport')
    def test_clean(self):
        fsimport = storages.fsimport
        td = self.session.transaction_data
        self.assertNotIn('fs_importing', td)
        with fsimport(self.session):
            self.assertIn('fs_importing', td)
            self.assertTrue(td['fs_importing'])
        self.assertNotIn('fs_importing', td)

    @tag('fsimport')
    def test_true(self):
        fsimport = storages.fsimport
        td = self.session.transaction_data
        td['fs_importing'] = True
        with fsimport(self.session):
            self.assertIn('fs_importing', td)
            self.assertTrue(td['fs_importing'])
        self.assertTrue(td['fs_importing'])

    @tag('fsimport')
    def test_False(self):
        fsimport = storages.fsimport
        td = self.session.transaction_data
        td['fs_importing'] = False
        with fsimport(self.session):
            self.assertIn('fs_importing', td)
            self.assertTrue(td['fs_importing'])
        self.assertFalse(td['fs_importing'])

if __name__ == '__main__':
    unittest_main()
