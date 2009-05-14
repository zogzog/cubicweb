from logilab.common.testlib import unittest_main
from cubicweb.devtools.apptest import EnvBasedTC
from cubicweb.devtools.testlib import WebTest
from cubicweb.web.views.autoform import AutomaticEntityForm as AEF
from cubicweb.web.formwidgets import AutoCompletionWidget
def rbc(entity, category):
    return [(rschema.type, x) for rschema, tschemas, x in AEF.erelations_by_category(entity, category)]

class AutomaticEntityFormTC(EnvBasedTC):

    def test_custom_widget(self):
        AEF.rfields_kwargs.tag_subject_of(('CWUser', 'login', '*'),
                                          {'widget':AutoCompletionWidget})
        form = self.vreg.select_object('forms', 'edition', self.request(), None,
                                       entity=self.user())
        field = form.field_by_name('login')
        self.assertIsInstance(field.widget, AutoCompletionWidget)
        AEF.rfields_kwargs.del_rtag('CWUser', 'login', '*', 'subject')


    def test_euser_relations_by_category(self):
        #for (rtype, role, stype, otype), tag in AEF.rcategories._tagdefs.items():
        #    if rtype == 'tags':
        #        print rtype, role, stype, otype, ':', tag
        e = self.etype_instance('CWUser')
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
                               ('connait', 'subject'),
                               ('checked_by', 'object'),
                               ])
        # owned_by is defined both as subject and object relations on CWUser
        self.assertListEquals(rbc(e, 'generated'),
                              [('use_email', 'subject'),
                               ('has_text', 'subject'),
                               ('identity', 'subject'),
                               ('is', 'subject'),
                               ('is_instance_of', 'subject'),
                               ('tags', 'object'),
                               ('for_user', 'object'),
                               ('created_by', 'object'),
                               ('wf_info_for', 'object'),
                               ('owned_by', 'object'),
                               ('identity', 'object'),
                               ])

    def test_inlined_view(self):
        self.failUnless(AEF.rinlined.etype_get('CWUser', 'use_email', 'subject'))
        self.failIf(AEF.rinlined.etype_get('CWUser', 'primary_email', 'subject'))

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
                              [('has_text', 'subject'),
                               ('identity', 'subject'),
                               ('is', 'subject'),
                               ('is_instance_of', 'subject'),
                               ('identity', 'object'),
                               ])

    def test_edition_form(self):
        rset = self.execute('CWUser X LIMIT 1')
        form = self.vreg.select_object('forms', 'edition', rset.req, rset,
                                       row=0, col=0)
        # should be also selectable by specifying entity
        self.vreg.select_object('forms', 'edition', self.request(), None,
                                entity=rset.get_entity(0, 0))
        self.failIf(any(f for f in form.fields if f is None))


class FormViewsTC(WebTest):
    def test_delete_conf_formview(self):
        rset = self.execute('CWGroup X')
        self.view('deleteconf', rset, template=None).source

    def test_automatic_edition_formview(self):
        rset = self.execute('CWUser X')
        self.view('edition', rset, row=0, template=None).source

    def test_automatic_edition_formview(self):
        rset = self.execute('CWUser X')
        self.view('copy', rset, row=0, template=None).source

    def test_automatic_creation_formview(self):
        self.view('creation', None, etype='CWUser', template=None).source

    def test_automatic_muledit_formview(self):
        rset = self.execute('CWUser X')
        self.view('muledit', rset, template=None).source

    def test_automatic_reledit_formview(self):
        rset = self.execute('CWUser X')
        self.view('reledit', rset, row=0, rtype='login', template=None).source

    def test_automatic_inline_edit_formview(self):
        geid = self.execute('CWGroup X LIMIT 1')[0][0]
        rset = self.execute('CWUser X LIMIT 1')
        self.view('inline-edition', rset, row=0, rtype='in_group', peid=geid, template=None).source

    def test_automatic_inline_creation_formview(self):
        geid = self.execute('CWGroup X LIMIT 1')[0][0]
        self.view('inline-creation', None, etype='CWUser', rtype='in_group', peid=geid, template=None).source


if __name__ == '__main__':
    unittest_main()
