from logilab.common.testlib import TestCase, unittest_main
from cubicweb.rtags import RelationTags, RelationTagsSet

class RelationTagsTC(TestCase):

    def test_rtags_expansion(self):
        rtags = RelationTags()
        rtags.tag_relation('primary', ('Societe', 'travaille', '*'), 'subject', )
        rtags.tag_relation('secondary', ('*', 'evaluee', '*'), 'subject')
        rtags.tag_relation('generated', ('*', 'tags', '*'), 'object')        
        self.assertEquals(rtags.get('evaluee', 'subject', 'Note'), 'secondary')
        self.assertEquals(rtags.get('travaille', 'subject', 'Societe'), 'primary')
        self.assertEquals(rtags.get('travaille', 'subject', 'Note'), None)
        self.assertEquals(rtags.get('tags', 'subject', 'Note'), None)
        self.assertEquals(rtags.get('tags', 'object', 'Note'), 'generated')

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
        rtags.tag_relation('primary', ('Societe', 'travaille', '*'), 'subject', )
        rtags.tag_relation('secondary', ('*', 'travaille', '*'), 'subject')
        self.assertEquals(rtags.get('travaille', 'subject', 'Societe'), set(('primary', 'secondary')))
        self.assertEquals(rtags.get('travaille', 'subject', 'Note'), set(('secondary',)))
        self.assertEquals(rtags.get('tags', 'subject', 'Note'), set())

if __name__ == '__main__':
    unittest_main()
