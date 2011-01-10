# -*- coding: utf-8 -*-
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
"""functional tests for core hooks

note: most schemahooks.py hooks are actually tested in unittest_migrations.py
"""
from __future__ import with_statement

from logilab.common.testlib import TestCase, unittest_main

from datetime import datetime

from cubicweb import ValidationError, AuthenticationError, BadConnectionId
from cubicweb.devtools.testlib import CubicWebTC

class CoreHooksTC(CubicWebTC):

    def test_delete_internal_entities(self):
        self.assertRaises(ValidationError, self.execute,
                          'DELETE CWEType X WHERE X name "CWEType"')
        self.assertRaises(ValidationError, self.execute,
                          'DELETE CWRType X WHERE X name "relation_type"')
        self.assertRaises(ValidationError, self.execute,
                          'DELETE CWGroup X WHERE X name "owners"')

    def test_delete_required_relations_subject(self):
        self.execute('INSERT CWUser X: X login "toto", X upassword "hop", X in_group Y '
                     'WHERE Y name "users"')
        self.commit()
        self.execute('DELETE X in_group Y WHERE X login "toto", Y name "users"')
        self.assertRaises(ValidationError, self.commit)
        self.execute('DELETE X in_group Y WHERE X login "toto"')
        self.execute('SET X in_group Y WHERE X login "toto", Y name "guests"')
        self.commit()

    def test_delete_required_relations_object(self):
        self.skipTest('no sample in the schema ! YAGNI ? Kermaat ?')

    def test_static_vocabulary_check(self):
        self.assertRaises(ValidationError,
                          self.execute,
                          'SET X composite "whatever" WHERE X from_entity FE, FE name "CWUser", X relation_type RT, RT name "in_group"')

    def test_missing_required_relations_subject_inline(self):
        # missing in_group relation
        self.execute('INSERT CWUser X: X login "toto", X upassword "hop"')
        self.assertRaises(ValidationError,
                          self.commit)

    def test_inlined(self):
        self.assertEqual(self.repo.schema['sender'].inlined, True)
        self.execute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')
        self.execute('INSERT EmailPart X: X content_format "text/plain", X ordernum 1, X content "this is a test"')
        eeid = self.execute('INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, X recipients Y, X parts P '
                            'WHERE Y is EmailAddress, P is EmailPart')[0][0]
        self.execute('SET X sender Y WHERE X is Email, Y is EmailAddress')
        rset = self.execute('Any S WHERE X sender S, X eid %s' % eeid)
        self.assertEqual(len(rset), 1)

    def test_composite_1(self):
        self.execute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')
        self.execute('INSERT EmailPart X: X content_format "text/plain", X ordernum 1, X content "this is a test"')
        self.execute('INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, X recipients Y, X parts P '
                     'WHERE Y is EmailAddress, P is EmailPart')
        self.failUnless(self.execute('Email X WHERE X sender Y'))
        self.commit()
        self.execute('DELETE Email X')
        rset = self.execute('Any X WHERE X is EmailPart')
        self.assertEqual(len(rset), 1)
        self.commit()
        rset = self.execute('Any X WHERE X is EmailPart')
        self.assertEqual(len(rset), 0)

    def test_composite_2(self):
        self.execute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')
        self.execute('INSERT EmailPart X: X content_format "text/plain", X ordernum 1, X content "this is a test"')
        self.execute('INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, X recipients Y, X parts P '
                     'WHERE Y is EmailAddress, P is EmailPart')
        self.commit()
        self.execute('DELETE Email X')
        self.execute('DELETE EmailPart X')
        self.commit()
        rset = self.execute('Any X WHERE X is EmailPart')
        self.assertEqual(len(rset), 0)

    def test_composite_redirection(self):
        self.execute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')
        self.execute('INSERT EmailPart X: X content_format "text/plain", X ordernum 1, X content "this is a test"')
        self.execute('INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, X recipients Y, X parts P '
                     'WHERE Y is EmailAddress, P is EmailPart')
        self.execute('INSERT Email X: X messageid "<2345>", X subject "test2", X sender Y, X recipients Y '
                     'WHERE Y is EmailAddress')
        self.commit()
        self.execute('DELETE X parts Y WHERE X messageid "<1234>"')
        self.execute('SET X parts Y WHERE X messageid "<2345>"')
        self.commit()
        rset = self.execute('Any X WHERE X is EmailPart')
        self.assertEqual(len(rset), 1)
        self.assertEqual(rset.get_entity(0, 0).reverse_parts[0].messageid, '<2345>')

    def test_unsatisfied_constraints(self):
        releid = self.execute('SET U in_group G WHERE G name "owners", U login "admin"')[0][0]
        with self.assertRaises(ValidationError) as cm:
            self.commit()
        self.assertEqual(cm.exception.errors,
                          {'in_group-object': u'RQLConstraint NOT O name "owners" failed'})

    def test_html_tidy_hook(self):
        req = self.request()
        entity = req.create_entity('Workflow', name=u'wf1', description_format=u'text/html',
                                 description=u'yo')
        self.assertEqual(entity.description, u'yo')
        entity = req.create_entity('Workflow', name=u'wf2', description_format=u'text/html',
                                 description=u'<b>yo')
        self.assertEqual(entity.description, u'<b>yo</b>')
        entity = req.create_entity('Workflow', name=u'wf3', description_format=u'text/html',
                                 description=u'<b>yo</b>')
        self.assertEqual(entity.description, u'<b>yo</b>')
        entity = req.create_entity('Workflow', name=u'wf4', description_format=u'text/html',
                                 description=u'<b>R&D</b>')
        self.assertEqual(entity.description, u'<b>R&amp;D</b>')
        entity = req.create_entity('Workflow', name=u'wf5', description_format=u'text/html',
                                 description=u"<div>c&apos;est <b>l'ét&eacute;")
        self.assertEqual(entity.description, u"<div>c'est <b>l'été</b></div>")

    def test_nonregr_html_tidy_hook_no_update(self):
        entity = self.request().create_entity('Workflow', name=u'wf1', description_format=u'text/html',
                                 description=u'yo')
        entity.set_attributes(name=u'wf2')
        self.assertEqual(entity.description, u'yo')
        entity.set_attributes(description=u'R&D<p>yo')
        entity.cw_attr_cache.pop('description')
        self.assertEqual(entity.description, u'R&amp;D<p>yo</p>')

    def test_metadata_cwuri(self):
        entity = self.request().create_entity('Workflow', name=u'wf1')
        self.assertEqual(entity.cwuri, self.repo.config['base-url'] + 'eid/%s' % entity.eid)

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
        u = self.create_user('  joe  ')
        tname = self.execute('Any L WHERE E login L, E eid %(e)s',
                             {'e': u.eid})[0][0]
        self.assertEqual(tname, 'joe')
        self.execute('SET X login " jijoe " WHERE X eid %(x)s', {'x': u.eid})
        tname = self.execute('Any L WHERE E login L, E eid %(e)s',
                             {'e': u.eid})[0][0]
        self.assertEqual(tname, 'jijoe')



