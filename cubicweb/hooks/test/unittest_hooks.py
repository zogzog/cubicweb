# -*- coding: utf-8 -*-
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
"""functional tests for core hooks

Note:
  syncschema.py hooks are mostly tested in server/test/unittest_migrations.py
"""

from datetime import datetime

from six import text_type

from pytz import utc

from cubicweb import ValidationError
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.server.hook import Operation


class CoreHooksTC(CubicWebTC):

    def test_inlined(self):
        with self.admin_access.repo_cnx() as cnx:
            self.assertEqual(self.repo.schema['sender'].inlined, True)
            cnx.execute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')
            cnx.execute('INSERT EmailPart X: X content_format "text/plain", X ordernum 1, '
                        'X content "this is a test"')
            eeid = cnx.execute('INSERT Email X: X messageid "<1234>", X subject "test", '
                               'X sender Y, X recipients Y, X parts P '
                               'WHERE Y is EmailAddress, P is EmailPart')[0][0]
            cnx.execute('SET X sender Y WHERE X is Email, Y is EmailAddress')
            rset = cnx.execute('Any S WHERE X sender S, X eid %s' % eeid)
            self.assertEqual(len(rset), 1)

    def test_symmetric(self):
        with self.admin_access.repo_cnx() as cnx:
            u1 = self.create_user(cnx, u'1')
            u2 = self.create_user(cnx, u'2')
            u3 = self.create_user(cnx, u'3')
            ga = cnx.create_entity('CWGroup', name=u'A')
            gb = cnx.create_entity('CWGroup', name=u'B')
            u1.cw_set(friend=u2)
            u2.cw_set(friend=u3)
            ga.cw_set(friend=gb)
            ga.cw_set(friend=u1)
            cnx.commit()
            for l1, l2 in ((u'1', u'2'),
                           (u'2', u'3')):
                self.assertTrue(cnx.execute('Any U1,U2 WHERE U1 friend U2, U1 login %(l1)s, U2 login %(l2)s',
                                            {'l1': l1, 'l2': l2}))
                self.assertTrue(cnx.execute('Any U1,U2 WHERE U2 friend U1, U1 login %(l1)s, U2 login %(l2)s',
                                            {'l1': l1, 'l2': l2}))
            self.assertTrue(cnx.execute('Any GA,GB WHERE GA friend GB, GA name "A", GB name "B"'))
            self.assertTrue(cnx.execute('Any GA,GB WHERE GB friend GA, GA name "A", GB name "B"'))
            self.assertTrue(cnx.execute('Any GA,U1 WHERE GA friend U1, GA name "A", U1 login "1"'))
            self.assertTrue(cnx.execute('Any GA,U1 WHERE U1 friend GA, GA name "A", U1 login "1"'))
            self.assertFalse(cnx.execute('Any GA,U WHERE GA friend U, GA name "A", U login "2"'))
            for l1, l2 in ((u'1', u'3'),
                           (u'3', u'1')):
                self.assertFalse(cnx.execute('Any U1,U2 WHERE U1 friend U2, U1 login %(l1)s, U2 login %(l2)s',
                                             {'l1': l1, 'l2': l2}))
                self.assertFalse(cnx.execute('Any U1,U2 WHERE U2 friend U1, U1 login %(l1)s, U2 login %(l2)s',
                                             {'l1': l1, 'l2': l2}))

    def test_html_tidy_hook(self):
        with self.admin_access.client_cnx() as cnx:
            entity = cnx.create_entity('Workflow', name=u'wf1',
                                       description_format=u'text/html',
                                       description=u'yo')
            self.assertEqual(u'yo', entity.description)
            entity = cnx.create_entity('Workflow', name=u'wf2',
                                       description_format=u'text/html',
                                       description=u'<b>yo')
            self.assertEqual(u'<b>yo</b>', entity.description)
            entity = cnx.create_entity('Workflow', name=u'wf3',
                                       description_format=u'text/html',
                                       description=u'<b>yo</b>')
            self.assertEqual(u'<b>yo</b>', entity.description)
            entity = cnx.create_entity('Workflow', name=u'wf4',
                                       description_format=u'text/html',
                                       description=u'<b>R&D</b>')
            self.assertEqual(u'<b>R&amp;D</b>', entity.description, )
            entity = cnx.create_entity('Workflow', name=u'wf5',
                                       description_format=u'text/html',
                                       description=u"<div>c&apos;est <b>l'ét&eacute;")
            self.assertEqual(u"<div>c'est <b>l'été</b></div>", entity.description)

    def test_nonregr_html_tidy_hook_no_update(self):
        with self.admin_access.client_cnx() as cnx:
            entity = cnx.create_entity('Workflow', name=u'wf1',
                                       description_format=u'text/html',
                                       description=u'yo')
            entity.cw_set(name=u'wf2')
            self.assertEqual(entity.description, u'yo')
            entity.cw_set(description=u'R&D<p>yo')
            self.assertEqual(entity.description, u'R&amp;D<p>yo</p>')

    def test_metadata_cwuri(self):
        with self.admin_access.repo_cnx() as cnx:
            entity = cnx.create_entity('Workflow', name=u'wf1')
            self.assertEqual(entity.cwuri, self.repo.config['base-url'] + str(entity.eid))

    def test_metadata_creation_modification_date(self):
        with self.admin_access.repo_cnx() as cnx:
            _now = datetime.now(utc)
            entity = cnx.create_entity('Workflow', name=u'wf1')
            self.assertEqual((entity.creation_date - _now).seconds, 0)
            self.assertEqual((entity.modification_date - _now).seconds, 0)

    def test_metadata_created_by(self):
        with self.admin_access.repo_cnx() as cnx:
            entity = cnx.create_entity('Bookmark', title=u'wf1', path=u'/view')
            cnx.commit()  # fire operations
            self.assertEqual(len(entity.created_by), 1)  # make sure we have only one creator
            self.assertEqual(entity.created_by[0].eid, cnx.user.eid)

    def test_metadata_owned_by(self):
        with self.admin_access.repo_cnx() as cnx:
            entity = cnx.create_entity('Bookmark', title=u'wf1', path=u'/view')
            cnx.commit()  # fire operations
            self.assertEqual(len(entity.owned_by), 1)  # make sure we have only one owner
            self.assertEqual(entity.owned_by[0].eid, cnx.user.eid)

    def test_user_login_stripped(self):
        with self.admin_access.repo_cnx() as cnx:
            u = self.create_user(cnx, '  joe  ')
            tname = cnx.execute('Any L WHERE E login L, E eid %(e)s',
                                {'e': u.eid})[0][0]
            self.assertEqual(tname, 'joe')
            cnx.execute('SET X login " jijoe " WHERE X eid %(x)s', {'x': u.eid})
            tname = cnx.execute('Any L WHERE E login L, E eid %(e)s',
                                {'e': u.eid})[0][0]
            self.assertEqual(tname, 'jijoe')


