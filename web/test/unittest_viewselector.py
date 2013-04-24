# -*- coding: utf-8 -*-
# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""XXX rename, split, reorganize this"""

from logilab.common.testlib import unittest_main

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb import CW_SOFTWARE_ROOT as BASE, Binary, UnknownProperty
from cubicweb.predicates import (match_user_groups, is_instance,
                                 specified_etype_implements, rql_condition)
from cubicweb.web import NoSelectableObject
from cubicweb.web.action import Action
from cubicweb.web.views import (
    primary, baseviews, tableview, editforms, calendar, management, embedding,
    actions, startup, cwuser, schema, xbel, vcard, owl, treeview, idownloadable,
    wdoc, debug, cwuser, cwproperties, cwsources, workflow, xmlrss, rdf,
    csvexport, json, undohistory)

from cubes.folder import views as folderviews

USERACTIONS = [actions.UserPreferencesAction,
               actions.UserInfoAction,
               actions.LogoutAction]
SITEACTIONS = [actions.ManageAction]
FOOTERACTIONS = [wdoc.HelpAction,
                 wdoc.AboutAction,
                 actions.PoweredByAction]
MANAGEACTIONS = [actions.SiteConfigurationAction,
                 schema.ViewSchemaAction,
                 cwuser.ManageUsersAction,
                 cwsources.ManageSourcesAction,
                 debug.SiteInfoAction]

if hasattr(rdf, 'RDFView'): # not available if rdflib not installed
    RDFVIEWS = [('rdf', rdf.RDFView)]
else:
    RDFVIEWS = []

class ViewSelectorTC(CubicWebTC):

    def setup_database(self):
        req = self.request()
        req.create_entity('BlogEntry', title=u"une news !", content=u"cubicweb c'est beau")
        req.create_entity('Bookmark', title=u"un signet !", path=u"view?vid=index")
        req.create_entity('EmailAddress', address=u"devel@logilab.fr", alias=u'devel')
        req.create_entity('Tag', name=u'x')

