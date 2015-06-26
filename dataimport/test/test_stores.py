# copyright 2003-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cubicweb.dataimport import stores
from cubicweb.devtools.testlib import CubicWebTC


class RQLObjectStoreTC(CubicWebTC):

    def test_all(self):
        with self.admin_access.repo_cnx() as cnx:
            store = stores.RQLObjectStore(cnx)
            # Check data insertion
            group_eid = store.prepare_insert_entity('CWGroup', name=u'grp')
            user_eid = store.prepare_insert_entity('CWUser', login=u'lgn',
                                                   upassword=u'pwd')
            store.prepare_insert_relation(user_eid, 'in_group', group_eid)
            cnx.commit()
            users = cnx.execute('CWUser X WHERE X login "lgn"')
            self.assertEqual(1, len(users))
            self.assertEqual(user_eid, users.one().eid)
            groups = cnx.execute('CWGroup X WHERE U in_group X, U login "lgn"')
            self.assertEqual(1, len(users))
            self.assertEqual(group_eid, groups.one().eid)
            # Check data update
            self.set_description('Check data update')
            store.prepare_update_entity('CWGroup', group_eid, name=u'new_grp')
            cnx.commit()
            group = cnx.execute('CWGroup X WHERE X name "grp"')
            self.assertEqual(len(group), 0)
            group = cnx.execute('CWGroup X WHERE X name "new_grp"')
            self.assertEqual, len(group), 1
            # Check data update with wrong type
            with self.assertRaises(AssertionError):
                store.prepare_update_entity('CWUser', group_eid, name=u'new_user')
            cnx.commit()
            group = cnx.execute('CWGroup X WHERE X name "new_user"')
            self.assertEqual(len(group), 0)
            group = cnx.execute('CWGroup X WHERE X name "new_grp"')
            self.assertEqual(len(group), 1)


class MetaGeneratorTC(CubicWebTC):

    def test_dont_generate_relation_to_internal_manager(self):
        with self.admin_access.repo_cnx() as cnx:
            metagen = stores.MetaGenerator(cnx)
            self.assertIn('created_by', metagen.etype_rels)
            self.assertIn('owned_by', metagen.etype_rels)
        with self.repo.internal_cnx() as cnx:
            metagen = stores.MetaGenerator(cnx)
            self.assertNotIn('created_by', metagen.etype_rels)
            self.assertNotIn('owned_by', metagen.etype_rels)

    def test_dont_generate_specified_values(self):
        with self.admin_access.repo_cnx() as cnx:
            metagen = stores.MetaGenerator(cnx)
            # hijack gen_modification_date to ensure we don't go through it
            metagen.gen_modification_date = None
            md = DT.datetime.now() - DT.timedelta(days=1)
            entity, rels = metagen.base_etype_dicts('CWUser')
            entity.cw_edited.update(dict(modification_date=md))
            with cnx.ensure_cnx_set:
                metagen.init_entity(entity)
            self.assertEqual(entity.cw_edited['modification_date'], md)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
