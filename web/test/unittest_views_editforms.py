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
from logilab.common.testlib import unittest_main, mock_object
from logilab.common.compat import any

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.web import uicfg
from cubicweb.web.formwidgets import AutoCompletionWidget

AFFK = uicfg.autoform_field_kwargs
AFS = uicfg.autoform_section

def rbc(entity, formtype, section):
    if section in ('attributes', 'metadata', 'hidden'):
        permission = 'update'
    else:
        permission = 'add'
    return [(rschema.type, x) for rschema, tschemas, x in AFS.relations_by_section(entity, formtype, section, permission)]

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
        e = self.vreg['etypes'].etype_class('CWUser')(self.request())
        # see custom configuration in views.cwuser
        self.assertEquals(rbc(e, 'main', 'attributes'),
                          [('login', 'subject'),
                           ('upassword', 'subject'),
                           ('firstname', 'subject'),
                           ('surname', 'subject'),
                           ('in_group', 'subject'),
                           ])
        self.assertListEquals(rbc(e, 'muledit', 'attributes'),
                              [('login', 'subject'),
                               ('upassword', 'subject'),
                               ('in_group', 'subject'),
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
        # XXX skip 'tags' relation here and in the hidden category because
        # of some test interdependancy when pytest is launched on whole cw
        # (appears here while expected in hidden
        self.assertListEquals([x for x in rbc(e, 'main', 'relations')
                               if x != ('tags', 'object')],
                              [('primary_email', 'subject'),
                               ('custom_workflow', 'subject'),
                               ('connait', 'subject'),
                               ('checked_by', 'object'),
                               ])
        self.assertListEquals(rbc(e, 'main', 'inlined'),
                              [('use_email', 'subject'),
                               ])
        # owned_by is defined both as subject and object relations on CWUser
        self.assertListEquals(sorted(x for x in rbc(e, 'main', 'hidden')
                                     if x != ('tags', 'object')),
                              sorted([('for_user', 'object'),
                                      ('created_by', 'object'),
                                      ('wf_info_for', 'object'),
                                      ('owned_by', 'object'),
                                      ]))

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
                               ])
        self.assertListEquals(rbc(e, 'muledit', 'attributes'),
                              [('nom', 'subject'),
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
                              [])

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
                  peid=geid, role='object', i18nctx='', pform=MOCKPFORM,
                  template=None).source

    def test_automatic_inline_creation_formview(self):
        geid = self.execute('CWGroup X LIMIT 1')[0][0]
        self.view('inline-creation', None, etype='CWUser', rtype='in_group',
                  peid=geid, petype='CWGroup', i18nctx='', role='object', pform=MOCKPFORM,
                  template=None)

MOCKPFORM = mock_object(form_previous_values={}, form_valerror=None)

if __name__ == '__main__':
    unittest_main()

