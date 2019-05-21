# -*- coding: utf-8 -*-
# copyright 2015-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr -- mailto:contact@logilab.fr
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.
"""Tests for cubicweb.dataimport.importer"""

from logilab.common.testlib import TestCase, unittest_main

from cubicweb import Binary, ValidationError
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.dataimport import RQLObjectStore, ucsvreader
from cubicweb.dataimport.importer import (ExtEntity, ExtEntitiesImporter, RelationMapping,
                                          SimpleImportLog, use_extid_as_cwuri, drop_extra_values)


class RelationMappingTC(CubicWebTC):

    def test_nosource(self):
        with self.admin_access.repo_cnx() as cnx:
            alice_eid = cnx.create_entity('Personne', nom=u'alice').eid
            bob_eid = cnx.create_entity('Personne', nom=u'bob', connait=alice_eid).eid
            cnx.commit()
            mapping = RelationMapping(cnx)
            self.assertEqual(mapping['connait'],
                             set([(bob_eid, alice_eid), (alice_eid, bob_eid)]))

    def test_with_source(self):
        with self.admin_access.repo_cnx() as cnx:
            alice_eid = cnx.create_entity('Personne', nom=u'alice').eid
            bob_eid = cnx.create_entity('Personne', nom=u'bob', connait=alice_eid).eid
            cnx.commit()
            mapping = RelationMapping(cnx, cnx.find('CWSource', name=u'system').one())
            self.assertEqual(mapping['connait'],
                             set([(bob_eid, alice_eid), (alice_eid, bob_eid)]))


class ExtEntitiesImporterTC(CubicWebTC):

    def importer(self, cnx):
        store = RQLObjectStore(cnx)
        return ExtEntitiesImporter(self.schema, store, raise_on_error=True)

    def test_simple_import(self):
        with self.admin_access.repo_cnx() as cnx:
            importer = self.importer(cnx)
            personne = ExtEntity('Personne', 1, {'nom': set([u'de la lune']),
                                                 'prenom': set([u'Jean'])})
            importer.import_entities([personne])
            cnx.commit()
            rset = cnx.execute('Any X WHERE X is Personne')
            entity = rset.get_entity(0, 0)
            self.assertEqual(entity.nom, u'de la lune')
            self.assertEqual(entity.prenom, u'Jean')

    def test_bytes_attribute(self):
        with self.admin_access.repo_cnx() as cnx:
            importer = self.importer(cnx)
            personne = ExtEntity('Personne', 1, {'photo': set([b'poilu']),
                                                 'nom': set([u'alf'])})
            importer.import_entities([personne])
            cnx.commit()
            entity = cnx.find('Personne').one()
            self.assertEqual(entity.photo.getvalue(), b'poilu')

    def test_binary_in_values(self):
        with self.admin_access.repo_cnx() as cnx:
            importer = self.importer(cnx)
            # Use a list to put a Binary in "values" (since Binary is not
            # hashable, a set cannot be used).
            personne = ExtEntity('Personne', 1, {'photo': [Binary(b'poilu')],
                                                 'nom': set([u'alf'])})
            importer.import_entities([personne])
            cnx.commit()
            entity = cnx.find('Personne').one()
            self.assertEqual(entity.photo.getvalue(), b'poilu')

    def test_import_missing_required_attribute(self):
        """Check import of ext entity with missing required attribute"""
        with self.admin_access.repo_cnx() as cnx:
            importer = self.importer(cnx)
            tag = ExtEntity('Personne', 2, {'prenom': set([u'Jean'])})
            self.assertRaises(ValidationError, importer.import_entities, [tag])

    def test_import_inlined_relation(self):
        """Check import of ext entities with inlined relation"""
        with self.admin_access.repo_cnx() as cnx:
            importer = self.importer(cnx)
            richelieu = ExtEntity('Personne', 3, {'nom': set([u'Richelieu']),
                                                  'enfant': set([4])})
            athos = ExtEntity('Personne', 4, {'nom': set([u'Athos'])})
            importer.import_entities([athos, richelieu])
            cnx.commit()
            rset = cnx.execute('Any X WHERE X is Personne, X nom "Richelieu"')
            entity = rset.get_entity(0, 0)
            self.assertEqual(entity.enfant[0].nom, 'Athos')

    def test_import_non_inlined_relation(self):
        """Check import of ext entities with non inlined relation"""
        with self.admin_access.repo_cnx() as cnx:
            importer = self.importer(cnx)
            richelieu = ExtEntity('Personne', 5, {'nom': set([u'Richelieu']),
                                                  'connait': set([6])})
            athos = ExtEntity('Personne', 6, {'nom': set([u'Athos'])})
            importer.import_entities([athos, richelieu])
            cnx.commit()
            rset = cnx.execute('Any X WHERE X is Personne, X nom "Richelieu"')
            entity = rset.get_entity(0, 0)
            self.assertEqual(entity.connait[0].nom, 'Athos')
            rset = cnx.execute('Any X WHERE X is Personne, X nom "Athos"')
            entity = rset.get_entity(0, 0)
            self.assertEqual(entity.connait[0].nom, 'Richelieu')

    def test_import_missing_inlined_relation(self):
        """Check import of ext entity with missing inlined relation"""
        with self.admin_access.repo_cnx() as cnx:
            importer = self.importer(cnx)
            richelieu = ExtEntity('Personne', 7,
                                  {'nom': set([u'Richelieu']), 'enfant': set([8])})
            self.assertRaises(Exception, importer.import_entities, [richelieu])
            cnx.commit()
            rset = cnx.execute('Any X WHERE X is Personne, X nom "Richelieu"')
            self.assertEqual(len(rset), 0)

    def test_import_missing_non_inlined_relation(self):
        """Check import of ext entity with missing non-inlined relation"""
        with self.admin_access.repo_cnx() as cnx:
            importer = self.importer(cnx)
            richelieu = ExtEntity('Personne', 9,
                                  {'nom': set([u'Richelieu']), 'connait': set([10])})
            self.assertRaises(Exception, importer.import_entities, [richelieu])
            cnx.commit()
            rset = cnx.execute('Any X WHERE X is Personne, X nom "Richelieu"')
            entity = rset.get_entity(0, 0)
            self.assertEqual(entity.nom, u'Richelieu')
            self.assertEqual(len(entity.connait), 0)

    def test_import_order(self):
        """Check import of ext entity in both order"""
        with self.admin_access.repo_cnx() as cnx:
            importer = self.importer(cnx)
            richelieu = ExtEntity('Personne', 3, {'nom': set([u'Richelieu']),
                                                  'enfant': set([4])})
            athos = ExtEntity('Personne', 4, {'nom': set([u'Athos'])})
            importer.import_entities([richelieu, athos])
            cnx.commit()
            rset = cnx.execute('Any X WHERE X is Personne, X nom "Richelieu"')
            entity = rset.get_entity(0, 0)
            self.assertEqual(entity.enfant[0].nom, 'Athos')

    def test_update(self):
        """Check update of ext entity"""
        with self.admin_access.repo_cnx() as cnx:
            importer = self.importer(cnx)
            # First import
            richelieu = ExtEntity('Personne', 11,
                                  {'nom': set([u'Richelieu Diacre'])})
            importer.import_entities([richelieu])
            cnx.commit()
            rset = cnx.execute('Any X WHERE X is Personne')
            entity = rset.get_entity(0, 0)
            self.assertEqual(entity.nom, u'Richelieu Diacre')
            # Second import
            richelieu = ExtEntity('Personne', 11,
                                  {'nom': set([u'Richelieu Cardinal'])})
            importer.import_entities([richelieu])
            cnx.commit()
            rset = cnx.execute('Any X WHERE X is Personne')
            self.assertEqual(len(rset), 1)
            entity = rset.get_entity(0, 0)
            self.assertEqual(entity.nom, u'Richelieu Cardinal')


