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
"""

"""
from logilab.common.testlib import TestCase, unittest_main
from cubicweb.rtags import RelationTags, RelationTagsSet, RelationTagsDict

class RelationTagsTC(TestCase):

    def test_rtags_expansion(self):
        rtags = RelationTags()
        rtags.tag_subject_of(('Societe', 'travaille', '*'), 'primary')
        rtags.tag_subject_of(('*', 'evaluee', '*'), 'secondary')
        rtags.tag_object_of(('*', 'tags', '*'), 'generated')
        self.assertEqual(rtags.get('Note', 'evaluee', '*', 'subject'),
                          'secondary')
        self.assertEqual(rtags.get('Societe', 'travaille', '*', 'subject'),
                          'primary')
        self.assertEqual(rtags.get('Note', 'travaille', '*', 'subject'),
                          None)
        self.assertEqual(rtags.get('Note', 'tags', '*', 'subject'),
                          None)
        self.assertEqual(rtags.get('*', 'tags', 'Note', 'object'),
                          'generated')
        self.assertEqual(rtags.get('Tag', 'tags', '*', 'object'),
                          'generated')

#         self.assertEqual(rtags.rtag('evaluee', 'Note', 'subject'), set(('secondary', 'link')))
#         self.assertEqual(rtags.is_inlined('evaluee', 'Note', 'subject'), False)
#         self.assertEqual(rtags.rtag('evaluee', 'Personne', 'subject'), set(('secondary', 'link')))
#         self.assertEqual(rtags.is_inlined('evaluee', 'Personne', 'subject'), False)
#         self.assertEqual(rtags.rtag('ecrit_par', 'Note', 'object'), set(('inlineview', 'link')))
#         self.assertEqual(rtags.is_inlined('ecrit_par', 'Note', 'object'), True)
#         class Personne2(Personne):
#             id = 'Personne'
#             __rtags__ = {
#                 ('evaluee', 'Note', 'subject') : set(('inlineview',)),
#                 }
#         self.vreg.register(Personne2)
#         rtags = Personne2.rtags
#         self.assertEqual(rtags.rtag('evaluee', 'Note', 'subject'), set(('inlineview', 'link')))
#         self.assertEqual(rtags.is_inlined('evaluee', 'Note', 'subject'), True)
#         self.assertEqual(rtags.rtag('evaluee', 'Personne', 'subject'), set(('secondary', 'link')))
#         self.assertEqual(rtags.is_inlined('evaluee', 'Personne', 'subject'), False)


    def test_rtagset_expansion(self):
        rtags = RelationTagsSet()
        rtags.tag_subject_of(('Societe', 'travaille', '*'), 'primary')
        rtags.tag_subject_of(('*', 'travaille', '*'), 'secondary')
        self.assertEqual(rtags.get('Societe', 'travaille', '*', 'subject'),
                          set(('primary', 'secondary')))
        self.assertEqual(rtags.get('Note', 'travaille', '*', 'subject'),
                          set(('secondary',)))
        self.assertEqual(rtags.get('Note', 'tags', "*", 'subject'),
                          set())

    def test_rtagdict_expansion(self):
        rtags = RelationTagsDict()
        rtags.tag_subject_of(('Societe', 'travaille', '*'),
                             {'key1': 'val1', 'key2': 'val1'})
        rtags.tag_subject_of(('*', 'travaille', '*'),
                             {'key1': 'val0', 'key3': 'val0'})
        rtags.tag_subject_of(('Societe', 'travaille', '*'),
                             {'key2': 'val2'})
        self.assertEqual(rtags.get('Societe', 'travaille', '*', 'subject'),
                          {'key1': 'val1', 'key2': 'val2', 'key3': 'val0'})
        self.assertEqual(rtags.get('Note', 'travaille', '*', 'subject'),
                          {'key1': 'val0', 'key3': 'val0'})
        self.assertEqual(rtags.get('Note', 'tags', "*", 'subject'),
                          {})

        rtags.setdefault(('Societe', 'travaille', '*', 'subject'), 'key1', 'val4')
        rtags.setdefault(('Societe', 'travaille', '*', 'subject'), 'key4', 'val4')
        self.assertEqual(rtags.get('Societe', 'travaille', '*', 'subject'),
                          {'key1': 'val1', 'key2': 'val2', 'key3': 'val0', 'key4': 'val4'})

if __name__ == '__main__':
    unittest_main()
