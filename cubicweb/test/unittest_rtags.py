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

from cubicweb.devtools.testlib import BaseTestCase
from cubicweb.rtags import RelationTags, RelationTagsSet, RelationTagsDict


class RelationTagsTC(BaseTestCase):

    def setUp(self):
        self.rtags = RelationTags(__module__=__name__)
        self.rtags.tag_subject_of(('Societe', 'travaille', '*'), 'primary')
        self.rtags.tag_subject_of(('*', 'evaluee', '*'), 'secondary')
        self.rtags.tag_object_of(('*', 'tags', '*'), 'generated')

    def test_expansion(self):
        self.assertEqual(self.rtags.get('Note', 'evaluee', '*', 'subject'),
                         'secondary')
        self.assertEqual(self.rtags.get('Societe', 'travaille', '*', 'subject'),
                         'primary')
        self.assertEqual(self.rtags.get('Note', 'travaille', '*', 'subject'),
                         None)
        self.assertEqual(self.rtags.get('Note', 'tags', '*', 'subject'),
                         None)
        self.assertEqual(self.rtags.get('*', 'tags', 'Note', 'object'),
                         'generated')
        self.assertEqual(self.rtags.get('Tag', 'tags', '*', 'object'),
                         'generated')

    def test_expansion_with_parent(self):
        derived_rtags = self.rtags.derive(__name__, None)
        derived_rtags.tag_subject_of(('Societe', 'travaille', '*'), 'secondary')
        derived_rtags.tag_subject_of(('Note', 'evaluee', '*'), 'primary')
        self.rtags.tag_object_of(('*', 'tags', '*'), 'hidden')

        self.assertEqual(derived_rtags.get('Note', 'evaluee', '*', 'subject'),
                         'primary')
        self.assertEqual(derived_rtags.get('Societe', 'evaluee', '*', 'subject'),
                         'secondary')
        self.assertEqual(derived_rtags.get('Societe', 'travaille', '*', 'subject'),
                         'secondary')
        self.assertEqual(derived_rtags.get('Note', 'travaille', '*', 'subject'),
                         None)
        self.assertEqual(derived_rtags.get('*', 'tags', 'Note', 'object'),
                         'hidden')


class RelationTagsSetTC(BaseTestCase):

    def setUp(self):
        self.rtags = RelationTagsSet(__module__=__name__)
        self.rtags.tag_subject_of(('Societe', 'travaille', '*'), 'primary')
        self.rtags.tag_subject_of(('*', 'travaille', '*'), 'secondary')

    def test_expansion(self):
        self.assertEqual(self.rtags.get('Societe', 'travaille', '*', 'subject'),
                         set(('primary', 'secondary')))
        self.assertEqual(self.rtags.get('Note', 'travaille', '*', 'subject'),
                         set(('secondary',)))
        self.assertEqual(self.rtags.get('Note', 'tags', "*", 'subject'),
                         set())

    def test_expansion_with_parent(self):
        derived_rtags = self.rtags.derive(__name__, None)
        derived_rtags.tag_subject_of(('Societe', 'travaille', '*'), 'derived_primary')
        self.assertEqual(derived_rtags.get('Societe', 'travaille', '*', 'subject'),
                         set(('derived_primary', 'secondary')))
        self.assertEqual(derived_rtags.get('Note', 'travaille', '*', 'subject'),
                         set(('secondary',)))

        derived_rtags.tag_subject_of(('*', 'travaille', '*'), 'derived_secondary')
        self.assertEqual(derived_rtags.get('Societe', 'travaille', '*', 'subject'),
                         set(('derived_primary', 'derived_secondary')))
        self.assertEqual(derived_rtags.get('Note', 'travaille', '*', 'subject'),
                         set(('derived_secondary',)))

        self.assertEqual(derived_rtags.get('Note', 'tags', "*", 'subject'),
                         set())


class RelationTagsDictTC(BaseTestCase):

    def setUp(self):
        self.rtags = RelationTagsDict(__module__=__name__)
        self.rtags.tag_subject_of(('Societe', 'travaille', '*'),
                                  {'key1': 'val1', 'key2': 'val1'})
        self.rtags.tag_subject_of(('*', 'travaille', '*'),
                                  {'key1': 'val0', 'key3': 'val0'})
        self.rtags.tag_subject_of(('Societe', 'travaille', '*'),
                                  {'key2': 'val2'})

    def test_expansion(self):
        self.assertEqual(self.rtags.get('Societe', 'travaille', '*', 'subject'),
                         {'key1': 'val1', 'key2': 'val2', 'key3': 'val0'})
        self.assertEqual(self.rtags.get('Note', 'travaille', '*', 'subject'),
                         {'key1': 'val0', 'key3': 'val0'})
        self.assertEqual(self.rtags.get('Note', 'tags', "*", 'subject'),
                         {})

        self.rtags.setdefault(('Societe', 'travaille', '*', 'subject'), 'key1', 'val4')
        self.rtags.setdefault(('Societe', 'travaille', '*', 'subject'), 'key4', 'val4')
        self.assertEqual(self.rtags.get('Societe', 'travaille', '*', 'subject'),
                         {'key1': 'val1', 'key2': 'val2', 'key3': 'val0', 'key4': 'val4'})

    def test_expansion_with_parent(self):
        derived_rtags = self.rtags.derive(__name__, None)

        derived_rtags.tag_subject_of(('Societe', 'travaille', '*'),
                                     {'key0': 'val0'})
        self.assertEqual(derived_rtags.get('Societe', 'travaille', '*', 'subject'),
                         {'key0': 'val0', 'key1': 'val0', 'key3': 'val0'})
        self.assertEqual(derived_rtags.get('Note', 'travaille', '*', 'subject'),
                         {'key1': 'val0', 'key3': 'val0'})
        self.assertEqual(derived_rtags.get('Note', 'tags', "*", 'subject'),
                         {})

        derived_rtags.tag_subject_of(('*', 'travaille', '*'),
                                     {'key0': 'val00', 'key4': 'val4'})
        self.assertEqual(derived_rtags.get('Societe', 'travaille', '*', 'subject'),
                         {'key0': 'val0', 'key4': 'val4'})
        self.assertEqual(derived_rtags.get('Note', 'travaille', '*', 'subject'),
                         {'key0': 'val00', 'key4': 'val4'})


if __name__ == '__main__':
    import unittest
    unittest.main()
