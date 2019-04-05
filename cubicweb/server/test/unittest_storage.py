# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from glob import glob
import os
import os.path as osp
import sys
import shutil
import tempfile

from cubicweb import Binary, QueryError
from cubicweb.predicates import is_instance
from cubicweb.server.sources import storages
from cubicweb.server.hook import Hook

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
    tempdir = None
    tags = CubicWebTC.tags | Tags('Storage', 'BFSS')

    def setup_database(self):
        self.tempdir = tempfile.mkdtemp()
        bfs_storage = storages.BytesFileSystemStorage(self.tempdir)
        self.bfs_storage = bfs_storage
        storages.set_attribute_storage(self.repo, 'File', 'data', bfs_storage)
        storages.set_attribute_storage(self.repo, 'BFSSTestable', 'opt_attr', bfs_storage)

    def tearDown(self):
        super(StorageTC, self).tearDown()
        storages.unset_attribute_storage(self.repo, 'File', 'data')
        del self.bfs_storage
        shutil.rmtree(self.tempdir)


    def create_file(self, cnx, content=b'the-data'):
        return cnx.create_entity('File', data=Binary(content),
                                 data_format=u'text/plain',
                                 data_name=u'foo.pdf')

    def fspath(self, cnx, entity):
        fspath = cnx.execute('Any fspath(D) WHERE F eid %(f)s, F data D',
                             {'f': entity.eid})[0][0].getvalue()
        return fspath.decode('utf-8')

    def test_bfss_wrong_fspath_usage(self):
        with self.admin_access.repo_cnx() as cnx:
            f1 = self.create_file(cnx)
            cnx.execute('Any fspath(D) WHERE F eid %(f)s, F data D', {'f': f1.eid})
            with self.assertRaises(NotImplementedError) as cm:
                cnx.execute('Any fspath(F) WHERE F eid %(f)s', {'f': f1.eid})
            self.assertEqual(str(cm.exception),
                             'This callback is only available for BytesFileSystemStorage '
                             'managed attribute. Is FSPATH() argument BFSS managed?')

    def test_bfss_storage(self):
        with self.admin_access.web_request() as req:
            cnx = req.cnx
            f1 = self.create_file(req)
            filepaths = glob(osp.join(self.tempdir, '%s_data_*' % f1.eid))
            self.assertEqual(len(filepaths), 1, filepaths)
            expected_filepath = filepaths[0]
            # file should be read only
            self.assertFalse(os.access(expected_filepath, os.W_OK))
            self.assertEqual(open(expected_filepath).read(), 'the-data')
            cnx.rollback()
            self.assertFalse(osp.isfile(expected_filepath))
            filepaths = glob(osp.join(self.tempdir, '%s_data_*' % f1.eid))
            self.assertEqual(len(filepaths), 0, filepaths)
            f1 = self.create_file(req)
            cnx.commit()
            filepaths = glob(osp.join(self.tempdir, '%s_data_*' % f1.eid))
            self.assertEqual(len(filepaths), 1, filepaths)
            expected_filepath = filepaths[0]
            self.assertEqual(open(expected_filepath).read(), 'the-data')

            # add f1 back to the entity cache with req as _cw
            f1 = req.entity_from_eid(f1.eid)
            f1.cw_set(data=Binary(b'the new data'))
            cnx.rollback()
            self.assertEqual(open(expected_filepath).read(), 'the-data')
            f1.cw_delete()
            self.assertTrue(osp.isfile(expected_filepath))
            cnx.rollback()
            self.assertTrue(osp.isfile(expected_filepath))
            f1.cw_delete()
            cnx.commit()
            self.assertFalse(osp.isfile(expected_filepath))

    def test_bfss_sqlite_fspath(self):
        with self.admin_access.repo_cnx() as cnx:
            f1 = self.create_file(cnx)
            expected_filepath = osp.join(self.tempdir, '%s_data_%s' % (f1.eid, f1.data_name))
            base, ext = osp.splitext(expected_filepath)
            self.assertTrue(self.fspath(cnx, f1).startswith(base))
            self.assertTrue(self.fspath(cnx, f1).endswith(ext))

    def test_bfss_fs_importing_doesnt_touch_path(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.transaction_data['fs_importing'] = True
            filepath = osp.abspath(__file__)
            f1 = cnx.create_entity('File', data=Binary(filepath.encode(sys.getfilesystemencoding())),
                                   data_format=u'text/plain', data_name=u'foo')
            self.assertEqual(self.fspath(cnx, f1), filepath)

    def test_source_storage_transparency(self):
        with self.admin_access.repo_cnx() as cnx:
            with self.temporary_appobjects(DummyBeforeHook, DummyAfterHook):
                self.create_file(cnx)

    def test_source_mapped_attribute_error_cases(self):
        with self.admin_access.repo_cnx() as cnx:
            with self.assertRaises(QueryError) as cm:
                cnx.execute('Any X WHERE X data ~= "hop", X is File')
            self.assertEqual(str(cm.exception), 'can\'t use File.data (X data ILIKE "hop") in restriction')
            with self.assertRaises(QueryError) as cm:
                cnx.execute('Any X, Y WHERE X data D, Y data D, '
                             'NOT X identity Y, X is File, Y is File')
            self.assertEqual(str(cm.exception), "can't use D as a restriction variable")
            # query returning mix of mapped / regular attributes (only file.data
            # mapped, not image.data for instance)
            with self.assertRaises(QueryError) as cm:
                cnx.execute('Any X WITH X BEING ('
                             ' (Any NULL)'
                             '  UNION '
                             ' (Any D WHERE X data D, X is File)'
                             ')')
            self.assertEqual(str(cm.exception), 'query fetch some source mapped attribute, some not')
            with self.assertRaises(QueryError) as cm:
                cnx.execute('(Any D WHERE X data D, X is File)'
                             ' UNION '
                             '(Any D WHERE X title D, X is Bookmark)')
            self.assertEqual(str(cm.exception), 'query fetch some source mapped attribute, some not')

            storages.set_attribute_storage(self.repo, 'State', 'name',
                                           storages.BytesFileSystemStorage(self.tempdir))
            try:
                with self.assertRaises(QueryError) as cm:
                    cnx.execute('Any D WHERE X name D, X is IN (State, Transition)')
                self.assertEqual(str(cm.exception), 'query fetch some source mapped attribute, some not')
            finally:
                storages.unset_attribute_storage(self.repo, 'State', 'name')

    def test_source_mapped_attribute_advanced(self):
        with self.admin_access.repo_cnx() as cnx:
            f1 = self.create_file(cnx)
            rset = cnx.execute('Any X,D WITH D,X BEING ('
                                ' (Any D, X WHERE X eid %(x)s, X data D)'
                                '  UNION '
                                ' (Any D, X WHERE X eid %(x)s, X data D)'
                                ')', {'x': f1.eid})
            self.assertEqual(len(rset), 2)
            self.assertEqual(rset[0][0], f1.eid)
            self.assertEqual(rset[1][0], f1.eid)
            self.assertEqual(rset[0][1].getvalue(), b'the-data')
            self.assertEqual(rset[1][1].getvalue(), b'the-data')
            rset = cnx.execute('Any X,LENGTH(D) WHERE X eid %(x)s, X data D',
                                {'x': f1.eid})
            self.assertEqual(len(rset), 1)
            self.assertEqual(rset[0][0], f1.eid)
            self.assertEqual(rset[0][1], len('the-data'))
            rset = cnx.execute('Any X,LENGTH(D) WITH D,X BEING ('
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
                cnx.execute('Any X,UPPER(D) WHERE X eid %(x)s, X data D',
                             {'x': f1.eid})
            self.assertEqual(str(cm.exception), 'UPPER can not be called on mapped attribute')


    def test_bfss_fs_importing_transparency(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.transaction_data['fs_importing'] = True
            filepath = osp.abspath(__file__)
            f1 = cnx.create_entity('File', data=Binary(filepath.encode(sys.getfilesystemencoding())),
                                   data_format=u'text/plain', data_name=u'foo')
            cw_value = f1.data.getvalue()
            fs_value = open(filepath, 'rb').read()
            if cw_value != fs_value:
                self.fail('cw value %r is different from file content' % cw_value)

    @tag('update')
    def test_bfss_update_with_existing_data(self):
        with self.admin_access.repo_cnx() as cnx:
            f1 = cnx.create_entity('File', data=Binary(b'some data'),
                                   data_format=u'text/plain', data_name=u'foo')
            # NOTE: do not use cw_set() which would automatically
            #       update f1's local dict. We want the pure rql version to work
            cnx.execute('SET F data %(d)s WHERE F eid %(f)s',
                         {'d': Binary(b'some other data'), 'f': f1.eid})
            self.assertEqual(f1.data.getvalue(), b'some other data')
            cnx.commit()
            f2 = cnx.execute('Any F WHERE F eid %(f)s, F is File', {'f': f1.eid}).get_entity(0, 0)
            self.assertEqual(f2.data.getvalue(), b'some other data')

    @tag('update', 'extension', 'commit')
    def test_bfss_update_with_different_extension_commited(self):
        with self.admin_access.repo_cnx() as cnx:
            f1 = cnx.create_entity('File', data=Binary(b'some data'),
                                   data_format=u'text/plain', data_name=u'foo.txt')
            # NOTE: do not use cw_set() which would automatically
            #       update f1's local dict. We want the pure rql version to work
            cnx.commit()
            old_path = self.fspath(cnx, f1)
            self.assertTrue(osp.isfile(old_path))
            self.assertEqual(osp.splitext(old_path)[1], '.txt')
            cnx.execute('SET F data %(d)s, F data_name %(dn)s, '
                         'F data_format %(df)s WHERE F eid %(f)s',
                         {'d': Binary(b'some other data'), 'f': f1.eid,
                          'dn': u'bar.jpg', 'df': u'image/jpeg'})
            cnx.commit()
            # the new file exists with correct extension
            # the old file is dead
            f2 = cnx.execute('Any F WHERE F eid %(f)s, F is File', {'f': f1.eid}).get_entity(0, 0)
            new_path = self.fspath(cnx, f2)
            self.assertFalse(osp.isfile(old_path))
            self.assertTrue(osp.isfile(new_path))
            self.assertEqual(osp.splitext(new_path)[1], '.jpg')

    @tag('update', 'extension', 'rollback')
    def test_bfss_update_with_different_extension_rolled_back(self):
        with self.admin_access.repo_cnx() as cnx:
            f1 = cnx.create_entity('File', data=Binary(b'some data'),
                                   data_format=u'text/plain', data_name=u'foo.txt')
            # NOTE: do not use cw_set() which would automatically
            #       update f1's local dict. We want the pure rql version to work
            cnx.commit()
            old_path = self.fspath(cnx, f1)
            old_data = f1.data.getvalue()
            self.assertTrue(osp.isfile(old_path))
            self.assertEqual(osp.splitext(old_path)[1], '.txt')
            cnx.execute('SET F data %(d)s, F data_name %(dn)s, '
                         'F data_format %(df)s WHERE F eid %(f)s',
                         {'d': Binary(b'some other data'),
                          'f': f1.eid,
                          'dn': u'bar.jpg',
                          'df': u'image/jpeg'})
            cnx.rollback()
            # the new file exists with correct extension
            # the old file is dead
            f2 = cnx.execute('Any F WHERE F eid %(f)s, F is File',
                              {'f': f1.eid}).get_entity(0, 0)
            new_path = self.fspath(cnx, f2)
            new_data = f2.data.getvalue()
            self.assertTrue(osp.isfile(new_path))
            self.assertEqual(osp.splitext(new_path)[1], '.txt')
            self.assertEqual(old_path, new_path)
            self.assertEqual(old_data, new_data)

    @tag('update', 'NULL')
    def test_bfss_update_to_None(self):
        with self.admin_access.repo_cnx() as cnx:
            f = cnx.create_entity('Affaire', opt_attr=Binary(b'toto'))
            cnx.commit()
            f.cw_set(opt_attr=None)
            cnx.commit()

    @tag('fs_importing', 'update')
    def test_bfss_update_with_fs_importing(self):
        with self.admin_access.repo_cnx() as cnx:
            f1 = cnx.create_entity('File', data=Binary(b'some data'),
                                   data_format=u'text/plain',
                                   data_name=u'foo')
            old_fspath = self.fspath(cnx, f1)
            cnx.transaction_data['fs_importing'] = True
            new_fspath = osp.join(self.tempdir, 'newfile.txt')
            open(new_fspath, 'w').write('the new data')
            cnx.execute('SET F data %(d)s WHERE F eid %(f)s',
                         {'d': Binary(new_fspath.encode(sys.getfilesystemencoding())), 'f': f1.eid})
            cnx.commit()
            self.assertEqual(f1.data.getvalue(), b'the new data')
            self.assertEqual(self.fspath(cnx, f1), new_fspath)
            self.assertFalse(osp.isfile(old_fspath))

    @tag('fsimport')
    def test_clean(self):
        with self.admin_access.repo_cnx() as cnx:
            fsimport = storages.fsimport
            td = cnx.transaction_data
            self.assertNotIn('fs_importing', td)
            with fsimport(cnx):
                self.assertIn('fs_importing', td)
                self.assertTrue(td['fs_importing'])
            self.assertNotIn('fs_importing', td)

    @tag('fsimport')
    def test_true(self):
        with self.admin_access.repo_cnx() as cnx:
            fsimport = storages.fsimport
            td = cnx.transaction_data
            td['fs_importing'] = True
            with fsimport(cnx):
                self.assertIn('fs_importing', td)
                self.assertTrue(td['fs_importing'])
            self.assertTrue(td['fs_importing'])

    @tag('fsimport')
    def test_False(self):
        with self.admin_access.repo_cnx() as cnx:
            fsimport = storages.fsimport
            td = cnx.transaction_data
            td['fs_importing'] = False
            with fsimport(cnx):
                self.assertIn('fs_importing', td)
                self.assertTrue(td['fs_importing'])
            self.assertFalse(td['fs_importing'])

if __name__ == '__main__':
    unittest_main()
