"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from logilab.common.testlib import TestCase, unittest_main
from cubicweb.rtags import RelationTags, RelationTagsSet, RelationTagsDict

class RelationTagsTC(TestCase):

    def test_rtags_expansion(self):
        rtags = RelationTags()
        rtags.tag_subject_of(('Societe', 'travaille', '*'), 'primary')
        rtags.tag_subject_of(('*', 'evaluee', '*'), 'secondary')
        rtags.tag_object_of(('*', 'tags', '*'), 'generated')
        self.assertEquals(rtags.get('Note', 'evaluee', '*', 'subject'),
                          'secondary')
        self.assertEquals(rtags.get('Societe', 'travaille', '*', 'subject'),
                          'primary')
        self.assertEquals(rtags.get('Note', 'travaille', '*', 'subject'),
                          None)
        self.assertEquals(rtags.get('Note', 'tags', '*', 'subject'),
                          None)
        self.assertEquals(rtags.get('*', 'tags', 'Note', 'object'),
                          'generated')
        self.assertEquals(rtags.get('Tag', 'tags', '*', 'object'),
                          'generated')

#         self.assertEquals(rtags.rtag('evaluee', 'Note', 'subject'), set(('secondary', 'link')))
#         self.assertEquals(rtags.is_inlined('evaluee', 'Note', 'subject'), False)
#         self.assertEquals(rtags.rtag('evaluee', 'Personne', 'subject'), set(('secondary', 'link')))
#         self.assertEquals(rtags.is_inlined('evaluee', 'Personne', 'subject'), False)
#         self.assertEquals(rtags.rtag('ecrit_par', 'Note', 'object'), set(('inlineview', 'link')))
#         self.assertEquals(rtags.is_inlined('ecrit_par', 'Note', 'object'), True)
#         class Personne2(Personne):
#             id = 'Personne'
#             __rtags__ = {
#                 ('evaluee', 'Note', 'subject') : set(('inlineview',)),
#                 }
#         self.vreg.register_appobject_class(Personne2)
#         rtags = Personne2.rtags
#         self.assertEquals(rtags.rtag('evaluee', 'Note', 'subject'), set(('inlineview', 'link')))
#         self.assertEquals(rtags.is_inlined('evaluee', 'Note', 'subject'), True)
#         self.assertEquals(rtags.rtag('evaluee', 'Personne', 'subject'), set(('secondary', 'link')))
#         self.assertEquals(rtags.is_inlined('evaluee', 'Personne', 'subject'), False)


    def test_rtagset_expansion(self):
        rtags = RelationTagsSet()
        rtags.tag_subject_of(('Societe', 'travaille', '*'), 'primary')
        rtags.tag_subject_of(('*', 'travaille', '*'), 'secondary')
        self.assertEquals(rtags.get('Societe', 'travaille', '*', 'subject'),
                          set(('primary', 'secondary')))
        self.assertEquals(rtags.get('Note', 'travaille', '*', 'subject'),
                          set(('secondary',)))
        self.assertEquals(rtags.get('Note', 'tags', "*", 'subject'),
                          set())

    def test_rtagdict_expansion(self):
        rtags = RelationTagsDict()
        rtags.tag_subject_of(('Societe', 'travaille', '*'),
                             {'key1': 'val1', 'key2': 'val1'})
        rtags.tag_subject_of(('*', 'travaille', '*'),
                             {'key1': 'val0', 'key3': 'val0'})
        rtags.tag_subject_of(('Societe', 'travaille', '*'),
                             {'key2': 'val2'})
        self.assertEquals(rtags.get('Societe', 'travaille', '*', 'subject'),
                          {'key1': 'val1', 'key2': 'val2', 'key3': 'val0'})
        self.assertEquals(rtags.get('Note', 'travaille', '*', 'subject'),
                          {'key1': 'val0', 'key3': 'val0'})
        self.assertEquals(rtags.get('Note', 'tags', "*", 'subject'),
                          {})

        rtags.setdefault(('Societe', 'travaille', '*', 'subject'), 'key1', 'val4')
        rtags.setdefault(('Societe', 'travaille', '*', 'subject'), 'key4', 'val4')
        self.assertEquals(rtags.get('Societe', 'travaille', '*', 'subject'),
                          {'key1': 'val1', 'key2': 'val2', 'key3': 'val0', 'key4': 'val4'})

if __name__ == '__main__':
    unittest_main()
