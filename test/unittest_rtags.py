from logilab.common.testlib import TestCase, unittest_main
from cubicweb.rtags import RelationTags, RelationTagsSet

class RelationTagsTC(TestCase):

    def test_rtags_expansion(self):
        rtags = RelationTags()
        rtags.tag_relation('!Societe', 'travaille', '*', 'primary')
        rtags.tag_relation('!*', 'evaluee', '*', 'secondary')
        rtags.tag_relation('*', 'tags', '!*', 'generated')
        self.assertEquals(rtags.get('!Note', 'evaluee', '*'),
                          'secondary')
        self.assertEquals(rtags.get('Note', 'evaluee', '*', 'subject'),
                          'secondary')
        self.assertEquals(rtags.get('!Societe', 'travaille', '*'),
                          'primary')
        self.assertEquals(rtags.get('!Note', 'travaille', '*'),
                          None)
        self.assertEquals(rtags.get('!Note', 'tags', '*'),
                          None)
        self.assertEquals(rtags.get('*', 'tags', '!Note'),
                          'generated')
        self.assertEquals(rtags.get('Tag', 'tags', '!*'),
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
#         self.vreg.register_vobject_class(Personne2)
#         rtags = Personne2.rtags
#         self.assertEquals(rtags.rtag('evaluee', 'Note', 'subject'), set(('inlineview', 'link')))
#         self.assertEquals(rtags.is_inlined('evaluee', 'Note', 'subject'), True)
#         self.assertEquals(rtags.rtag('evaluee', 'Personne', 'subject'), set(('secondary', 'link')))
#         self.assertEquals(rtags.is_inlined('evaluee', 'Personne', 'subject'), False)


    def test_rtagset_expansion(self):
        rtags = RelationTagsSet()
        rtags.tag_relation('!Societe', 'travaille', '*', 'primary')
        rtags.tag_relation('!*', 'travaille', '*', 'secondary')
        self.assertEquals(rtags.get('!Societe', 'travaille', '*'),
                          set(('primary', 'secondary')))
        self.assertEquals(rtags.get('Societe', 'travaille', '*', 'subject'),
                          set(('primary', 'secondary')))
        self.assertEquals(rtags.get('!Note', 'travaille', '*'),
                          set(('secondary',)))
        self.assertEquals(rtags.get('!Note', 'tags', "*"),
                          set())

if __name__ == '__main__':
    unittest_main()