class UserGroupHooksTC(CubicWebTC):

    def test_user_synchronization(self):
        self.create_user('toto', password='hop', commit=False)
        self.assertRaises(AuthenticationError,
                          self.repo.connect, u'toto', password='hop')
        self.commit()
        cnxid = self.repo.connect(u'toto', password='hop')
        self.failIfEqual(cnxid, self.session.id)
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
        ueid = self.create_user('toto').eid
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
        self.failIf(self.execute('Any X WHERE X created_by Y, X eid >= %(x)s', {'x': eid}))


class CWPropertyHooksTC(CubicWebTC):

    def test_unexistant_eproperty(self):
        with self.assertRaises(ValidationError) as cm:
            self.execute('INSERT CWProperty X: X pkey "bla.bla", X value "hop", X for_user U')
        self.assertEqual(cm.exception.errors, {'pkey-subject': 'unknown property key bla.bla'})
        with self.assertRaises(ValidationError) as cm:
            self.execute('INSERT CWProperty X: X pkey "bla.bla", X value "hop"')
        self.assertEqual(cm.exception.errors, {'pkey-subject': 'unknown property key bla.bla'})

    def test_site_wide_eproperty(self):
        with self.assertRaises(ValidationError) as cm:
            self.execute('INSERT CWProperty X: X pkey "ui.site-title", X value "hop", X for_user U')
        self.assertEqual(cm.exception.errors, {'for_user-subject': "site-wide property can't be set for user"})

    def test_bad_type_eproperty(self):
        with self.assertRaises(ValidationError) as cm:
            self.execute('INSERT CWProperty X: X pkey "ui.language", X value "hop", X for_user U')
        self.assertEqual(cm.exception.errors, {'value-subject': u'unauthorized value'})
        with self.assertRaises(ValidationError) as cm:
            self.execute('INSERT CWProperty X: X pkey "ui.language", X value "hop"')
        self.assertEqual(cm.exception.errors, {'value-subject': u'unauthorized value'})


class SchemaHooksTC(CubicWebTC):

    def test_duplicate_etype_error(self):
        # check we can't add a CWEType or CWRType entity if it already exists one
        # with the same name
        self.assertRaises(ValidationError,
                          self.execute, 'INSERT CWEType X: X name "CWUser"')
        self.assertRaises(ValidationError,
                          self.execute, 'INSERT CWRType X: X name "in_group"')

    def test_validation_unique_constraint(self):
        self.assertRaises(ValidationError,
                          self.execute, 'INSERT CWUser X: X login "admin"')
        try:
            self.execute('INSERT CWUser X: X login "admin"')
        except ValidationError, ex:
            self.assertIsInstance(ex.entity, int)
            self.assertEqual(ex.errors, {'login-subject': 'the value "admin" is already used, use another one'})


if __name__ == '__main__':
    unittest_main()
