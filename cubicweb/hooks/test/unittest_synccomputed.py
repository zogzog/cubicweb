# copyright 2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""unit tests for computed attributes/relations hooks"""

from unittest import TestCase

from yams.buildobjs import EntityType, String, Int, SubjectRelation

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.schema import build_schema_from_namespace


class FormulaDependenciesMatrixTC(TestCase):

    def simple_schema(self):
        THISYEAR = 2014

        class Person(EntityType):
            name = String()
            salary = Int()
            birth_year = Int(required=True)
            works_for = SubjectRelation('Company')
            age = Int(formula='Any %d - D WHERE X birth_year D' % THISYEAR)

        class Company(EntityType):
            name = String()
            total_salary = Int(formula='Any SUM(SA) GROUPBY X WHERE P works_for X, P salary SA')

        schema = build_schema_from_namespace(vars().items())
        return schema

    def setUp(self):
        from cubicweb.hooks.synccomputed import _FormulaDependenciesMatrix
        self.schema = self.simple_schema()
        self.dependencies = _FormulaDependenciesMatrix(self.schema)

    def test_computed_attributes_by_etype(self):
        comp_by_etype = self.dependencies.computed_attribute_by_etype
        self.assertEqual(len(comp_by_etype), 2)
        values = comp_by_etype['Person']
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].rtype, 'age')
        values = comp_by_etype['Company']
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].rtype, 'total_salary')

    def test_computed_attribute_by_relation(self):
        comp_by_rdef = self.dependencies.computed_attribute_by_relation
        self.assertEqual(len(comp_by_rdef), 1)
        key, values = next(iter(comp_by_rdef.items()))
        self.assertEqual(key.rtype, 'works_for')
        self.assertEqual(len(values), 1)
        self.assertEqual(values[0].rtype, 'total_salary')

    def test_computed_attribute_by_etype_attrs(self):
        comp_by_attr = self.dependencies.computed_attribute_by_etype_attrs
        self.assertEqual(len(comp_by_attr), 1)
        values = comp_by_attr['Person']
        self.assertEqual(len(values), 2)
        values = set((rdef.formula, tuple(v))
                     for rdef, v in values.items())
        self.assertEquals(values,
                          set((('Any 2014 - D WHERE X birth_year D', tuple(('birth_year',))),
                               ('Any SUM(SA) GROUPBY X WHERE P works_for X, P salary SA', tuple(('salary',)))))
                          )


class ComputedAttributeTC(CubicWebTC):
    appid = 'data-computed'

    def setup_entities(self, req):
        self.societe = req.create_entity('Societe', nom=u'Foo')
        req.create_entity('Person', name=u'Titi', salaire=1000,
                          travaille=self.societe, birth_year=2001)
        self.tata = req.create_entity('Person', name=u'Tata', salaire=2000,
                                      travaille=self.societe, birth_year=1990)


    def test_update_on_add_remove_relation(self):
        """check the rewriting of a computed attribute"""
        with self.admin_access.web_request() as req:
            self.setup_entities(req)
            req.cnx.commit()
            rset = req.execute('Any S WHERE X salaire_total S, X nom "Foo"')
            self.assertEqual(rset[0][0], 3000)
            # Add relation.
            toto = req.create_entity('Person', name=u'Toto', salaire=1500,
                                   travaille=self.societe, birth_year=1988)
            req.cnx.commit()
            rset = req.execute('Any S WHERE X salaire_total S, X nom "Foo"')
            self.assertEqual(rset[0][0], 4500)
            # Delete relation.
            toto.cw_set(travaille=None)
            req.cnx.commit()
            rset = req.execute('Any S WHERE X salaire_total S, X nom "Foo"')
            self.assertEqual(rset[0][0], 3000)

    def test_recompute_on_attribute_update(self):
        """check the modification of an attribute triggers the update of the
        computed attributes that depend on it"""
        with self.admin_access.web_request() as req:
            self.setup_entities(req)
            req.cnx.commit()
            rset = req.execute('Any S WHERE X salaire_total S, X nom "Foo"')
            self.assertEqual(rset[0][0], 3000)
            # Update attribute.
            self.tata.cw_set(salaire=1000)
            req.cnx.commit()
            rset = req.execute('Any S WHERE X salaire_total S, X nom "Foo"')
            self.assertEqual(rset[0][0], 2000)

    def test_init_on_entity_creation(self):
        """check the computed attribute is initialized on entity creation"""
        with self.admin_access.web_request() as req:
            p = req.create_entity('Person', name=u'Tata', salaire=2000,
                                  birth_year=1990)
            req.cnx.commit()
            rset = req.execute('Any A, X WHERE X age A, X name "Tata"')
            self.assertEqual(rset[0][0], 2014 - 1990)


    def test_recompute_on_ambiguous_relation(self):
        # check we don't end up with TypeResolverException as in #4901163
        with self.admin_access.client_cnx() as cnx:
            societe = cnx.create_entity('Societe', nom=u'Foo')
            cnx.create_entity('MirrorEntity', mirror_of=societe, extid=u'1')
            cnx.commit()

if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
