# -*- coding: utf-8 -*-
# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

    def test_static_vocabulary_check(self):
        self.assertRaises(ValidationError,
                          self.execute,
                          'SET X composite "whatever" WHERE X from_entity FE, FE name "CWUser", X relation_type RT, RT name "in_group"')

    def test_missing_required_relations_subject_inline(self):
        # missing in_group relation
        self.execute('INSERT CWUser X: X login "toto", X upassword "hop"')
        self.assertRaises(ValidationError,
                          self.commit)

    def test_composite_1(self):
        self.execute('INSERT EmailAddress X: X address "toto@logilab.fr", X alias "hop"')
        self.execute('INSERT EmailPart X: X content_format "text/plain", X ordernum 1, X content "this is a test"')
        self.execute('INSERT Email X: X messageid "<1234>", X subject "test", X sender Y, X recipients Y, X parts P '
                     'WHERE Y is EmailAddress, P is EmailPart')
        self.assertTrue(self.execute('Email X WHERE X sender Y'))
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

    def test_unique_constraint(self):
        req = self.request()
        entity = req.create_entity('CWGroup', name=u'trout')
        self.commit()
        self.assertRaises(ValidationError, req.create_entity, 'CWGroup', name=u'trout')
        self.rollback()
        req.execute('SET X name "trout" WHERE X eid %(x)s', {'x': entity.eid})
        self.commit()

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