class VRegistryTC(ViewSelectorTC):
    """test the view selector"""

    def _test_registered(self, registry, content):
        try:
            expected = getattr(self, 'all_%s' % registry)
        except AttributeError:
            return
        if registry == 'hooks':
            self.assertEqual(len(content), expected, content)
            return
        try:
            self.assertSetEqual(list(content), expected)
        except Exception:
            print registry, sorted(expected), sorted(content)
            print 'no more', [v for v in expected if not v in content]
            print 'missing', [v for v in content if not v in expected]
            raise

    def setUp(self):
        super(VRegistryTC, self).setUp()
        assert self.vreg['views']['propertiesform']

    def test_possible_views_none_rset(self):
        req = self.request()
        self.assertListEqual(self.pviews(req, None),
                             [('cw.sources-management', cwsources.CWSourcesManagementView),
                              ('cw.users-and-groups-management', cwuser.UsersAndGroupsManagementView),
                              ('gc', debug.GCView),
                              ('index', startup.IndexView),
                              ('info', debug.ProcessInformationView),
                              ('manage', startup.ManageView),
                              ('owl', owl.OWLView),
                              ('propertiesform', cwproperties.CWPropertiesForm),
                              ('registry', debug.RegistryView),
                              ('schema', schema.SchemaView),
                              ('siteinfo', debug.SiteInfoView),
                              ('systempropertiesform', cwproperties.SystemCWPropertiesForm),
                              ('tree', folderviews.FolderTreeView),
                              ('undohistory', undohistory.UndoHistoryView),
                              ])

    def test_possible_views_noresult(self):
        req = self.request()
        rset = req.execute('Any X WHERE X eid 999999')
        self.assertListEqual([('jsonexport', json.JsonRsetView)],
                             self.pviews(req, rset))

    def test_possible_views_one_egroup(self):
        req = self.request()
        rset = req.execute('CWGroup X WHERE X name "managers"')
        self.assertListEqual(self.pviews(req, rset),
                             [('csvexport', csvexport.CSVRsetView),
                              ('ecsvexport', csvexport.CSVEntityView),
                              ('ejsonexport', json.JsonEntityView),
                              ('filetree', treeview.FileTreeView),
                              ('jsonexport', json.JsonRsetView),
                              ('list', baseviews.ListView),
                              ('oneline', baseviews.OneLineView),
                              ('owlabox', owl.OWLABOXView),
                              ('primary', cwuser.CWGroupPrimaryView)] + RDFVIEWS + [
                              ('rsetxml', xmlrss.XMLRsetView),
                              ('rss', xmlrss.RSSView),
                              ('sameetypelist', baseviews.SameETypeListView),
                              ('security', management.SecurityManagementView),
                              ('table', tableview.RsetTableView),
                              ('text', baseviews.TextView),
                              ('treeview', treeview.TreeView),
                              ('xbel', xbel.XbelView),
                              ('xml', xmlrss.XMLView),
                              ])

    def test_possible_views_multiple_egroups(self):
        req = self.request()
        rset = req.execute('CWGroup X')
        self.assertListEqual(self.pviews(req, rset),
                             [('csvexport', csvexport.CSVRsetView),
                              ('ecsvexport', csvexport.CSVEntityView),
                              ('ejsonexport', json.JsonEntityView),
                              ('filetree', treeview.FileTreeView),
                              ('jsonexport', json.JsonRsetView),
                              ('list', baseviews.ListView),
                              ('oneline', baseviews.OneLineView),
                              ('owlabox', owl.OWLABOXView),
                              ('primary', cwuser.CWGroupPrimaryView)] + RDFVIEWS + [
                              ('rsetxml', xmlrss.XMLRsetView),
                              ('rss', xmlrss.RSSView),
                              ('sameetypelist', baseviews.SameETypeListView),
                              ('security', management.SecurityManagementView),
                              ('table', tableview.RsetTableView),
                              ('text', baseviews.TextView),
                              ('treeview', treeview.TreeView),
                              ('xbel', xbel.XbelView),
                              ('xml', xmlrss.XMLView),
                              ])

    def test_propertiesform_admin(self):
        assert self.vreg['views']['propertiesform']
        req1 = self.request()
        req2 = self.request()
        rset1 = req1.execute('CWUser X WHERE X login "admin"')
        rset2 = req2.execute('CWUser X WHERE X login "anon"')
        self.assertTrue(self.vreg['views'].select('propertiesform', req1, rset=None))
        self.assertTrue(self.vreg['views'].select('propertiesform', req1, rset=rset1))
        self.assertTrue(self.vreg['views'].select('propertiesform', req2, rset=rset2))

    def test_propertiesform_anon(self):
        self.login('anon')
        req1 = self.request()
        req2 = self.request()
        rset1 = req1.execute('CWUser X WHERE X login "admin"')
        rset2 = req2.execute('CWUser X WHERE X login "anon"')
        self.assertRaises(NoSelectableObject, self.vreg['views'].select, 'propertiesform', req1, rset=None)
        self.assertRaises(NoSelectableObject, self.vreg['views'].select, 'propertiesform', req1, rset=rset1)
        self.assertRaises(NoSelectableObject, self.vreg['views'].select, 'propertiesform', req1, rset=rset2)

    def test_propertiesform_jdoe(self):
        self.create_user(self.request(), 'jdoe')
        self.login('jdoe')
        req1 = self.request()
        req2 = self.request()
        rset1 = req1.execute('CWUser X WHERE X login "admin"')
        rset2 = req2.execute('CWUser X WHERE X login "jdoe"')
        self.assertTrue(self.vreg['views'].select('propertiesform', req1, rset=None))
        self.assertRaises(NoSelectableObject, self.vreg['views'].select, 'propertiesform', req1, rset=rset1)
        self.assertTrue(self.vreg['views'].select('propertiesform', req2, rset=rset2))

    def test_possible_views_multiple_different_types(self):
        req = self.request()
        rset = req.execute('Any X')
        self.assertListEqual(self.pviews(req, rset),
                             [('csvexport', csvexport.CSVRsetView),
                              ('ecsvexport', csvexport.CSVEntityView),
                              ('ejsonexport', json.JsonEntityView),
                              ('filetree', treeview.FileTreeView),
                              ('jsonexport', json.JsonRsetView),
                              ('list', baseviews.ListView),
                              ('oneline', baseviews.OneLineView),
                              ('owlabox', owl.OWLABOXView),
                              ('primary', primary.PrimaryView),] + RDFVIEWS + [
                              ('rsetxml', xmlrss.XMLRsetView),
                              ('rss', xmlrss.RSSView),
                              ('security', management.SecurityManagementView),
                              ('table', tableview.RsetTableView),
                              ('text', baseviews.TextView),
                              ('treeview', treeview.TreeView),
                              ('xbel', xbel.XbelView),
                              ('xml', xmlrss.XMLView),
                              ])

    def test_possible_views_any_rset(self):
        req = self.request()
        rset = req.execute('Any N, X WHERE X in_group Y, Y name N')
        self.assertListEqual(self.pviews(req, rset),
                             [('csvexport', csvexport.CSVRsetView),
                              ('jsonexport', json.JsonRsetView),
                              ('rsetxml', xmlrss.XMLRsetView),
                              ('table', tableview.RsetTableView),
                              ])

    def test_possible_views_multiple_eusers(self):
        req = self.request()
        rset = req.execute('CWUser X')
        self.assertListEqual(self.pviews(req, rset),
                             [('csvexport', csvexport.CSVRsetView),
                              ('ecsvexport', csvexport.CSVEntityView),
                              ('ejsonexport', json.JsonEntityView),
                              ('filetree', treeview.FileTreeView),
                              ('foaf', cwuser.FoafView),
                              ('jsonexport', json.JsonRsetView),
                              ('list', baseviews.ListView),
                              ('oneline', baseviews.OneLineView),
                              ('owlabox', owl.OWLABOXView),
                              ('primary', primary.PrimaryView)] + RDFVIEWS + [
                              ('rsetxml', xmlrss.XMLRsetView),
                              ('rss', xmlrss.RSSView),
                              ('sameetypelist', baseviews.SameETypeListView),
                              ('security', management.SecurityManagementView),
                              ('table', tableview.RsetTableView),
                              ('text', baseviews.TextView),
                              ('treeview', treeview.TreeView),
                              ('vcard', vcard.VCardCWUserView),
                              ('xbel', xbel.XbelView),
                              ('xml', xmlrss.XMLView),
                              ])

    def test_possible_actions_none_rset(self):
        req = self.request()
        self.assertDictEqual(self.pactionsdict(req, None, skipcategories=()),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,
                              'manage': MANAGEACTIONS,
                              'footer': FOOTERACTIONS,

                              })
    def test_possible_actions_no_entity(self):
        req = self.request()
        rset = req.execute('Any X WHERE X eid 999999')
        self.assertDictEqual(self.pactionsdict(req, rset, skipcategories=()),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,
                              'manage': MANAGEACTIONS,
                              'footer': FOOTERACTIONS,
                              })

    def test_possible_actions_same_type_entities(self):
        req = self.request()
        rset = req.execute('CWGroup X')
        self.assertDictEqual(self.pactionsdict(req, rset, skipcategories=()),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,
                              'manage': MANAGEACTIONS,
                              'footer': FOOTERACTIONS,
                              'mainactions': [actions.MultipleEditAction],
                              'moreactions': [actions.DeleteAction,
                                              actions.AddNewAction],
                              })

    def test_possible_actions_different_types_entities(self):
        req = self.request()
        rset = req.execute('Any X')
        self.assertDictEqual(self.pactionsdict(req, rset, skipcategories=()),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,
                              'manage': MANAGEACTIONS,
                              'footer': FOOTERACTIONS,
                              'moreactions': [actions.DeleteAction],
                              })

    def test_possible_actions_final_entities(self):
        req = self.request()
        rset = req.execute('Any N, X WHERE X in_group Y, Y name N')
        self.assertDictEqual(self.pactionsdict(req, rset, skipcategories=()),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,
                              'manage': MANAGEACTIONS,
                              'footer': FOOTERACTIONS,
                              })

    def test_possible_actions_eetype_cwuser_entity(self):
        req = self.request()
        rset = req.execute('CWEType X WHERE X name "CWUser"')
        self.assertDictEqual(self.pactionsdict(req, rset, skipcategories=()),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,
                              'manage': MANAGEACTIONS,
                              'footer': FOOTERACTIONS,
                              'mainactions': [actions.ModifyAction,
                                              actions.ViewSameCWEType],
                              'moreactions': [actions.ManagePermissionsAction,
                                              actions.AddRelatedActions,
                                              actions.DeleteAction,
                                              actions.CopyAction,
                                              ],
                              })


    def test_select_creation_form(self):
        rset = None
        req = self.request()
        # creation form
        req.form['etype'] = 'CWGroup'
        self.assertIsInstance(self.vreg['views'].select('creation', req, rset=rset),
                              editforms.CreationFormView)
        del req.form['etype']
        # custom creation form
        class CWUserCreationForm(editforms.CreationFormView):
            __select__ = specified_etype_implements('CWUser')
        self.vreg._loadedmods[__name__] = {}
        self.vreg.register(CWUserCreationForm)
        req.form['etype'] = 'CWUser'
        self.assertIsInstance(self.vreg['views'].select('creation', req, rset=rset),
                              CWUserCreationForm)

    def test_select_view(self):
        # no entity
        rset = None
        req = self.request()
        self.assertIsInstance(self.vreg['views'].select('index', req, rset=rset),
                             startup.IndexView)
        self.assertRaises(NoSelectableObject,
                             self.vreg['views'].select, 'primary', req, rset=rset)
        self.assertRaises(NoSelectableObject,
                             self.vreg['views'].select, 'table', req, rset=rset)

        # no entity
        req = self.request()
        rset = req.execute('Any X WHERE X eid 999999')
        self.assertRaises(NoSelectableObject,
                              self.vreg['views'].select, 'index', req, rset=rset)
        self.assertRaises(NoSelectableObject,
                              self.vreg['views'].select, 'creation', req, rset=rset)
        self.assertRaises(NoSelectableObject,
                              self.vreg['views'].select, 'primary', req, rset=rset)
        self.assertRaises(NoSelectableObject,
                             self.vreg['views'].select, 'table', req, rset=rset)
        # one entity
        req = self.request()
        rset = req.execute('CWGroup X WHERE X name "managers"')
        self.assertIsInstance(self.vreg['views'].select('primary', req, rset=rset),
                             primary.PrimaryView)
        self.assertIsInstance(self.vreg['views'].select('list', req, rset=rset),
                             baseviews.ListView)
        self.assertIsInstance(self.vreg['views'].select('edition', req, rset=rset),
                             editforms.EditionFormView)
        self.assertIsInstance(self.vreg['views'].select('table', req, rset=rset),
                             tableview.RsetTableView)
        self.assertRaises(NoSelectableObject,
                              self.vreg['views'].select, 'creation', req, rset=rset)
        self.assertRaises(NoSelectableObject,
                              self.vreg['views'].select, 'index', req, rset=rset)
        # list of entities of the same type
        req = self.request()
        rset = req.execute('CWGroup X')
        self.assertIsInstance(self.vreg['views'].select('primary', req, rset=rset),
                             primary.PrimaryView)
        self.assertIsInstance(self.vreg['views'].select('list', req, rset=rset),
                             baseviews.ListView)
        self.assertIsInstance(self.vreg['views'].select('table', req, rset=rset),
                             tableview.RsetTableView)
        self.assertRaises(NoSelectableObject,
                              self.vreg['views'].select, 'creation', req, rset=rset)
        # list of entities of different types
        req = self.request()
        rset = req.execute('Any X')
        self.assertIsInstance(self.vreg['views'].select('primary', req, rset=rset),
                                  primary.PrimaryView)
        self.assertIsInstance(self.vreg['views'].select('list', req, rset=rset),
                                  baseviews.ListView)
        self.assertIsInstance(self.vreg['views'].select('table', req, rset=rset),
                                  tableview.RsetTableView)
        self.assertRaises(NoSelectableObject,
                             self.vreg['views'].select, 'creation', req, rset=rset)
        self.assertRaises(NoSelectableObject,
                              self.vreg['views'].select, 'index', req, rset=rset)
        # whatever
        req = self.request()
        rset = req.execute('Any N, X WHERE X in_group Y, Y name N')
        self.assertIsInstance(self.vreg['views'].select('table', req, rset=rset),
                                  tableview.RsetTableView)
        self.assertRaises(NoSelectableObject,
                              self.vreg['views'].select, 'index', req, rset=rset)
        self.assertRaises(NoSelectableObject,
                              self.vreg['views'].select, 'creation', req, rset=rset)
        self.assertRaises(NoSelectableObject,
                             self.vreg['views'].select, 'primary', req, rset=rset)
        self.assertRaises(NoSelectableObject,
                             self.vreg['views'].select, 'list', req, rset=rset)
        self.assertRaises(NoSelectableObject,
                             self.vreg['views'].select, 'edition', req, rset=rset)
        # mixed query
        req = self.request()
        rset = req.execute('Any U,G WHERE U is CWUser, G is CWGroup')
        self.assertRaises(NoSelectableObject,
                              self.vreg['views'].select, 'edition', req, rset=rset)
        self.assertRaises(NoSelectableObject,
                              self.vreg['views'].select, 'creation', req, rset=rset)
        self.assertIsInstance(self.vreg['views'].select('table', req, rset=rset),
                              tableview.RsetTableView)

    def test_interface_selector(self):
        image = self.request().create_entity('File', data_name=u'bim.png', data=Binary('bim'))
        # image primary view priority
        req = self.request()
        rset = req.execute('File X WHERE X data_name "bim.png"')
        self.assertIsInstance(self.vreg['views'].select('primary', req, rset=rset),
                              idownloadable.IDownloadablePrimaryView)


    def test_score_entity_selector(self):
        image = self.request().create_entity('File', data_name=u'bim.png', data=Binary('bim'))
        # image/ehtml primary view priority
        req = self.request()
        rset = req.execute('File X WHERE X data_name "bim.png"')
        self.assertIsInstance(self.vreg['views'].select('image', req, rset=rset),
                              idownloadable.ImageView)
        self.assertRaises(NoSelectableObject, self.vreg['views'].select, 'ehtml', req, rset=rset)

        fileobj = self.request().create_entity('File', data_name=u'bim.html', data=Binary('<html>bam</html'))
        # image/ehtml primary view priority
        req = self.request()
        rset = req.execute('File X WHERE X data_name "bim.html"')
        self.assertIsInstance(self.vreg['views'].select('ehtml', req, rset=rset),
                              idownloadable.EHTMLView)
        self.assertRaises(NoSelectableObject, self.vreg['views'].select, 'image', req, rset=rset)

        fileobj = self.request().create_entity('File', data_name=u'bim.txt', data=Binary('boum'))
        # image/ehtml primary view priority
        req = self.request()
        rset = req.execute('File X WHERE X data_name "bim.txt"')
        self.assertRaises(NoSelectableObject, self.vreg['views'].select, 'image', req, rset=rset)
        self.assertRaises(NoSelectableObject, self.vreg['views'].select, 'ehtml', req, rset=rset)


    def _test_view(self, vid, rql, args):
        if rql is None:
            rset = None
            req = self.request()
        else:
            req = self.request()
            rset = req.execute(rql)
        try:
            obj = self.vreg['views'].select(vid, req, rset=rset, **args)
            return obj.render(**args)
        except Exception:
            print vid, rset, args
            raise

    def test_form(self):
        for vid, rql, args in (
            #('creation', 'Any X WHERE X eid 999999', {}),
            ('edition', 'CWGroup X WHERE X name "managers"', {}),
            ('copy', 'CWGroup X WHERE X name "managers"', {}),
            ('muledit', 'CWGroup X', {}),
            #('muledit', 'Any X', {}),
            ):
            self._test_view(vid, rql, args)


    def test_properties(self):
        self.assertEqual(sorted(k for k in self.vreg['propertydefs'].iterkeys()
                                if k.startswith('ctxcomponents.edit_box')),
                         ['ctxcomponents.edit_box.context',
                          'ctxcomponents.edit_box.order',
                          'ctxcomponents.edit_box.visible'])
        self.assertEqual([k for k in self.vreg['propertyvalues'].iterkeys()
                          if not k.startswith('system.version')],
                         [])
        self.assertEqual(self.vreg.property_value('ctxcomponents.edit_box.visible'), True)
        self.assertEqual(self.vreg.property_value('ctxcomponents.edit_box.order'), 2)
        self.assertEqual(self.vreg.property_value('ctxcomponents.possible_views_box.visible'), False)
        self.assertEqual(self.vreg.property_value('ctxcomponents.possible_views_box.order'), 10)
        self.assertRaises(UnknownProperty, self.vreg.property_value, 'ctxcomponents.actions_box')



