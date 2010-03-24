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

from cubicweb import Binary
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


    def create_file(self, content):
        req = self.request()
        return req.create_entity('File', data=Binary(content),
                                 data_format=u'text/plain', data_name=u'foo')

    def test_bfs_storage(self):
        f1 = self.create_file(content='the-data')
        expected_filepath = osp.join(self.tempdir, '%s_data' % f1.eid)
        self.failUnless(osp.isfile(expected_filepath))
        self.assertEquals(file(expected_filepath).read(), 'the-data')

    def test_sqlite_fspath(self):
        f1 = self.create_file(content='the-data')
        expected_filepath = osp.join(self.tempdir, '%s_data' % f1.eid)
        fspath = self.execute('Any fspath(F, "File", "data") WHERE F eid %(f)s',
                              {'f': f1.eid})[0][0]
        self.assertEquals(fspath.getvalue(), expected_filepath)

    def test_fs_importing_doesnt_touch_path(self):
        self.session.transaction_data['fs_importing'] = True
        f1 = self.session.create_entity('File', data=Binary('/the/path'),
                                        data_format=u'text/plain', data_name=u'foo')
        fspath = self.execute('Any fspath(F, "File", "data") WHERE F eid %(f)s',
                              {'f': f1.eid})[0][0]
        self.assertEquals(fspath.getvalue(), '/the/path')

    def test_storage_transparency(self):
        self.vreg._loadedmods[__name__] = {}
        self.vreg.register(DummyBeforeHook)
        self.vreg.register(DummyAfterHook)
        try:
            self.create_file(content='the-data')
        finally:
            self.vreg.unregister(DummyBeforeHook)
            self.vreg.unregister(DummyAfterHook)

if __name__ == '__main__':
    unittest_main()
