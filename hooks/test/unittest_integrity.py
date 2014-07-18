# -*- coding: utf-8 -*-
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
"""functional tests for integrity hooks"""

from cubicweb import ValidationError
from cubicweb.devtools.testlib import CubicWebTC

class CoreHooksTC(CubicWebTC):

    def test_delete_internal_entities(self):
        with self.admin_access.repo_cnx() as cnx:
            self.assertRaises(ValidationError, cnx.execute,
                              'DELETE CWEType X WHERE X name "CWEType"')
            cnx.rollback()
            self.assertRaises(ValidationError, cnx.execute,
                              'DELETE CWRType X WHERE X name "relation_type"')
            cnx.rollback()
            self.assertRaises(ValidationError, cnx.execute,
                              'DELETE CWGroup X WHERE X name "owners"')

    def test_delete_required_relations_subject(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute('INSERT CWUser X: X login "toto", X upassword "hop", X in_group Y '
                         'WHERE Y name "users"')
            cnx.commit()
            cnx.execute('DELETE X in_group Y WHERE X login "toto", Y name "users"')
            self.assertRaises(ValidationError, cnx.commit)
            cnx.rollback()
            cnx.execute('DELETE X in_group Y WHERE X login "toto"')
            cnx.execute('SET X in_group Y WHERE X login "toto", Y name "guests"')
            cnx.commit()

    def test_static_vocabulary_check(self):
        with self.admin_access.repo_cnx() as cnx:
            self.assertRaises(ValidationError,
                              cnx.execute,
                              'SET X composite "whatever" WHERE X from_entity FE, FE name "CWUser", '
                              'X relation_type RT, RT name "in_group"')

    def test_missing_required_relations_subject_inline(self):
        with self.admin_access.repo_cnx() as cnx:
            # missing in_group relation
            cnx.execute('INSERT CWUser X: X login "toto", X upassword "hop"')
            self.assertRaises(ValidationError, cnx.commit)

    def test_composite_1(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')
            cnx.execute('INSERT EmailPart X: X content_format "text/plain", X ordernum 1, '
                        'X content "this is a test"')
            cnx.execute('INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, '
                        'X recipients Y, X parts P '
                         'WHERE Y is EmailAddress, P is EmailPart')
            self.assertTrue(cnx.execute('Email X WHERE X sender Y'))
            cnx.commit()
            cnx.execute('DELETE Email X')
            rset = cnx.execute('Any X WHERE X is EmailPart')
            self.assertEqual(len(rset), 0)
            cnx.commit()
            rset = cnx.execute('Any X WHERE X is EmailPart')
            self.assertEqual(len(rset), 0)

    def test_composite_2(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')
            cnx.execute('INSERT EmailPart X: X content_format "text/plain", X ordernum 1, '
                        'X content "this is a test"')
            cnx.execute('INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, '
                        'X recipients Y, X parts P '
                         'WHERE Y is EmailAddress, P is EmailPart')
            cnx.commit()
            cnx.execute('DELETE Email X')
            cnx.execute('DELETE EmailPart X')
            cnx.commit()
            rset = cnx.execute('Any X WHERE X is EmailPart')
            self.assertEqual(len(rset), 0)

    def test_composite_redirection(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')
            cnx.execute('INSERT EmailPart X: X content_format "text/plain", X ordernum 1, '
                        'X content "this is a test"')
            cnx.execute('INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, '
                        'X recipients Y, X parts P '
                         'WHERE Y is EmailAddress, P is EmailPart')
            cnx.execute('INSERT Email X: X messageid "<2345>", X subject "test2", X sender Y, '
                        'X recipients Y '
                         'WHERE Y is EmailAddress')
            cnx.commit()
            cnx.execute('DELETE X parts Y WHERE X messageid "<1234>"')
            cnx.execute('SET X parts Y WHERE X messageid "<2345>"')
            cnx.commit()
            rset = cnx.execute('Any X WHERE X is EmailPart')
            self.assertEqual(len(rset), 1)
            self.assertEqual(rset.get_entity(0, 0).reverse_parts[0].messageid, '<2345>')

    def test_composite_object_relation_deletion(self):
        with self.admin_access.repo_cnx() as cnx:
            root = cnx.create_entity('Folder', name=u'root')
            a = cnx.create_entity('Folder', name=u'a', parent=root)
            cnx.create_entity('Folder', name=u'b', parent=a)
            cnx.create_entity('Folder', name=u'c', parent=root)
            cnx.commit()
            cnx.execute('DELETE Folder F WHERE F name "a"')
            cnx.execute('DELETE F parent R WHERE R name "root"')
            cnx.commit()
            self.assertEqual([['root'], ['c']],
                             cnx.execute('Any NF WHERE F is Folder, F name NF').rows)
            self.assertEqual([], cnx.execute('Any NF,NP WHERE F parent P, F name NF, P name NP').rows)

    def test_composite_subject_relation_deletion(self):
        with self.admin_access.repo_cnx() as cnx:
            root = cnx.create_entity('Folder', name=u'root')
            a = cnx.create_entity('Folder', name=u'a')
            b = cnx.create_entity('Folder', name=u'b')
            c = cnx.create_entity('Folder', name=u'c')
            root.cw_set(children=(a, c))
            a.cw_set(children=b)
            cnx.commit()
            cnx.execute('DELETE Folder F WHERE F name "a"')
            cnx.execute('DELETE R children F WHERE R name "root"')
            cnx.commit()
            self.assertEqual([['root'], ['c']],
                             cnx.execute('Any NF WHERE F is Folder, F name NF').rows)
            self.assertEqual([], cnx.execute('Any NF,NP WHERE F parent P, F name NF, P name NP').rows)

    def test_unsatisfied_constraints(self):
        with self.admin_access.repo_cnx() as cnx:
            cnx.execute('SET U in_group G WHERE G name "owners", U login "admin"')[0][0]
            with self.assertRaises(ValidationError) as cm:
                cnx.commit()
        self.assertEqual(cm.exception.errors,
                         {'in_group-object': u'RQLConstraint NOT O name "owners" failed'})

    def test_unique_constraint(self):
        with self.admin_access.repo_cnx() as cnx:
            entity = cnx.create_entity('CWGroup', name=u'trout')
            cnx.commit()
            self.assertRaises(ValidationError, cnx.create_entity, 'CWGroup', name=u'trout')
            cnx.rollback()
            cnx.execute('SET X name "trout" WHERE X eid %(x)s', {'x': entity.eid})
            cnx.commit()

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