class CWETypeRQLAction(Action):
    __regid__ = 'testaction'
    __select__ = is_instance('CWEType') & rql_condition('X name "CWEType"')
    title = 'bla'

class RQLActionTC(ViewSelectorTC):

    def setUp(self):
        super(RQLActionTC, self).setUp()
        self.vreg._loadedmods[__name__] = {}
        self.vreg.register(CWETypeRQLAction)
        actionsreg = self.vreg['actions']
        actionsreg['testaction'][0].__registered__(actionsreg)

    def tearDown(self):
        super(RQLActionTC, self).tearDown()
        del self.vreg['actions']['testaction']

    def test(self):
        req = self.request()
        rset = req.execute('CWEType X WHERE X name "CWEType"')
        self.assertDictEqual(self.pactionsdict(req, rset, skipcategories=()),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,
                              'footer': FOOTERACTIONS,
                              'manage': MANAGEACTIONS,
                              'mainactions': [actions.ModifyAction, actions.ViewSameCWEType],
                              'moreactions': [actions.ManagePermissionsAction,
                                              actions.AddRelatedActions,
                                              actions.DeleteAction,
                                              actions.CopyAction,
                                              CWETypeRQLAction,
                                              ],
                              })
        req = self.request()
        rset = req.execute('CWEType X WHERE X name "CWRType"')
        self.assertDictEqual(self.pactionsdict(req, rset, skipcategories=()),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,
                              'footer': FOOTERACTIONS,
                              'manage': MANAGEACTIONS,
                              'mainactions': [actions.ModifyAction, actions.ViewSameCWEType],
                              'moreactions': [actions.ManagePermissionsAction,
                                              actions.AddRelatedActions,
                                              actions.DeleteAction,
                                              actions.CopyAction,]
                              })



if __name__ == '__main__':
    unittest_main()
