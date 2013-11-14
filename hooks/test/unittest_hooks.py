# -*- coding: utf-8 -*-
# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cubicweb import ValidationError, AuthenticationError, BadConnectionId
from cubicweb.devtools.testlib import CubicWebTC

class CoreHooksTC(CubicWebTC):

    def test_inlined(self):
        self.assertEqual(self.repo.schema['sender'].inlined, True)
        self.execute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')
        self.execute('INSERT EmailPart X: X content_format "text/plain", X ordernum 1, X content "this is a test"')
        eeid = self.execute('INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, X recipients Y, X parts P '
                            'WHERE Y is EmailAddress, P is EmailPart')[0][0]
        self.execute('SET X sender Y WHERE X is Email, Y is EmailAddress')
        rset = self.execute('Any S WHERE X sender S, X eid %s' % eeid)
        self.assertEqual(len(rset), 1)

    def test_symmetric(self):
        req = self.request()
        u1 = self.create_user(req, u'1')
        u2 = self.create_user(req, u'2')
        u3 = self.create_user(req, u'3')
        ga = req.create_entity('CWGroup', name=u'A')
        gb = req.create_entity('CWGroup', name=u'B')
        u1.cw_set(friend=u2)
        u2.cw_set(friend=u3)
        ga.cw_set(friend=gb)
        ga.cw_set(friend=u1)
        self.commit()
        req = self.request()
        for l1, l2 in ((u'1', u'2'),
                       (u'2', u'3')):
            self.assertTrue(req.execute('Any U1,U2 WHERE U1 friend U2, U1 login %(l1)s, U2 login %(l2)s',
                                        {'l1': l1, 'l2': l2}))
            self.assertTrue(req.execute('Any U1,U2 WHERE U2 friend U1, U1 login %(l1)s, U2 login %(l2)s',
                                        {'l1': l1, 'l2': l2}))
        self.assertTrue(req.execute('Any GA,GB WHERE GA friend GB, GA name "A", GB name "B"'))
        self.assertTrue(req.execute('Any GA,GB WHERE GB friend GA, GA name "A", GB name "B"'))
        self.assertTrue(req.execute('Any GA,U1 WHERE GA friend U1, GA name "A", U1 login "1"'))
        self.assertTrue(req.execute('Any GA,U1 WHERE U1 friend GA, GA name "A", U1 login "1"'))
        self.assertFalse(req.execute('Any GA,U WHERE GA friend U, GA name "A", U login "2"'))
        for l1, l2 in ((u'1', u'3'),
                       (u'3', u'1')):
            self.assertFalse(req.execute('Any U1,U2 WHERE U1 friend U2, U1 login %(l1)s, U2 login %(l2)s',
                                         {'l1': l1, 'l2': l2}))
            self.assertFalse(req.execute('Any U1,U2 WHERE U2 friend U1, U1 login %(l1)s, U2 login %(l2)s',
                                         {'l1': l1, 'l2': l2}))

    def test_html_tidy_hook(self):
        req = self.request()
        entity = req.create_entity('Workflow', name=u'wf1',
                                   description_format=u'text/html',
                                   description=u'yo')
        self.assertEqual(entity.description, u'yo')
        entity = req.create_entity('Workflow', name=u'wf2',
                                   description_format=u'text/html',
                                   description=u'<b>yo')
        self.assertEqual(entity.description, u'<b>yo</b>')
        entity = req.create_entity('Workflow', name=u'wf3',
                                   description_format=u'text/html',
                                   description=u'<b>yo</b>')
        self.assertEqual(entity.description, u'<b>yo</b>')
        entity = req.create_entity('Workflow', name=u'wf4',
                                   description_format=u'text/html',
                                   description=u'<b>R&D</b>')
        self.assertEqual(entity.description, u'<b>R&amp;D</b>')
        entity = req.create_entity('Workflow', name=u'wf5',
                                   description_format=u'text/html',
                                   description=u"<div>c&apos;est <b>l'ét&eacute;")
        self.assertEqual(entity.description, u"<div>c'est <b>l'été</b></div>")

    def test_nonregr_html_tidy_hook_no_update(self):
        entity = self.request().create_entity('Workflow', name=u'wf1',
                                              description_format=u'text/html',
                                              description=u'yo')
        entity.cw_set(name=u'wf2')
        self.assertEqual(entity.description, u'yo')
        entity.cw_set(description=u'R&D<p>yo')
        self.assertEqual(entity.description, u'R&amp;D<p>yo</p>')

    def test_metadata_cwuri(self):
        entity = self.request().create_entity('Workflow', name=u'wf1')
        self.assertEqual(entity.cwuri, self.repo.config['base-url'] + str(entity.eid))

    def test_metadata_creation_modification_date(self):
        _now = datetime.now()
        entity = self.request().create_entity('Workflow', name=u'wf1')
        self.assertEqual((entity.creation_date - _now).seconds, 0)
        self.assertEqual((entity.modification_date - _now).seconds, 0)

    def test_metadata_created_by(self):
        entity = self.request().create_entity('Bookmark', title=u'wf1', path=u'/view')
        self.commit() # fire operations
        self.assertEqual(len(entity.created_by), 1) # make sure we have only one creator
        self.assertEqual(entity.created_by[0].eid, self.session.user.eid)

    def test_metadata_owned_by(self):
        entity = self.request().create_entity('Bookmark', title=u'wf1', path=u'/view')
        self.commit() # fire operations
        self.assertEqual(len(entity.owned_by), 1) # make sure we have only one owner
        self.assertEqual(entity.owned_by[0].eid, self.session.user.eid)

    def test_user_login_stripped(self):
        req = self.request()
        u = self.create_user(req, '  joe  ')
        tname = self.execute('Any L WHERE E login L, E eid %(e)s',
                             {'e': u.eid})[0][0]
        self.assertEqual(tname, 'joe')
        self.execute('SET X login " jijoe " WHERE X eid %(x)s', {'x': u.eid})
        tname = self.execute('Any L WHERE E login L, E eid %(e)s',
                             {'e': u.eid})[0][0]
        self.assertEqual(tname, 'jijoe')



