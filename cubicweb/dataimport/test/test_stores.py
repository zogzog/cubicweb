# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unittest for cubicweb.dataimport.stores"""

import datetime as DT

import pytz

from cubicweb.dataimport import stores
from cubicweb.devtools.testlib import CubicWebTC


class RQLObjectStoreTC(CubicWebTC):
    store_impl = stores.RQLObjectStore
    insert_group_attrs = dict(name=u'grp')
    insert_user_attrs = dict(login=u'lgn', upassword=u'pwd')
    source_name = 'system'
    user_extid = None

    def test_base(self):
        with self.admin_access.repo_cnx() as cnx:
            store = self.store_impl(cnx)
            # Check data insertion
            group_eid = store.prepare_insert_entity('CWGroup', **self.insert_group_attrs)
            user_eid = store.prepare_insert_entity('CWUser', **self.insert_user_attrs)
            store.prepare_insert_relation(user_eid, 'in_group', group_eid)
            store.flush()
            store.commit()
            store.finish()
            user = cnx.execute('CWUser X WHERE X login "lgn"').one()
            self.assertEqual(user_eid, user.eid)
            self.assertTrue(user.creation_date)
            self.assertTrue(user.modification_date)
            self.assertTrue(user.cwuri)
            self.assertEqual(user.created_by[0].eid, cnx.user.eid)
            self.assertEqual(user.owned_by[0].eid, cnx.user.eid)
            self.assertEqual(user.cw_source[0].name, self.source_name)
            groups = cnx.execute('CWGroup X WHERE U in_group X, U login "lgn"')
            self.assertEqual(group_eid, groups.one().eid)
            # Check data update
            store.prepare_update_entity('CWGroup', group_eid, name=u'new_grp')
            store.commit()
            self.assertFalse(cnx.execute('CWGroup X WHERE X name "grp"'))
            self.assertTrue(cnx.execute('CWGroup X WHERE X name "new_grp"'))
            # Check data update with wrong type
            with self.assertRaises(AssertionError):
                store.prepare_update_entity('CWUser', group_eid, name=u'new_user')
            store.commit()
            self.assertFalse(cnx.execute('CWGroup X WHERE X name "new_user"'))
            self.assertTrue(cnx.execute('CWGroup X WHERE X name "new_grp"'))


class NoHookRQLObjectStoreTC(RQLObjectStoreTC):
    store_impl = stores.NoHookRQLObjectStore


class NoHookRQLObjectStoreWithCustomMDGenStoreTC(RQLObjectStoreTC):
    insert_group_attrs = RQLObjectStoreTC.insert_group_attrs.copy()
    insert_group_attrs['cwuri'] = u'http://somewhere.com/group/1'
    insert_user_attrs = RQLObjectStoreTC.insert_user_attrs.copy()
    insert_user_attrs['cwuri'] = u'http://somewhere.com/user/1'
    source_name = 'test'
    user_extid = b'http://somewhere.com/user/1'

    def store_impl(self, cnx):
        source = cnx.create_entity('CWSource', type=u'datafeed', name=u'test', url=u'test')
        cnx.commit()
        metagen = stores.MetadataGenerator(cnx, source=cnx.repo.source_by_eid(source.eid))
        return stores.NoHookRQLObjectStore(cnx, metagen)


class MetaGeneratorTC(CubicWebTC):
    metagenerator_impl = stores.MetaGenerator
    _etype_rels = staticmethod(lambda x: x.etype_rels)

    def test_dont_generate_relation_to_internal_manager(self):
        with self.admin_access.repo_cnx() as cnx:
            metagen = self.metagenerator_impl(cnx)
            self.assertIn('created_by', self._etype_rels(metagen))
            self.assertIn('owned_by', self._etype_rels(metagen))
        with self.repo.internal_cnx() as cnx:
            metagen = self.metagenerator_impl(cnx)
            self.assertNotIn('created_by', self._etype_rels(metagen))
            self.assertNotIn('owned_by', self._etype_rels(metagen))

    def test_dont_generate_specified_values(self):
        with self.admin_access.repo_cnx() as cnx:
            metagen = self.metagenerator_impl(cnx)
            # hijack gen_modification_date to ensure we don't go through it
            metagen.gen_modification_date = None
            md = DT.datetime.now(pytz.utc) - DT.timedelta(days=1)
            entity, rels = metagen.base_etype_dicts('CWUser')
            entity.cw_edited.update(dict(modification_date=md))
            metagen.init_entity(entity)
            self.assertEqual(entity.cw_edited['modification_date'], md)


class MetadataGeneratorWrapperTC(MetaGeneratorTC):
    @staticmethod
    def metagenerator_impl(cnx):
        return stores._MetaGeneratorBWCompatWrapper(stores.MetadataGenerator(cnx))

    _etype_rels = staticmethod(lambda x: x._mdgen._etype_rels)


class MetadataGeneratorTC(CubicWebTC):

    def test_dont_generate_relation_to_internal_manager(self):
        with self.admin_access.repo_cnx() as cnx:
            metagen = stores.MetadataGenerator(cnx)
            self.assertIn('created_by', metagen.etype_rels('CWUser'))
            self.assertIn('owned_by', metagen.etype_rels('CWUser'))
        with self.repo.internal_cnx() as cnx:
            metagen = stores.MetadataGenerator(cnx)
            self.assertNotIn('created_by', metagen.etype_rels('CWUser'))
            self.assertNotIn('owned_by', metagen.etype_rels('CWUser'))

    def test_dont_generate_specified_values(self):
        with self.admin_access.repo_cnx() as cnx:
            metagen = stores.MetadataGenerator(cnx)
            # hijack gen_modification_date to ensure we don't go through it
            metagen.gen_modification_date = None
            md = DT.datetime.now(pytz.utc) - DT.timedelta(days=1)
            attrs = metagen.base_etype_attrs('CWUser')
            attrs.update(dict(modification_date=md))
            metagen.init_entity_attrs('CWUser', 1, attrs)
            self.assertEqual(attrs['modification_date'], md)


if __name__ == '__main__':
    import unittest
    unittest.main()
