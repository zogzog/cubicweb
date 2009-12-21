"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from logilab.common.testlib import unittest_main, mock_object
from logilab.common.compat import any

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web import uicfg
from cubicweb.web.formwidgets import AutoCompletionWidget

AFFK = uicfg.autoform_field_kwargs
AFS = uicfg.autoform_section

def rbc(entity, formtype, section):
    return [(rschema.type, x) for rschema, tschemas, x in AFS.relations_by_section(entity, formtype, section)]

class AutomaticEntityFormTC(CubicWebTC):

    def test_custom_widget(self):
        AFFK.tag_subject_of(('CWUser', 'login', '*'),
                            {'widget': AutoCompletionWidget(autocomplete_initfunc='get_logins')})
        form = self.vreg['forms'].select('edition', self.request(),
                                         entity=self.user())
        field = form.field_by_name('login', 'subject')
        self.assertIsInstance(field.widget, AutoCompletionWidget)
        AFFK.del_rtag('CWUser', 'login', '*', 'subject')


    def test_cwuser_relations_by_category(self):
        #for (rtype, role, stype, otype), tag in AEF.rcategories._tagdefs.items():
        #    if rtype == 'tags':
        #        print rtype, role, stype, otype, ':', tag
        e = self.vreg['etypes'].etype_class('CWUser')(self.request())
        # see custom configuration in views.cwuser
        self.assertEquals(rbc(e, 'main', 'attributes'),
                          [('login', 'subject'),
                           ('upassword', 'subject'),
                           ('firstname', 'subject'),
                           ('surname', 'subject'),
                           ('in_group', 'subject'),
                           ('eid', 'subject'),
                           ])
        self.assertListEquals(rbc(e, 'muledit', 'attributes'),
                              [('login', 'subject'),
                               ('upassword', 'subject'),
                               ('in_group', 'subject'),
                               ('eid', 'subject'),
                               ])
        self.assertListEquals(rbc(e, 'main', 'metadata'),
                              [('last_login_time', 'subject'),
                               ('modification_date', 'subject'),
                               ('created_by', 'subject'),
                               ('creation_date', 'subject'),
                               ('cwuri', 'subject'),
                               ('owned_by', 'subject'),
                               ('bookmarked_by', 'object'),
                               ])
        self.assertListEquals(rbc(e, 'main', 'relations'),
                              [('primary_email', 'subject'),
                               ('custom_workflow', 'subject'),
                               ('connait', 'subject'),
                               ('checked_by', 'object'),
                               ])
        self.assertListEquals(rbc(e, 'main', 'inlined'),
                              [('use_email', 'subject'),
                               ])
        # owned_by is defined both as subject and object relations on CWUser
        self.assertListEquals(rbc(e, 'main', 'hidden'),
                              [('in_state', 'subject'),
                               ('is', 'subject'),
                               ('is_instance_of', 'subject'),
                               ('has_text', 'subject'),
                               ('identity', 'subject'),
                               ('tags', 'object'),
                               ('for_user', 'object'),
                               ('created_by', 'object'),
                               ('wf_info_for', 'object'),
                               ('owned_by', 'object'),
                               ('identity', 'object'),
                               ])

    def test_inlined_view(self):
        self.failUnless('main_inlined' in AFS.etype_get('CWUser', 'use_email', 'subject', 'EmailAddress'))
        self.failIf('main_inlined' in AFS.etype_get('CWUser', 'primary_email', 'subject', 'EmailAddress'))
        self.failUnless('main_relations' in AFS.etype_get('CWUser', 'primary_email', 'subject', 'EmailAddress'))

    def test_personne_relations_by_category(self):
        e = self.vreg['etypes'].etype_class('Personne')(self.request())
        self.assertListEquals(rbc(e, 'main', 'attributes'),
                              [('nom', 'subject'),
                               ('prenom', 'subject'),
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
                               ('salary', 'subject'),
                               ('eid', 'subject')
                               ])
        self.assertListEquals(rbc(e, 'muledit', 'attributes'),
                              [('nom', 'subject'),
                               ('eid', 'subject')
                               ])
        self.assertListEquals(rbc(e, 'main', 'metadata'),
                              [('creation_date', 'subject'),
                               ('cwuri', 'subject'),
                               ('modification_date', 'subject'),
                               ('created_by', 'subject'),
                               ('owned_by', 'subject'),
                               ])
        self.assertListEquals(rbc(e, 'main', 'relations'),
                              [('travaille', 'subject'),
                               ('connait', 'object')
                               ])
        self.assertListEquals(rbc(e, 'main', 'hidden'),
                              [('is', 'subject'),
                               ('has_text', 'subject'),
                               ('identity', 'subject'),
                               ('is_instance_of', 'subject'),
                               ('identity', 'object'),
                               ])

    def test_edition_form(self):
        rset = self.execute('CWUser X LIMIT 1')
        form = self.vreg['forms'].select('edition', rset.req, rset=rset,
                                row=0, col=0)
        # should be also selectable by specifying entity
        self.vreg['forms'].select('edition', rset.req,
                         entity=rset.get_entity(0, 0))
        self.failIf(any(f for f in form.fields if f is None))


class FormViewsTC(CubicWebTC):
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
        self.view('inline-edition', rset, row=0, col=0, rtype='in_group',
                  peid=geid, role='object', template=None, i18nctx='',
                  pform=MOCKPFORM).source

    def test_automatic_inline_creation_formview(self):
        geid = self.execute('CWGroup X LIMIT 1')[0][0]
        self.view('inline-creation', None, etype='CWUser', rtype='in_group',
                  peid=geid, template=None, i18nctx='', role='object',
                  pform=MOCKPFORM).source

MOCKPFORM = mock_object(form_previous_values={}, form_valerror=None)

if __name__ == '__main__':
    unittest_main()