class UserGroupHooksTC(CubicWebTC):

    def test_user_synchronization(self):
        req = self.request()
        self.create_user(req, 'toto', password='hop', commit=False)
        self.assertRaises(AuthenticationError,
                          self.repo.connect, u'toto', password='hop')
        self.commit()
        cnxid = self.repo.connect(u'toto', password='hop')
        self.assertNotEqual(cnxid, self.session.id)
        self.execute('DELETE CWUser X WHERE X login "toto"')
        self.repo.execute(cnxid, 'State X')
        self.commit()
        self.assertRaises(BadConnectionId,
                          self.repo.execute, cnxid, 'State X')

    def test_user_group_synchronization(self):
        user = self.session.user
        self.assertEqual(user.groups, set(('managers',)))
        self.execute('SET X in_group G WHERE X eid %s, G name "guests"' % user.eid)
        self.assertEqual(user.groups, set(('managers',)))
        self.commit()
        self.assertEqual(user.groups, set(('managers', 'guests')))
        self.execute('DELETE X in_group G WHERE X eid %s, G name "guests"' % user.eid)
        self.assertEqual(user.groups, set(('managers', 'guests')))
        self.commit()
        self.assertEqual(user.groups, set(('managers',)))

    def test_user_composite_owner(self):
        req = self.request()
        ueid = self.create_user(req, 'toto').eid
        # composite of euser should be owned by the euser regardless of who created it
        self.execute('INSERT EmailAddress X: X address "toto@logilab.fr", U use_email X '
                     'WHERE U login "toto"')
        self.commit()
        self.assertEqual(self.execute('Any A WHERE X owned_by U, U use_email X,'
                                       'U login "toto", X address A')[0][0],
                          'toto@logilab.fr')

    def test_no_created_by_on_deleted_entity(self):
        eid = self.execute('INSERT EmailAddress X: X address "toto@logilab.fr"')[0][0]
        self.execute('DELETE EmailAddress X WHERE X eid %s' % eid)
        self.commit()
        self.assertFalse(self.execute('Any X WHERE X created_by Y, X eid >= %(x)s', {'x': eid}))



class SchemaHooksTC(CubicWebTC):

    def test_duplicate_etype_error(self):
        # check we can't add a CWEType or CWRType entity if it already exists one
        # with the same name
        self.assertRaises(ValidationError,
                          self.execute, 'INSERT CWEType X: X name "CWUser"')
        self.assertRaises(ValidationError,
                          self.execute, 'INSERT CWRType X: X name "in_group"')

    def test_validation_unique_constraint(self):
        with self.assertRaises(ValidationError) as cm:
            self.execute('INSERT CWUser X: X login "admin"')
        ex = cm.exception
        ex.translate(unicode)
        self.assertIsInstance(ex.entity, int)
        self.assertEqual(ex.errors, {'login-subject': 'the value "admin" is already used, use another one'})


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
