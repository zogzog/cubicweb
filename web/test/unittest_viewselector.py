# -*- coding: iso-8859-1 -*-
"""XXX rename, split, reorganize this
"""
from __future__ import with_statement

from logilab.common.testlib import unittest_main

from cubicweb.devtools.apptest import EnvBasedTC
from cubicweb import CW_SOFTWARE_ROOT as BASE, Binary
from cubicweb.selectors import (match_user_groups, implements,
                                specified_etype_implements, rql_condition,
                                traced_selection)
from cubicweb.web import NoSelectableObject
from cubicweb.web.action import Action
from cubicweb.web.views import (baseviews, tableview, baseforms, calendar,
                                management, embedding, actions, startup,
                                euser, schemaentities, xbel, vcard, owl,
                                treeview, idownloadable, wdoc, debug, eproperties)

USERACTIONS = [('myprefs', actions.UserPreferencesAction),
               ('myinfos', actions.UserInfoAction),
               ('logout', actions.LogoutAction)]
SITEACTIONS = [('siteconfig', actions.SiteConfigurationAction),
               ('manage', actions.ManageAction),
               ('schema', actions.ViewSchemaAction)]


class ViewSelectorTC(EnvBasedTC):

    def setup_database(self):
        self.add_entity('BlogEntry', title=u"une news !", content=u"cubicweb c'est beau")
        self.add_entity('Bookmark', title=u"un signet !", path=u"view?vid=index")
        self.add_entity('EmailAddress', address=u"devel@logilab.fr", alias=u'devel')
        self.add_entity('Tag', name=u'x')

    def pactions(self, req, rset):
        resdict = self.vreg.possible_actions(req, rset)
        for cat, actions in resdict.items():
            resdict[cat] = [(a.id, a.__class__) for a in actions]
        return resdict


