"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from logilab.common.testlib import TestCase, unittest_main

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.devtools.fake import FakeRequest

from cubicweb.web.views.urlrewrite import SimpleReqRewriter, SchemaBasedRewriter, rgx, rgx_action


class UrlRewriteTC(TestCase):

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
        self.assertListEquals(rules, [
            ('foo' , dict(rql='Foo F')),
            ('/index' , dict(vid='index2')),
            ('/_', dict(vid='manage')),
            ('/_registry', dict(vid='registry')),
            ('/schema', dict(vid='schema')),
            ('/myprefs', dict(vid='propertiesform')),
            ('/siteconfig', dict(vid='systempropertiesform')),
            ('/siteinfo', dict(vid='info')),
            ('/manage', dict(vid='manage')),
            ('/notfound', dict(vid='404')),
            ('/error', dict(vid='error')),
            ('/sparql', dict(vid='sparql')),
            ('/schema/([^/]+?)/?$', {'rql': r'Any X WHERE X is CWEType, X name "\1"', 'vid': 'eschema'}),
            ('/add/([^/]+?)/?$' , dict(vid='creation', etype=r'\1')),
            ('/doc/images/(.+?)/?$', dict(fid='\\1', vid='wdocimages')),
            ('/doc/?$', dict(fid='main', vid='wdoc')),
            ('/doc/(.+?)/?$', dict(fid='\\1', vid='wdoc')),
            ('/changelog/?$', dict(vid='changelog')),
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
        self.assertListEquals(Rewriter.rules, [
            ('foo' , dict(rql='Foo F')),
            ('/index' , dict(vid='index2')),
            ])

    def test_basic_transformation(self):
        """test simple string-based rewrite"""
        rewriter = SimpleReqRewriter()
        req = FakeRequest()
        self.assertRaises(KeyError, rewriter.rewrite, req, '/view?vid=whatever')
        self.assertEquals(req.form, {})
        rewriter.rewrite(req, '/index')
        self.assertEquals(req.form, {'vid' : "index"})

    def test_regexp_transformation(self):
        """test regexp-based rewrite"""
        rewriter = SimpleReqRewriter()
        req = FakeRequest()
        rewriter.rewrite(req, '/add/Task')
        self.assertEquals(req.form, {'vid' : "creation", 'etype' : "Task"})
        req = FakeRequest()
        rewriter.rewrite(req, '/add/Task/')
        self.assertEquals(req.form, {'vid' : "creation", 'etype' : "Task"})




class RgxActionRewriteTC(CubicWebTC):

    def setup_database(self):
        self.p1 = self.create_user(u'user1')
        self.p1.set_attributes(firstname=u'joe', surname=u'Dalton')
        self.p2 = self.create_user(u'user2')
        self.p2.set_attributes(firstname=u'jack', surname=u'Dalton')

    def test_rgx_action_with_transforms(self):
        class TestSchemaBasedRewriter(SchemaBasedRewriter):
            rules = [
                (rgx('/(?P<sn>\w+)/(?P<fn>\w+)'), rgx_action(r'Any X WHERE X surname %(sn)s, X firstname %(fn)s',
                                                                             argsgroups=('sn', 'fn'),
                                                                             transforms={'sn' : unicode.capitalize,
                                                                                         'fn' : unicode.lower,})),
                ]
        rewriter = TestSchemaBasedRewriter()
        req = self.request()
        pmid, rset = rewriter.rewrite(req, u'/DaLToN/JoE')
        self.assertEquals(len(rset), 1)
        self.assertEquals(rset[0][0], self.p1.eid)

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

        rewriter = Rewriter()
        req = self.request()
        pmid, rset = rewriter.rewrite(req, '/collector')
        self.assertEquals(rset.rql, RQL1)
        self.assertEquals(req.form, {'vid' : "baseindex"})
        pmid, rset = rewriter.rewrite(req, '/collector/something')
        self.assertEquals(rset.rql, RQL2)
        self.assertEquals(req.form, {'vid' : "index"})
        pmid, rset = rewriter.rewrite(req, '/collector/something/')
        self.assertEquals(req.form, {'vid' : "index"})
        self.assertEquals(rset.rql, RQL2)
        pmid, rset = rewriter.rewrite(req, '/collector/somethingelse/')
        self.assertEquals(rset.rql, RQL1)
        self.assertEquals(req.form, {'vid' : "baseindex"})

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

        rewriter = Rewriter()
        req = self.request()
        pmid, rset = rewriter.rewrite(req, '/collector')
        self.assertEquals(rset.rql, RQL2)
        self.assertEquals(req.form, {'vid' : "index"})
        pmid, rset = rewriter.rewrite(req, '/collector/something')
        self.assertEquals(rset.rql, RQL2)
        self.assertEquals(req.form, {'vid' : "index"})
        pmid, rset = rewriter.rewrite(req, '/collector/something/')
        self.assertEquals(req.form, {'vid' : "index"})
        self.assertEquals(rset.rql, RQL2)
        pmid, rset = rewriter.rewrite(req, '/collector/somethingelse/')
        self.assertEquals(rset.rql, RQL2)
        self.assertEquals(req.form, {'vid' : "index"})


if __name__ == '__main__':
    unittest_main()