class UserGroupHooksTC(CubicWebTC):

    def test_user_group_synchronization(self):
        with self.admin_access.repo_cnx() as cnx:
            user = cnx.user
            self.assertEqual(user.groups, set(('managers',)))
            cnx.execute('SET X in_group G WHERE X eid %s, G name "guests"' % user.eid)
            self.assertEqual(user.groups, set(('managers',)))
            cnx.commit()
            self.assertEqual(user.groups, set(('managers', 'guests')))
            cnx.execute('DELETE X in_group G WHERE X eid %s, G name "guests"' % user.eid)
            self.assertEqual(user.groups, set(('managers', 'guests')))
            cnx.commit()
            self.assertEqual(user.groups, set(('managers',)))

    def test_user_composite_owner(self):
        with self.admin_access.repo_cnx() as cnx:
            self.create_user(cnx, 'toto').eid
            # composite of euser should be owned by the euser regardless of who created it
            cnx.execute('INSERT EmailAddress X: X address "toto@logilab.fr", U use_email X '
                        'WHERE U login "toto"')
            cnx.commit()
            self.assertEqual(cnx.execute('Any A WHERE X owned_by U, U use_email X,'
                                         'U login "toto", X address A')[0][0],
                             'toto@logilab.fr')

    def test_user_composite_no_owner_on_deleted_entity(self):
        with self.admin_access.repo_cnx() as cnx:
            u = self.create_user(cnx, 'toto').eid
            cnx.commit()
            e = cnx.create_entity('EmailAddress', address=u'toto@logilab.fr', reverse_use_email=u)
            e.cw_delete()
            cnx.commit()
            self.assertFalse(cnx.system_sql(
                'SELECT * FROM owned_by_relation '
                'WHERE eid_from NOT IN (SELECT eid FROM entities)').fetchall())

    def test_no_created_by_on_deleted_entity(self):
        with self.admin_access.repo_cnx() as cnx:
            eid = cnx.execute('INSERT EmailAddress X: X address "toto@logilab.fr"')[0][0]
            cnx.execute('DELETE EmailAddress X WHERE X eid %s' % eid)
            cnx.commit()
            self.assertFalse(cnx.execute('Any X WHERE X created_by Y, X eid >= %(x)s', {'x': eid}))


class SchemaHooksTC(CubicWebTC):

    def test_duplicate_etype_error(self):
        with self.admin_access.repo_cnx() as cnx:
            # check we can't add a CWEType or CWRType entity if it already exists one
            # with the same name
            self.assertRaises(ValidationError,
                              cnx.execute, 'INSERT CWEType X: X name "CWUser"')
            cnx.rollback()
            self.assertRaises(ValidationError,
                              cnx.execute, 'INSERT CWRType X: X name "in_group"')

    def test_validation_unique_constraint(self):
        with self.admin_access.repo_cnx() as cnx:
            with self.assertRaises(ValidationError) as cm:
                cnx.execute('INSERT CWUser X: X login "admin", X upassword "admin"')
            ex = cm.exception
            ex.translate(text_type)
            self.assertIsInstance(ex.entity, int)
            self.assertEqual(ex.errors,
                             {'': u'some relations violate a unicity constraint',
                              'login': u'login is part of violated unicity constraint'})


class OperationTC(CubicWebTC):

    def test_bad_postcommit_event(self):

        class BadOp(Operation):
            def postcommit_event(self):
                raise RuntimeError('this is bad')

        with self.admin_access.cnx() as cnx:
            BadOp(cnx)
            with self.assertRaises(RuntimeError) as cm:
                cnx.commit()
            self.assertEqual(str(cm.exception), 'this is bad')


if __name__ == '__main__':
    import unittest
    unittest.main()