class VRegistryTC(ViewSelectorTC):
    """test the view selector"""

    def _test_registered(self, registry, content):
        try:
            expected = getattr(self, 'all_%s' % registry)
        except AttributeError:
            return
        if registry == 'hooks':
            self.assertEquals(len(content), expected, content)
            return
        try:
            self.assertSetEqual(content.keys(), expected)
        except:
            print registry, sorted(expected), sorted(content.keys())
            print 'no more', [v for v in expected if not v in content.keys()]
            print 'missing', [v for v in content.keys() if not v in expected]
            raise


    def test_possible_views_none_rset(self):
        req = self.request()
        self.assertListEqual(self.pviews(req, None),
                             [('changelog', wdoc.ChangeLogView),
                              ('debug', debug.DebugView),
                              ('epropertiesform', eproperties.EPropertiesForm),
                              ('index', startup.IndexView),
                              ('info', management.ProcessInformationView),
                              ('manage', startup.ManageView),
                              ('owl', owl.OWLView),
                              ('schema', startup.SchemaView),
                              ('systemepropertiesform', eproperties.SystemEPropertiesForm)])

    def test_possible_views_noresult(self):
        rset, req = self.env.get_rset_and_req('Any X WHERE X eid 999999')
        self.assertListEqual(self.pviews(req, rset),
                             [])

    def test_possible_views_one_egroup(self):
        rset, req = self.env.get_rset_and_req('CWGroup X WHERE X name "managers"')
        self.assertListEqual(self.pviews(req, rset),
                             [('csvexport', baseviews.CSVRsetView),
                              ('ecsvexport', baseviews.CSVEntityView),
                              ('editable-table', tableview.EditableTableView),
                              ('filetree', treeview.FileTreeView),
                              ('list', baseviews.ListView),
                              ('oneline', baseviews.OneLineView),
                              ('owlabox', owl.OWLABOXView),
                              ('primary', baseviews.PrimaryView),
                              ('rsetxml', baseviews.XMLRsetView),
                              ('rss', baseviews.RssView),
                              ('secondary', baseviews.SecondaryView),
                              ('security', management.SecurityManagementView),
                              ('table', tableview.TableView),
                              ('text', baseviews.TextView),
                              ('treeview', treeview.TreeView),
                              ('xbel', xbel.XbelView),
                              ('xml', baseviews.XmlView),
                              ])

    def test_possible_views_multiple_egroups(self):
        rset, req = self.env.get_rset_and_req('CWGroup X')
        self.assertListEqual(self.pviews(req, rset),
                             [('csvexport', baseviews.CSVRsetView),
                              ('ecsvexport', baseviews.CSVEntityView),
                              ('editable-table', tableview.EditableTableView),
                              ('filetree', treeview.FileTreeView),
                              ('list', baseviews.ListView),
                              ('oneline', baseviews.OneLineView),
                              ('owlabox', owl.OWLABOXView),
                              ('primary', baseviews.PrimaryView),
                              ('rsetxml', baseviews.XMLRsetView),
                              ('rss', baseviews.RssView),
                              ('secondary', baseviews.SecondaryView),
                              ('security', management.SecurityManagementView),
                              ('table', tableview.TableView),
                              ('text', baseviews.TextView),
                              ('treeview', treeview.TreeView),
                              ('xbel', xbel.XbelView),
                              ('xml', baseviews.XmlView),
                              ])

    def test_possible_views_multiple_different_types(self):
        rset, req = self.env.get_rset_and_req('Any X')
        self.assertListEqual(self.pviews(req, rset),
                             [('csvexport', baseviews.CSVRsetView),
                              ('ecsvexport', baseviews.CSVEntityView),
                              ('editable-table', tableview.EditableTableView),
                              ('filetree', treeview.FileTreeView),
                              ('list', baseviews.ListView),
                              ('oneline', baseviews.OneLineView),
                              ('owlabox', owl.OWLABOXView),
                              ('primary', baseviews.PrimaryView),
                              ('rsetxml', baseviews.XMLRsetView),
                              ('rss', baseviews.RssView),
                              ('secondary', baseviews.SecondaryView),
                              ('security', management.SecurityManagementView),
                              ('table', tableview.TableView),
                              ('text', baseviews.TextView),
                              ('treeview', treeview.TreeView),
                              ('xbel', xbel.XbelView),
                              ('xml', baseviews.XmlView),
                              ])

    def test_possible_views_any_rset(self):
        rset, req = self.env.get_rset_and_req('Any N, X WHERE X in_group Y, Y name N')
        self.assertListEqual(self.pviews(req, rset),
                             [('csvexport', baseviews.CSVRsetView),
                              ('editable-table', tableview.EditableTableView),
                              ('rsetxml', baseviews.XMLRsetView),
                              ('table', tableview.TableView),
                              ])

    def test_possible_views_multiple_eusers(self):
        rset, req = self.env.get_rset_and_req('CWUser X')
        self.assertListEqual(self.pviews(req, rset),
                             [('csvexport', baseviews.CSVRsetView),
                              ('ecsvexport', baseviews.CSVEntityView),
                              ('editable-table', tableview.EditableTableView),
                              ('filetree', treeview.FileTreeView),
                              ('foaf', euser.FoafView),
                              ('list', baseviews.ListView),
                              ('oneline', baseviews.OneLineView),
                              ('owlabox', owl.OWLABOXView),
                              ('primary', euser.CWUserPrimaryView),
                              ('rsetxml', baseviews.XMLRsetView),
                              ('rss', baseviews.RssView),
                              ('secondary', baseviews.SecondaryView),
                              ('security', management.SecurityManagementView),
                              ('table', tableview.TableView),
                              ('text', baseviews.TextView),
                              ('treeview', treeview.TreeView),
                              ('vcard', vcard.VCardCWUserView),
                              ('xbel', xbel.XbelView),
                              ('xml', baseviews.XmlView),
                              ])

    def test_possible_actions_none_rset(self):
        req = self.request()
        self.assertDictEqual(self.pactions(req, None),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,

                              })
    def test_possible_actions_no_entity(self):
        rset, req = self.env.get_rset_and_req('Any X WHERE X eid 999999')
        self.assertDictEqual(self.pactions(req, rset),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,
                              })

    def test_possible_actions_same_type_entities(self):
        rset, req = self.env.get_rset_and_req('CWGroup X')
        self.assertDictEqual(self.pactions(req, rset),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,
                              'mainactions': [('muledit', actions.MultipleEditAction)],
                              'moreactions': [('delete', actions.DeleteAction),
                                              ('addentity', actions.AddNewAction)],
                              })

    def test_possible_actions_different_types_entities(self):
        rset, req = self.env.get_rset_and_req('Any X')
        self.assertDictEqual(self.pactions(req, rset),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,
                              'moreactions': [('delete', actions.DeleteAction)],
                              })

    def test_possible_actions_final_entities(self):
        rset, req = self.env.get_rset_and_req('Any N, X WHERE X in_group Y, Y name N')
        self.assertDictEqual(self.pactions(req, rset),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS})

    def test_possible_actions_eetype_euser_entity(self):
        rset, req = self.env.get_rset_and_req('CWEType X WHERE X name "CWUser"')
        self.assertDictEqual(self.pactions(req, rset),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,
                              'mainactions': [('edit', actions.ModifyAction),
                                              ('workflow', schemaentities.ViewWorkflowAction),],
                              'moreactions': [('delete', actions.DeleteAction),
                                              ('copy', actions.CopyAction),
                                              ('managepermission', actions.ManagePermissionsAction)],
                              })


    def test_select_creation_form(self):
        rset = None
        req = self.request()
        # creation form
        req.form['etype'] = 'CWGroup'
        self.assertIsInstance(self.vreg.select_view('creation', req, rset),
                                  baseforms.CreationForm)
        del req.form['etype']
        # custom creation form
        class CWUserCreationForm(baseforms.CreationForm):
            __select__ = specified_etype_implements('CWUser')
        self.vreg.register_vobject_class(CWUserCreationForm)
        req.form['etype'] = 'CWUser'
        self.assertIsInstance(self.vreg.select_view('creation', req, rset),
                              CWUserCreationForm)

    def test_select_view(self):
        # no entity
        rset = None
        req = self.request()
        self.assertIsInstance(self.vreg.select_view('index', req, rset),
                             startup.IndexView)
        self.failUnlessRaises(NoSelectableObject,
                             self.vreg.select_view, 'primary', req, rset)
        self.failUnlessRaises(NoSelectableObject,
                             self.vreg.select_view, 'table', req, rset)

        # no entity
        rset, req = self.env.get_rset_and_req('Any X WHERE X eid 999999')
        self.failUnlessRaises(NoSelectableObject,
                              self.vreg.select_view, 'index', req, rset)
        self.failUnlessRaises(NoSelectableObject,
                              self.vreg.select_view, 'creation', req, rset)
        self.failUnlessRaises(NoSelectableObject,
                              self.vreg.select_view, 'primary', req, rset)
        self.failUnlessRaises(NoSelectableObject,
                             self.vreg.select_view, 'table', req, rset)
        # one entity
        rset, req = self.env.get_rset_and_req('CWGroup X WHERE X name "managers"')
        self.assertIsInstance(self.vreg.select_view('primary', req, rset),
                             baseviews.PrimaryView)
        self.assertIsInstance(self.vreg.select_view('list', req, rset),
                             baseviews.ListView)
        self.assertIsInstance(self.vreg.select_view('edition', req, rset),
                             baseforms.EditionForm)
        self.assertIsInstance(self.vreg.select_view('table', req, rset),
                             tableview.TableView)
        self.failUnlessRaises(NoSelectableObject,
                              self.vreg.select_view, 'creation', req, rset)
        self.failUnlessRaises(NoSelectableObject,
                              self.vreg.select_view, 'index', req, rset)
        # list of entities of the same type
        rset, req = self.env.get_rset_and_req('CWGroup X')
        self.assertIsInstance(self.vreg.select_view('primary', req, rset),
                             baseviews.PrimaryView)
        self.assertIsInstance(self.vreg.select_view('list', req, rset),
                             baseviews.ListView)
        self.assertIsInstance(self.vreg.select_view('table', req, rset),
                             tableview.TableView)
        self.failUnlessRaises(NoSelectableObject,
                              self.vreg.select_view, 'creation', req, rset)
        # list of entities of different types
        rset, req = self.env.get_rset_and_req('Any X')
        self.assertIsInstance(self.vreg.select_view('primary', req, rset),
                                  baseviews.PrimaryView)
        self.assertIsInstance(self.vreg.select_view('list', req, rset),
                                  baseviews.ListView)
        self.assertIsInstance(self.vreg.select_view('table', req, rset),
                                  tableview.TableView)
        self.failUnlessRaises(NoSelectableObject,
                             self.vreg.select_view, 'creation', req, rset)
        self.failUnlessRaises(NoSelectableObject,
                              self.vreg.select_view, 'index', req, rset)
        # whatever
        rset, req = self.env.get_rset_and_req('Any N, X WHERE X in_group Y, Y name N')
        self.assertIsInstance(self.vreg.select_view('table', req, rset),
                                  tableview.TableView)
        self.failUnlessRaises(NoSelectableObject,
                              self.vreg.select_view, 'index', req, rset)
        self.failUnlessRaises(NoSelectableObject,
                              self.vreg.select_view, 'creation', req, rset)
        self.failUnlessRaises(NoSelectableObject,
                             self.vreg.select_view, 'primary', req, rset)
        self.failUnlessRaises(NoSelectableObject,
                             self.vreg.select_view, 'list', req, rset)
        self.failUnlessRaises(NoSelectableObject,
                             self.vreg.select_view, 'edition', req, rset)
        # mixed query
        rset, req = self.env.get_rset_and_req('Any U,G WHERE U is CWUser, G is CWGroup')
        self.failUnlessRaises(NoSelectableObject,
                              self.vreg.select_view, 'edition', req, rset)
        self.failUnlessRaises(NoSelectableObject,
                              self.vreg.select_view, 'creation', req, rset)
        self.assertIsInstance(self.vreg.select_view('table', req, rset),
                              tableview.TableView)
        # euser primary view priority
        rset, req = self.env.get_rset_and_req('CWUser X WHERE X login "admin"')
        self.assertIsInstance(self.vreg.select_view('primary', req, rset),
                             euser.CWUserPrimaryView)
        self.assertIsInstance(self.vreg.select_view('text', req, rset),
                             baseviews.TextView)

    def test_interface_selector(self):
        image = self.add_entity('Image', name=u'bim.png', data=Binary('bim'))
        # image primary view priority
        rset, req = self.env.get_rset_and_req('Image X WHERE X name "bim.png"')
        self.assertIsInstance(self.vreg.select_view('primary', req, rset),
                              idownloadable.IDownloadablePrimaryView)


    def test_score_entity_selector(self):
        image = self.add_entity('Image', name=u'bim.png', data=Binary('bim'))
        # image primary view priority
        rset, req = self.env.get_rset_and_req('Image X WHERE X name "bim.png"')
        self.assertIsInstance(self.vreg.select_view('image', req, rset),
                              idownloadable.ImageView)
        fileobj = self.add_entity('File', name=u'bim.txt', data=Binary('bim'))
        # image primary view priority
        rset, req = self.env.get_rset_and_req('File X WHERE X name "bim.txt"')
        self.assertRaises(NoSelectableObject, self.vreg.select_view, 'image', req, rset)



    def _test_view(self, vid, rql, args):
        if rql is None:
            rset = None
            req = self.request()
        else:
            rset, req = self.env.get_rset_and_req(rql)
        try:
            self.vreg.render('views', vid, req, rset=rset, **args)
        except:
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
        self.assertEquals(sorted(k for k in self.vreg['propertydefs'].keys()
                                 if k.startswith('boxes.edit_box')),
                          ['boxes.edit_box.context',
                           'boxes.edit_box.order',
                           'boxes.edit_box.visible'])
        self.assertEquals([k for k in self.vreg['propertyvalues'].keys()
                           if not k.startswith('system.version')],
                          [])
        self.assertEquals(self.vreg.property_value('boxes.edit_box.visible'), True)
        self.assertEquals(self.vreg.property_value('boxes.edit_box.order'), 2)
        self.assertEquals(self.vreg.property_value('boxes.possible_views_box.visible'), False)
        self.assertEquals(self.vreg.property_value('boxes.possible_views_box.order'), 10)
        self.assertRaises(KeyError, self.vreg.property_value, 'boxes.actions_box')




