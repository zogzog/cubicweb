# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from logilab.common.testlib import unittest_main, mock_object
from logilab.common import tempattr

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.predicates import is_instance
from cubicweb.web.views import uicfg
from cubicweb.web.views.editforms import DeleteConfFormView
from cubicweb.web.formwidgets import AutoCompletionWidget
from cubicweb.schema import RRQLExpression


AFFK = uicfg.autoform_field_kwargs
AFS = uicfg.autoform_section


def rbc(entity, formtype, section):
    if section in ('attributes', 'metadata', 'hidden'):
        permission = 'update'
    else:
        permission = 'add'
    return [(rschema.type, x)
            for rschema, tschemas, x in AFS.relations_by_section(entity,
                                                                 formtype,
                                                                 section,
                                                                 permission)]

class AutomaticEntityFormTC(CubicWebTC):

    def test_custom_widget(self):
        with self.admin_access.web_request() as req:
            AFFK.tag_subject_of(('CWUser', 'login', '*'),
                                {'widget': AutoCompletionWidget(autocomplete_initfunc='get_logins')})
            form = self.vreg['forms'].select('edition', req, entity=req.user)
            field = form.field_by_name('login', 'subject')
            self.assertIsInstance(field.widget, AutoCompletionWidget)
            AFFK.del_rtag('CWUser', 'login', '*', 'subject')


    def test_cwuser_relations_by_category(self):
        with self.admin_access.web_request() as req:
            e = self.vreg['etypes'].etype_class('CWUser')(req)
            # see custom configuration in views.cwuser
            self.assertEqual(rbc(e, 'main', 'attributes'),
                             [('login', 'subject'),
                              ('upassword', 'subject'),
                              ('firstname', 'subject'),
                              ('surname', 'subject'),
                              ('in_group', 'subject'),
                              ])
            self.assertEqual(rbc(e, 'muledit', 'attributes'),
                                  [('login', 'subject'),
                                   ('upassword', 'subject'),
                                   ('in_group', 'subject'),
                                   ])
            self.assertCountEqual(rbc(e, 'main', 'metadata'),
                                  [('last_login_time', 'subject'),
                                   ('cw_source', 'subject'),
                                   ('creation_date', 'subject'),
                                   ('modification_date', 'subject'),
                                   ('created_by', 'subject'),
                                   ('owned_by', 'subject'),
                                   ('bookmarked_by', 'object'),
                                   ])
            # XXX skip 'tags' relation here and in the hidden category because
            # of some test interdependancy when pytest is launched on whole cw
            # (appears here while expected in hidden
            self.assertCountEqual([x for x in rbc(e, 'main', 'relations')
                                   if x != ('tags', 'object')],
                                  [('connait', 'subject'),
                                   ('custom_workflow', 'subject'),
                                   ('primary_email', 'subject'),
                                   ('checked_by', 'object'),
                                   ])
            self.assertListEqual(rbc(e, 'main', 'inlined'),
                                  [('use_email', 'subject'),
                                   ])
            # owned_by is defined both as subject and object relations on CWUser
            self.assertListEqual(sorted(x for x in rbc(e, 'main', 'hidden')
                                         if x != ('tags', 'object')),
                                  sorted([('for_user', 'object'),
                                          ('created_by', 'object'),
                                          ('wf_info_for', 'object'),
                                          ('owned_by', 'object'),
                                          ]))

    def test_inlined_view(self):
        self.assertIn('main_inlined',
                      AFS.etype_get('CWUser', 'use_email', 'subject', 'EmailAddress'))
        self.assertNotIn('main_inlined',
                         AFS.etype_get('CWUser', 'primary_email', 'subject', 'EmailAddress'))
        self.assertIn('main_relations',
                      AFS.etype_get('CWUser', 'primary_email', 'subject', 'EmailAddress'))

    def test_personne_relations_by_category(self):
        with self.admin_access.web_request() as req:
            e = self.vreg['etypes'].etype_class('Personne')(req)
            self.assertListEqual(rbc(e, 'main', 'attributes'),
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
                                   ('tzdatenaiss', 'subject'),
                                   ('test', 'subject'),
                                   ('description', 'subject'),
                                   ('salary', 'subject'),
                                   ])
            self.assertListEqual(rbc(e, 'muledit', 'attributes'),
                                  [('nom', 'subject'),
                                   ])
            self.assertCountEqual(rbc(e, 'main', 'metadata'),
                                  [('cw_source', 'subject'),
                                   ('creation_date', 'subject'),
                                   ('modification_date', 'subject'),
                                   ('created_by', 'subject'),
                                   ('owned_by', 'subject'),
                                   ])
            self.assertCountEqual(rbc(e, 'main', 'relations'),
                                  [('travaille', 'subject'),
                                   ('manager', 'object'),
                                   ('connait', 'object'),
                                   ])
            self.assertListEqual(rbc(e, 'main', 'hidden'),
                                  [])

    def test_edition_form(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('CWUser X LIMIT 1')
            form = self.vreg['forms'].select('edition', req, rset=rset, row=0, col=0)
            # should be also selectable by specifying entity
            self.vreg['forms'].select('edition', req, entity=rset.get_entity(0, 0))
            self.assertFalse(any(f for f in form.fields if f is None))

    def test_edition_form_with_action(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('CWUser X LIMIT 1')
            form = self.vreg['forms'].select('edition', req, rset=rset, row=0,
                                             col=0, action='my_custom_action')
            self.assertEqual(form.form_action(), 'my_custom_action')

    def test_attribute_add_permissions(self):
        # https://www.cubicweb.org/ticket/4342844
        with self.admin_access.repo_cnx() as cnx:
            self.create_user(cnx, u'toto')
            cnx.commit()
        with self.new_access(u'toto').web_request() as req:
            e = self.vreg['etypes'].etype_class('Personne')(req)
            cform = self.vreg['forms'].select('edition', req, entity=e)
            self.assertIn('sexe',
                          [rschema.type
                           for rschema, _ in cform.editable_attributes()])
            with self.new_access(u'toto').repo_cnx() as cnx:
                person_eid = cnx.create_entity('Personne', nom=u'Robert').eid
                cnx.commit()
            person = req.entity_from_eid(person_eid)
            mform = self.vreg['forms'].select('edition', req, entity=person)
            self.assertNotIn('sexe',
                             [rschema.type
                              for rschema, _ in mform.editable_attributes()])

    def test_editable_attributes(self):
        with self.admin_access.web_request() as req:
            entity = self.vreg['etypes'].etype_class('Personne')(req)
            form = self.vreg['forms'].select('edition', req, entity=entity)
            expected = [
                ('nom', 'subject'),
                ('prenom', 'subject'),
                ('sexe', 'subject'),
                ('promo', 'subject'),
                ('titre', 'subject'),
                ('ass', 'subject'),
                ('web', 'subject'),
                ('tel', 'subject'),
                ('fax', 'subject'),
                ('datenaiss', 'subject'),
                ('tzdatenaiss', 'subject'),
                ('test', 'subject'),
                ('description', 'subject'),
                ('salary', 'subject'),
            ]
            self.assertEqual(
                [(rschema.type, role) for rschema, role in form.editable_attributes()],
                expected)

            # now with display_fields attribute set
            form.display_fields = [('nom', 'subject')]
            expected = [('nom', 'subject')]
            self.assertEqual(
                [(rschema.type, role) for rschema, role in form.editable_attributes()],
                expected)

    def test_inlined_relations(self):
        with self.admin_access.web_request() as req:
            with self.temporary_permissions(EmailAddress={'add': ()}):
                autoform = self.vreg['forms'].select('edition', req, entity=req.user)
                self.assertEqual(list(autoform.inlined_form_views()), [])

    def test_inlined_form_views(self):
        # when some relation has + cardinality, and some already linked entities which are not
        # updatable, a link to optionally add a new sub-entity should be displayed, not a sub-form
        # forcing creation of a sub-entity
        from cubicweb.web.views import autoform
        with self.admin_access.web_request() as req:
            req.create_entity('EmailAddress', address=u'admin@cubicweb.org',
                              reverse_use_email=req.user.eid)
            use_email_schema = self.vreg.schema['CWUser'].rdef('use_email')
            with tempattr(use_email_schema, 'cardinality', '+1'):
                with self.temporary_permissions(EmailAddress={'update': ()}):
                    form = self.vreg['forms'].select('edition', req, entity=req.user)
                    formviews = list(form.inlined_form_views())
                    self.assertEqual(len(formviews), 1, formviews)
                    self.assertIsInstance(formviews[0], autoform.InlineAddNewLinkView)
            # though do not introduce regression on entity creation with 1 cardinality relation
            with tempattr(use_email_schema, 'cardinality', '11'):
                user = self.vreg['etypes'].etype_class('CWUser')(req)
                form = self.vreg['forms'].select('edition', req, entity=user)
                formviews = list(form.inlined_form_views())
                self.assertEqual(len(formviews), 1, formviews)
                self.assertIsInstance(formviews[0], autoform.InlineEntityCreationFormView)

    def test_check_inlined_rdef_permissions(self):
        # try to check permissions when creating an entity ('user' below is a
        # fresh entity without an eid)
        with self.admin_access.web_request() as req:
            ttype = 'EmailAddress'
            rschema = self.schema['use_email']
            rdef =  rschema.rdefs[('CWUser', ttype)]
            tschema = self.schema[ttype]
            role = 'subject'
            with self.temporary_permissions((rdef, {'add': ()})):
                user = self.vreg['etypes'].etype_class('CWUser')(req)
                autoform = self.vreg['forms'].select('edition', req, entity=user)
                self.assertFalse(autoform.check_inlined_rdef_permissions(rschema, role,
                                                                         tschema, ttype))
            # we actually don't care about the actual expression,
            # may_have_permission only checks the presence of such expressions
            expr = RRQLExpression('S use_email O')
            with self.temporary_permissions((rdef, {'add': (expr,)})):
                user = self.vreg['etypes'].etype_class('CWUser')(req)
                autoform = self.vreg['forms'].select('edition', req, entity=user)
                self.assertTrue(autoform.check_inlined_rdef_permissions(rschema, role,
                                                                        tschema, ttype))


class FormViewsTC(CubicWebTC):

    def test_delete_conf_formview(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('CWGroup X')
            self.view('deleteconf', rset, template=None, req=req).source

    def test_delete_conf_formview_composite(self):
        with self.admin_access.cnx() as cnx:
            d1 = cnx.create_entity('Directory', name=u'dtest1')
            d2 = cnx.create_entity('Directory', name=u'dtest2', parent=d1)
            d3 = cnx.create_entity('Directory', name=u'dtest3', parent=d2)
            d4 = cnx.create_entity('Directory', name=u'dtest4', parent=d1)
            for i in range(3):
                cnx.create_entity('Directory', name=u'child%s' % (i,),
                                  parent=d3)
            cnx.commit()

        class DirectoryDeleteView(DeleteConfFormView):
            __select__ = (DeleteConfFormView.__select__ &
                          is_instance('Directory'))
            show_composite = True

        self.vreg['propertyvalues']['navigation.page-size'] = 3
        with self.admin_access.web_request() as req, \
                self.temporary_appobjects(DirectoryDeleteView):
            rset = req.execute('Directory X WHERE X name "dtest1"')
            source = self.view('deleteconf', rset,
                               template=None, req=req).source.decode('utf-8')
            # Show composite object at depth 1
            # Don't display "And more composite entities" since their are equal
            # to page size
            expected = (
                '<li>'
                '<a href="http://testing.fr/cubicweb/directory/%s">dtest1</a>'
                '<ul class="treeview"><li>'
                '<a href="http://testing.fr/cubicweb/directory/%s">dtest4</a>'
                '</li><li class="last">'
                '<a href="http://testing.fr/cubicweb/directory/%s">dtest2</a>'
                '</li></ul></li>') % (d1.eid, d4.eid, d2.eid)
            self.assertIn(expected, source)

            # Page size is reached, show "And more composite entities"
            rset = req.execute('Directory X WHERE X name "dtest3"')
            source = self.view('deleteconf', rset,
                               template=None, req=req).source.decode('utf-8')
            expected = (
                '<li>'
                '<a href="http://testing.fr/cubicweb/directory/%s">dtest3</a>'
                '<ul class="treeview"><li>'
                '<a href="http://testing.fr/cubicweb/directory/%s">child2</a>'
                '</li><li>'
                '<a href="http://testing.fr/cubicweb/directory/%s">child1</a>'
                '</li><li class="last">And more composite entities</li>'
                '</ul></li>') % (
                    d3.eid,
                    req.find('Directory', name='child2').one().eid,
                    req.find('Directory', name='child1').one().eid)
            self.assertIn(expected, source)

            # No composite entities
            rset = req.execute('Directory X WHERE X name "dtest4"')
            source = self.view('deleteconf', rset,
                               template=None, req=req).source.decode('utf-8')
            expected = ('<li><a href="http://testing.fr/cubicweb/directory/%s">'
                        'dtest4</a></li>') % (d4.eid,)
            self.assertIn(expected, source)

    def test_automatic_edition_formview(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('CWUser X')
            self.view('edition', rset, row=0, template=None, req=req).source

    def test_automatic_edition_copyformview(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('CWUser X')
            self.view('copy', rset, row=0, template=None, req=req).source

    def test_automatic_creation_formview(self):
        with self.admin_access.web_request() as req:
            self.view('creation', None, etype='CWUser', template=None, req=req).source

    def test_automatic_muledit_formview(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('CWUser X')
            self.view('muledit', rset, template=None, req=req).source

    def test_automatic_reledit_formview(self):
        with self.admin_access.web_request() as req:
            rset = req.execute('CWUser X')
            self.view('reledit', rset, row=0, rtype='login', template=None, req=req).source

    def test_automatic_inline_edit_formview(self):
        with self.admin_access.web_request() as req:
            geid = req.execute('CWGroup X LIMIT 1')[0][0]
            rset = req.execute('CWUser X LIMIT 1')
            self.view('inline-edition', rset, row=0, col=0, rtype='in_group',
                      peid=geid, role='object', i18nctx='', pform=MOCKPFORM,
                      template=None, req=req).source

    def test_automatic_inline_creation_formview(self):
        with self.admin_access.web_request() as req:
            geid = req.execute('CWGroup X LIMIT 1')[0][0]
            self.view('inline-creation', None, etype='CWUser', rtype='in_group',
                      peid=geid, petype='CWGroup', i18nctx='', role='object', pform=MOCKPFORM,
                      template=None, req=req)

MOCKPFORM = mock_object(form_previous_values={}, form_valerror=None)

if __name__ == '__main__':
    unittest_main()
