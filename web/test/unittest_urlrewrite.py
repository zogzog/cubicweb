# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
from logilab.common.testlib import TestCase, unittest_main

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.devtools.fake import FakeRequest

from cubicweb.web.views.urlrewrite import SimpleReqRewriter, SchemaBasedRewriter, rgx, rgx_action


class UrlRewriteTC(CubicWebTC):

    def test_auto_extend_rules(self):
        class Rewriter(SimpleReqRewriter):
            rules = [
                ('foo', dict(rql='Foo F')),
                ('/index', dict(vid='index2')),
                ]
        rules = []
        for pattern, values in Rewriter.rules:
            if hasattr(pattern, 'pattern'):
                pattern = pattern.pattern
            rules.append((pattern, values))
        self.assertListEqual(rules, [
            ('foo' , dict(rql='Foo F')),
            ('/index' , dict(vid='index2')),
            ('/_', dict(vid='manage')),
            ('/_registry', dict(vid='registry')),
            ('/schema', dict(vid='schema')),
            ('/myprefs', dict(vid='propertiesform')),
            ('/siteconfig', dict(vid='systempropertiesform')),
            ('/siteinfo', dict(vid='siteinfo')),
            ('/manage', dict(vid='manage')),
            ('/notfound', dict(vid='404')),
            ('/error', dict(vid='error')),
            ('/sparql', dict(vid='sparql')),
            ('/processinfo', dict(vid='processinfo')),
            ('/cwuser$', {'vid': 'cw.users-and-groups-management',
                          'tab': 'cw_users_management'}),
            ('/cwgroup$', {'vid': 'cw.users-and-groups-management',
                           'tab': 'cw_groups_management'}),
            ('/cwsource$', {'vid': 'cw.sources-management'}),
            ('/schema/([^/]+?)/?$', {'rql': r'Any X WHERE X is CWEType, X name "\1"', 'vid': 'primary'}),
            ('/add/([^/]+?)/?$' , dict(vid='creation', etype=r'\1')),
            ('/doc/images/(.+?)/?$', dict(fid='\\1', vid='wdocimages')),
            ('/doc/?$', dict(fid='main', vid='wdoc')),
            ('/doc/(.+?)/?$', dict(fid='\\1', vid='wdoc')),
            # now in SchemaBasedRewriter
            #('/search/(.+)$', dict(rql=r'Any X WHERE X has_text "\1"')),
            ])


    def test_no_extend_rules(self):
        class Rewriter(SimpleReqRewriter):
            ignore_baseclass_rules = True
            rules = [
                ('foo', dict(rql='Foo F')),
                ('/index', dict(vid='index2')),
                ]
        self.assertListEqual(Rewriter.rules, [
            ('foo' , dict(rql='Foo F')),
            ('/index' , dict(vid='index2')),
            ])

    def test_basic_transformation(self):
        """test simple string-based rewrite"""
        req = FakeRequest()
        rewriter = SimpleReqRewriter(req)
        self.assertRaises(KeyError, rewriter.rewrite, req, '/view?vid=whatever')
        self.assertEqual(req.form, {})
        rewriter.rewrite(req, '/index')
        self.assertEqual(req.form, {'vid' : "index"})

    def test_regexp_transformation(self):
        """test regexp-based rewrite"""
        req = FakeRequest()
        rewriter = SimpleReqRewriter(req)
        rewriter.rewrite(req, '/add/Task')
        self.assertEqual(req.form, {'vid' : "creation", 'etype' : "Task"})
        req = FakeRequest()
        rewriter.rewrite(req, '/add/Task/')
        self.assertEqual(req.form, {'vid' : "creation", 'etype' : "Task"})




class RgxActionRewriteTC(CubicWebTC):

    def setup_database(self):
        req = self.request()
        self.p1 = self.create_user(req, u'user1')
        self.p1.cw_set(firstname=u'joe', surname=u'Dalton')
        self.p2 = self.create_user(req, u'user2')
        self.p2.cw_set(firstname=u'jack', surname=u'Dalton')

    def test_rgx_action_with_transforms(self):
        class TestSchemaBasedRewriter(SchemaBasedRewriter):
            rules = [
                (rgx('/(?P<sn>\w+)/(?P<fn>\w+)'), rgx_action(r'Any X WHERE X surname %(sn)s, X firstname %(fn)s',
                                                                             argsgroups=('sn', 'fn'),
                                                                             transforms={'sn' : unicode.capitalize,
                                                                                         'fn' : unicode.lower,})),
                ]
        req = self.request()
        rewriter = TestSchemaBasedRewriter(req)
        pmid, rset = rewriter.rewrite(req, u'/DaLToN/JoE')
        self.assertEqual(len(rset), 1)
        self.assertEqual(rset[0][0], self.p1.eid)

    def test_inheritance_precedence(self):
        RQL1 = 'Any C WHERE C is CWEType'
        RQL2 = 'Any C WHERE C is CWUser'

        class BaseRewriter(SchemaBasedRewriter):
            rules = [
               (rgx('/collector(.*)'),
                rgx_action(rql=RQL1,
                    form=dict(vid='baseindex')),
                ),
                ]
        class Rewriter(BaseRewriter):
            rules = [
               (rgx('/collector/something(/?)'),
                rgx_action(rql=RQL2,
                    form=dict(vid='index')),
                ),
                ]

        req = self.request()
        rewriter = Rewriter(req)
        pmid, rset = rewriter.rewrite(req, '/collector')
        self.assertEqual(rset.rql, RQL1)
        self.assertEqual(req.form, {'vid' : "baseindex"})
        pmid, rset = rewriter.rewrite(req, '/collector/something')
        self.assertEqual(rset.rql, RQL2)
        self.assertEqual(req.form, {'vid' : "index"})
        pmid, rset = rewriter.rewrite(req, '/collector/something/')
        self.assertEqual(req.form, {'vid' : "index"})
        self.assertEqual(rset.rql, RQL2)
        pmid, rset = rewriter.rewrite(req, '/collector/somethingelse/')
        self.assertEqual(rset.rql, RQL1)
        self.assertEqual(req.form, {'vid' : "baseindex"})

    def test_inheritance_precedence_same_rgx(self):
        RQL1 = 'Any C WHERE C is CWEType'
        RQL2 = 'Any C WHERE C is CWUser'

        class BaseRewriter(SchemaBasedRewriter):
            rules = [
               (rgx('/collector(.*)'),
                rgx_action(rql=RQL1,
                    form=dict(vid='baseindex')),
                ),
                ]
        class Rewriter(BaseRewriter):
            rules = [
               (rgx('/collector(.*)'),
                rgx_action(rql=RQL2,
                    form=dict(vid='index')),
                ),
                ]

        req = self.request()
        rewriter = Rewriter(req)
        pmid, rset = rewriter.rewrite(req, '/collector')
        self.assertEqual(rset.rql, RQL2)
        self.assertEqual(req.form, {'vid' : "index"})
        pmid, rset = rewriter.rewrite(req, '/collector/something')
        self.assertEqual(rset.rql, RQL2)
        self.assertEqual(req.form, {'vid' : "index"})
        pmid, rset = rewriter.rewrite(req, '/collector/something/')
        self.assertEqual(req.form, {'vid' : "index"})
        self.assertEqual(rset.rql, RQL2)
        pmid, rset = rewriter.rewrite(req, '/collector/somethingelse/')
        self.assertEqual(rset.rql, RQL2)
        self.assertEqual(req.form, {'vid' : "index"})


if __name__ == '__main__':
    unittest_main()
