from logilab.common.testlib import unittest_main
from cubicweb.devtools.apptest import EnvBasedTC
from cubicweb.web.views.editforms import AutomaticEntityForm as AEF

def rbc(entity, category):
    return [(rschema.type, x) for rschema, tschemas, x in AEF.erelations_by_category(entity, category)]

class AutomaticEntityFormTC(EnvBasedTC):

    def test_euser_relations_by_category(self):
        #for (rtype, role, stype, otype), tag in AEF.rcategories._tagdefs.items():
        #    if rtype == 'tags':
        #        print rtype, role, stype, otype, ':', tag
        e = self.etype_instance('EUser')
        # see custom configuration in views.euser
        self.assertEquals(rbc(e, 'primary'),
                          [('login', 'subject'),
                           ('upassword', 'subject'),
                           ('in_group', 'subject'),
                           ('in_state', 'subject'),
                           ('eid', 'subject'),
                           ])
        self.assertListEquals(rbc(e, 'secondary'),
                              [('firstname', 'subject'),
                               ('surname', 'subject')
                               ])
        self.assertListEquals(rbc(e, 'metadata'),
                              [('last_login_time', 'subject'),
                               ('created_by', 'subject'),
                               ('creation_date', 'subject'),
                               ('modification_date', 'subject'),
                               ('owned_by', 'subject'),
                               ('bookmarked_by', 'object'),
                               ])        
        self.assertListEquals(rbc(e, 'generic'),
                              [('primary_email', 'subject'),
                               ('use_email', 'subject'),
                               ('connait', 'subject'),
                               ('checked_by', 'object'),
                               ])
        # owned_by is defined both as subject and object relations on EUser
        self.assertListEquals(rbc(e, 'generated'),
                              [('is', 'subject'),
                               ('is_instance_of', 'subject'),
                               ('tags', 'object'),
                               ('for_user', 'object'),
                               ('created_by', 'object'),
                               ('wf_info_for', 'object'),
                               ('owned_by', 'object'),
                               ])

    def test_inlined_view(self):
        self.failUnless(AEF.rinlined.etype_rtag('EUser', 'use_email', 'subject'))
        self.failIf(AEF.rinlined.etype_rtag('EUser', 'primary_email', 'subject'))
                        
    def test_personne_relations_by_category(self):
        e = self.etype_instance('Personne')
        self.assertListEquals(rbc(e, 'primary'),
                              [('nom', 'subject'),
                               ('eid', 'subject')
                               ])
        self.assertListEquals(rbc(e, 'secondary'),
                              [('prenom', 'subject'),
                               ('sexe', 'subject'),
                               ('promo', 'subject'),
                               ('titre', 'subject'),
                               ('ass', 'subject'),
                               ('web', 'subject'),
                               ('tel', 'subject'),
                               ('fax', 'subject'),
                               ('datenaiss', 'subject'),
                               ('test', 'subject'),
                               ('description', 'subject'),
                               ('salary', 'subject')
                               ])
        self.assertListEquals(rbc(e, 'metadata'),
                              [('created_by', 'subject'),
                               ('creation_date', 'subject'),
                               ('modification_date', 'subject'),
                               ('owned_by', 'subject'),
                               ])        
        self.assertListEquals(rbc(e, 'generic'),
                              [('travaille', 'subject'),
                               ('connait', 'object')
                               ])
        self.assertListEquals(rbc(e, 'generated'),
                              [('is', 'subject'),
                               ('is_instance_of', 'subject'),
                               ])
if __name__ == '__main__':
    unittest_main()