class CWETypeRQLAction(Action):
    id = 'testaction'
    __select__ = implements('CWEType') & rql_condition('X name "CWEType"')
    title = 'bla'

class RQLActionTC(ViewSelectorTC):

    def setUp(self):
        super(RQLActionTC, self).setUp()
        self.vreg.register_vobject_class(CWETypeRQLAction)

    def tearDown(self):
        super(RQLActionTC, self).tearDown()
        del self.vreg._registries['actions']['testaction']

    def test(self):
        rset, req = self.env.get_rset_and_req('CWEType X WHERE X name "CWEType"')
        self.assertDictEqual(self.pactions(req, rset),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,
                              'mainactions': [('edit', actions.ModifyAction)],
                              'moreactions': [('delete', actions.DeleteAction),
                                              ('copy', actions.CopyAction),
                                              ('testaction', CWETypeRQLAction),
                                              ('managepermission', actions.ManagePermissionsAction)],
                              })
        rset, req = self.env.get_rset_and_req('CWEType X WHERE X name "CWRType"')
        self.assertDictEqual(self.pactions(req, rset),
                             {'useractions': USERACTIONS,
                              'siteactions': SITEACTIONS,
                              'mainactions': [('edit', actions.ModifyAction)],
                              'moreactions': [('delete', actions.DeleteAction),
                                              ('copy', actions.CopyAction),
                                              ('managepermission', actions.ManagePermissionsAction)],
                              })



if __name__ == '__main__':
    unittest_main()