class UseExtidAsCwuriTC(TestCase):

    def test(self):
        personne = ExtEntity('Personne', b'1', {'nom': set([u'de la lune']),
                                                'prenom': set([u'Jean'])})
        mapping = {}
        set_cwuri = use_extid_as_cwuri(mapping)
        list(set_cwuri((personne,)))
        self.assertIn('cwuri', personne.values)
        self.assertEqual(personne.values['cwuri'], set([u'1']))
        mapping[b'1'] = 'whatever'
        personne.values.pop('cwuri')
        list(set_cwuri((personne,)))
        self.assertNotIn('cwuri', personne.values)
        personne = ExtEntity('Personne', u'ééé', {})
        mapping = {}
        set_cwuri = use_extid_as_cwuri(mapping)
        list(set_cwuri((personne,)))
        self.assertIn('cwuri', personne.values)
        self.assertEqual(personne.values['cwuri'], set([u'ééé']))


class DropExtraValuesTC(CubicWebTC):

    def test(self):
        personne = ExtEntity('Personne', b'1', {'nom': set([u'de la lune', 'di la luna']),
                                                'prenom': set([u'Jean']),
                                                'enfant': set('23'),
                                                'connait': set('45')})
        log = SimpleImportLog('<unspecified>')
        list(drop_extra_values((personne,), self.schema, log))
        self.assertEqual(len(personne.values['nom']), 1)
        self.assertEqual(len(personne.values['enfant']), 1)
        self.assertEqual(len(personne.values['connait']), 2)
        self.assertEqual(len(log.logs), 2)


def extentities_from_csv(fpath):
    """Yield ExtEntity read from `fpath` CSV file."""
    with open(fpath, 'rb') as f:
        for uri, name, knows in ucsvreader(f, skipfirst=True, skip_empty=False):
            yield ExtEntity('Personne', uri,
                            {'nom': set([name]), 'connait': set([knows])})


class DataimportFunctionalTC(CubicWebTC):

    def test_csv(self):
        extenties = extentities_from_csv(self.datapath('people.csv'))
        with self.admin_access.repo_cnx() as cnx:
            store = RQLObjectStore(cnx)
            importer = ExtEntitiesImporter(self.schema, store)
            importer.import_entities(extenties)
            cnx.commit()
            rset = cnx.execute('String N WHERE X nom N, X connait Y, Y nom "Alice"')
            self.assertEqual(rset[0][0], u'Bob')


if __name__ == '__main__':
    unittest_main()
