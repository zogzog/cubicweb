from logilab.common.testlib import TestCase, unittest_main
from cubicweb.rtags import RelationTags

class RelationTagsTC(TestCase):
    
    def test_rtags_expansion(self):
        rtags = RelationTags()
        rtags.set_rtag('primary', 'travaille', 'subject', 'Societe')
        rtags.set_rtag('secondary', 'evaluee', 'subject')
        rtags.set_rtag('generated', 'tags', 'object')
        self.assertEquals(rtags.rtag('evaluee', 'subject', 'Note'), 'secondary')
        self.assertEquals(rtags.rtag('travaille', 'subject', 'Societe'), 'primary')
        self.assertEquals(rtags.rtag('travaille', 'subject', 'Note'), None)
        self.assertEquals(rtags.rtag('tags', 'subject', 'Note'), None)
        self.assertEquals(rtags.rtag('tags', 'object', 'Note'), 'generated')
        
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

if __name__ == '__main__':
    unittest_main()
