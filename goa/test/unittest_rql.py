from cubicweb.goa.testlib import *

from cubicweb import Binary

from logilab.common.testlib import unittest_main
from mx.DateTime import now, today, DateTimeType
import rql

from google.appengine.api.datastore_types import Blob, Text

# stored procedure definition #################################################

from rql.utils import register_function, FunctionDescr

class itemtype_sort_value(FunctionDescr):
    supported_backends = ('sqlite',)
    rtype = 'Int'

try:
    register_function(itemtype_sort_value)
except AssertionError:
    pass

def init_sqlite_connexion(cnx):
    def itemtype_sort_value(text):
        return {"personal":2, "business":1}[text]
    cnx.create_function("ITEMTYPE_SORT_VALUE", 1, itemtype_sort_value)

from cubicweb.server import SQL_CONNECT_HOOKS
sqlite_hooks = SQL_CONNECT_HOOKS.setdefault('sqlite', [])
sqlite_hooks.append(init_sqlite_connexion)

# end stored procedure definition #############################################

class Article(db.Model):        
    content = db.TextProperty()
    synopsis = db.StringProperty(default=u'hello')

class Blog(db.Model):
    diem = db.DateProperty(required=True, auto_now_add=True)
    content = db.TextProperty()
    itemtype = db.StringProperty(required=True, choices=(u'personal', u'business'))
    talks_about = db.ReferenceProperty(Article) 
    cites = db.SelfReferenceProperty() 
    data = db.BlobProperty()

    
class RQLTest(GAEBasedTC):
    MODEL_CLASSES = (Article, Blog)
    
    def setUp(self):
        GAEBasedTC.setUp(self)
        # hack to make talks_about cardinality to ** instead of ?*
        self.schema.rschema('talks_about').set_rproperty('Blog', 'Article',
                                                         'cardinality', '**')
        self.req = self.request()
        self.article = self.add_entity('Article', content=u'very interesting')
        self.blog = self.add_entity('Blog', itemtype=u'personal', content=u'hop')
        self.execute('SET X talks_about Y WHERE X eid %(x)s, Y eid %(y)s',
                     {'x': self.blog.eid, 'y': self.article.eid})
        self.commit()
        
    def _check_rset_size(self, rset, row, col):
        self.assertEquals(len(rset), row)
        self.assertEquals(len(rset[0]), col)
        self.assertEquals(len(rset.description), row)
        self.assertEquals(len(rset.description[0]), col)
        
    def _check_blog_rset(self, rset):
        self._check_rset_size(rset, 1, 1)
        self.assertEquals(rset.description[0][0], 'Blog')
        self.assertEquals(rset[0][0], self.blog.eid)
        self.assertEquals(rset.get_entity(0, 0).eid, self.blog.eid)

    def test_0_const(self):
        rset = self.req.execute('Any 1')
        self._check_rset_size(rset, 1, 1)
        self.assertEquals(rset[0][0], 1)
        self.assertEquals(rset.description[0][0], 'Int')

    def test_0_now_const(self):
        rset = self.req.execute('Any NOW')
        self._check_rset_size(rset, 1, 1)
        self.assertIsInstance(rset[0][0], DateTimeType)
        self.assertEquals(rset.description[0][0], 'Datetime')

    def test_0_today_const(self):
        rset = self.req.execute('Any TODAY')
        self._check_rset_size(rset, 1, 1)
        self.assertIsInstance(rset[0][0], DateTimeType)
        self.assertEquals(rset[0][0], today())
        self.assertEquals(rset.description[0][0], 'Date')


    def test_1_eid(self):
        rset = self.req.execute('Any X WHERE X eid %(x)s', {'x': self.blog.eid})
        self._check_blog_rset(rset)
        rset = self.req.execute('Any X WHERE X eid "%s"' % self.blog.eid)
        self._check_blog_rset(rset)

    def test_1_eid_eid(self):
        rset = self.req.execute('Any X,Y WHERE X eid %(x)s, Y eid %(y)s', {'x': self.blog.eid,
                                                                           'y': self.article.eid})
        self._check_rset_size(rset, 1, 2)
        self.assertEquals(rset.description[0], ('Blog', 'Article'))
        self.assertEquals(rset[0][0], self.blog.eid)
        self.assertEquals(rset[0][1], self.article.eid)

    def test_1_eid_with_is(self):
        self.assertRaises(rql.TypeResolverException,
                          self.req.execute, 'Any X WHERE X eid %(x)s, X is Article', {'x': self.blog.eid})
        rset = self.req.execute('Any X WHERE X eid %(x)s, X is Blog', {'x': self.blog.eid})
        self._check_blog_rset(rset)

    def test_1_is(self):
        rset = self.req.execute('Any X WHERE X is Blog')
        self._check_blog_rset(rset)
        blog2 = Blog(itemtype=u'personal', content=u'hop')
        blog2.put()
        rset = self.req.execute('Any X WHERE X is Blog')
        self.assertEquals(len(rset), 2)
        self.assertEquals(rset.description, [('Blog',), ('Blog',)])

        
    def test_2_attribute_selection_1(self):
        rset = self.req.execute('Any X,D,C WHERE X is Blog, X diem D, X content C')
        self._check_rset_size(rset, 1, 3)
        self.assertEquals(rset[0], [self.blog.eid, today(), u'hop'])
        self.assertEquals(rset.description[0], ('Blog', 'Date', 'String'))
        self.assertIsInstance(rset[0][1], DateTimeType)
        
    def test_2_attribute_selection_2(self):
        rset = self.req.execute('Any D,C WHERE X is Blog, X diem D, X content C')
        self._check_rset_size(rset, 1, 2)
        self.assertEquals(rset[0], [today(), u'hop'])
        self.assertEquals(rset.description[0], ('Date', 'String'))
        
    def test_2_attribute_selection_binary(self):
        rset = self.req.execute('Any D WHERE X is Blog, X data D')
        self._check_rset_size(rset, 1, 1)
        self.assertEquals(rset[0], [None])
        self.assertEquals(rset.description[0], ('Bytes',))
        self.blog['data'] = Binary('raw data')
        self.blog.put()
        rset = self.req.execute('Any D WHERE X is Blog, X data D')
        self._check_rset_size(rset, 1, 1)
        self.assertIsInstance(rset[0][0], Binary)
        value = rset[0][0].getvalue()
        self.assertIsInstance(value, str)
        self.failIf(isinstance(value, Blob)) 
        self.assertEquals(value, 'raw data')
        self.assertEquals(rset.description[0], ('Bytes',))
        
    def test_2_attribute_selection_long_text(self):
        self.blog['content'] = text = 'a'*501
        self.blog.put()
        rset = self.req.execute('Any C WHERE X is Blog, X content C')
        self._check_rset_size(rset, 1, 1)
        self.assertIsInstance(rset[0][0], unicode)
        self.failIf(isinstance(rset[0][0], Text)) 
        self.assertEquals(rset[0][0], text)
        
    def test_2_attribute_selection_transformation(self):
        rset = self.req.execute('Any X,UPPER(C) WHERE X is Blog, X content C')
        self._check_rset_size(rset, 1, 2)
        self.assertEquals(rset[0], [self.blog.eid, u'HOP'])
        self.assertEquals(rset.description[0], ('Blog', 'String',))


    def test_3_attribute_restriction(self):
        rset = self.req.execute('Any X WHERE X itemtype "personal"')
        self._check_blog_rset(rset)
        rset = self.req.execute('Any X WHERE X itemtype "business"')
        self.assertEquals(len(rset), 0)
        
    def test_3_ambigous_attribute_restriction_1(self):
        rset = self.req.execute('Any X WHERE X content "hello"')
        self.assertEquals(len(rset), 0)
        
    def test_3_ambigous_attribute_restriction_2(self):
        rset = self.req.execute('Any X WHERE X content "hop"')
        self._check_blog_rset(rset)
        
    def test_3_ambigous_attribute_restriction_3(self):
        article = Article(content=u'hop')
        article.put()
        rset = self.req.execute('Any X WHERE X content "hop"')
        self._check_rset_size(rset, 2, 1)
        self.assertUnorderedIterableEquals([r[0] for r in rset], [self.blog.eid, article.eid])
        self.assertUnorderedIterableEquals([r[0] for r in rset.description], ['Blog', 'Article'])

    def test_3_incoherant_attribute_restriction(self):
        rset = self.req.execute('Any X WHERE X eid %(x)s, X content "hola"',
                                {'x': self.blog.eid})
        self.assertEquals(len(rset), 0)
        
    def test_3_multiple_attribute_restriction(self):
        rset = self.req.execute('Any X WHERE X content "hop", X itemtype "personal"')
        self._check_blog_rset(rset)
        
    def test_3_incoherant_multiple_attribute_restriction(self):
        rset = self.req.execute('Any X WHERE X content "hip", X itemtype "personal"')
        self.assertEquals(len(rset), 0)

    def test_3_today_attribute_restriction(self):
        rset = self.req.execute('Any X WHERE X diem < TODAY')
        self.assertEquals(len(rset), 0)
        rset = self.req.execute('Any X WHERE X diem <= TODAY')
        self._check_blog_rset(rset)
        rset = self.req.execute('Any X WHERE X diem > TODAY')
        self.assertEquals(len(rset), 0)
        rset = self.req.execute('Any X WHERE X diem >= TODAY')
        self._check_blog_rset(rset)

    def test_3_now_attribute_restriction(self):
        rset = self.req.execute('Any X WHERE X diem < NOW')
        self._check_blog_rset(rset)
        rset = self.req.execute('Any X WHERE X diem <= NOW')
        self._check_blog_rset(rset)
        rset = self.req.execute('Any X WHERE X diem > NOW')
        self.assertEquals(len(rset), 0)
        rset = self.req.execute('Any X WHERE X diem >= NOW')
        self.assertEquals(len(rset), 0)

    def test_3_in_attribute_restriction(self):
        self.skip('missing actual gae support, retry latter')
        article2 = Article(content=u'hip')
        rset = self.req.execute('Any X WHERE X content IN ("hop", "hip")')
        self._check_rset_size(rset, 2, 1)
        self.assertUnorderedIterableEquals([r[0] for r in rset], [self.blog.eid, article.eid])
        self.assertUnorderedIterableEquals([r[0] for r in rset.description], ['Blog', 'Article'])

    def test_3_like(self):
        repo = self.config.repository()
        versions = repo.get_versions()
        self.assertEquals(versions.keys(), ['cubicweb'])
    
    def _setup_relation_description(self):
        self.article2 = self.add_entity('Article', content=u'hop')
        self.blog2 = self.add_entity('Blog', itemtype=u'personal', content=u'hip')
        self.execute('SET X talks_about Y WHERE X eid %(x)s, Y eid %(y)s',
                     {'x': self.blog2.eid, 'y': self.article2.eid})
        self.blog3 = self.add_entity('Blog', itemtype=u'business', content=u'hep')
        self.commit()
        
    def test_4_relation_restriction_1(self):
        self._setup_relation_description()
        rset = self.req.execute('Any X WHERE X talks_about Y')
        self._check_rset_size(rset, 2, 1)
        self.assertUnorderedIterableEquals([r[0] for r in rset],
                             [self.blog.eid, self.blog2.eid])
        self.assertUnorderedIterableEquals([r[0] for r in rset.description], ['Blog', 'Blog'])
        
    def test_4_relation_restriction_2(self):
        self._setup_relation_description()
        rset = self.req.execute('Any Y WHERE X talks_about Y')
        self._check_rset_size(rset, 2, 1)
        self.assertUnorderedIterableEquals([r[0] for r in rset],
                             [self.article.eid, self.article2.eid])
        self.assertUnorderedIterableEquals([r[0] for r in rset.description],
                             ['Article', 'Article'])
        
    def test_4_relation_restriction_3(self):
        self._setup_relation_description()
        rset = self.req.execute('Any X,Y WHERE X talks_about Y')
        self._check_rset_size(rset, 2, 2)
        self.assertUnorderedIterableEquals([tuple(r) for r in rset],
                             [(self.blog.eid, self.article.eid),
                              (self.blog2.eid, self.article2.eid)])
        self.assertUnorderedIterableEquals([tuple(r) for r in rset.description],
                             [('Blog', 'Article'),
                              ('Blog', 'Article')])
        
    def test_4_relation_restriction_4(self):
        self._setup_relation_description()
        rset = self.req.execute('Any X,Y WHERE X talks_about Y, X eid %(x)s',
                                {'x': self.blog.eid})
        self._check_rset_size(rset, 1, 2)
        self.assertEquals(rset[0], [self.blog.eid, self.article.eid])
        self.assertUnorderedIterableEquals(rset.description[0], ['Blog', 'Article'])
        
    def test_4_relation_restriction_5(self):
        self._setup_relation_description()
        rset = self.req.execute('Any X,Y WHERE X talks_about Y, Y eid %(x)s',
                                {'x': self.article.eid})
        self._check_rset_size(rset, 1, 2)
        self.assertEquals(rset[0], [self.blog.eid, self.article.eid])
        self.assertUnorderedIterableEquals(rset.description[0], ['Blog', 'Article'])
        
    def test_4_relation_subject_restriction(self):
        self._setup_relation_description()
        rset = self.req.execute('Any X,Y WHERE X talks_about Y, X content %(c)s',
                                {'c': 'hop'})
        self._check_rset_size(rset, 1, 2)
        self.assertEquals(rset[0], [self.blog.eid, self.article.eid])
        self.assertUnorderedIterableEquals(rset.description[0], ['Blog', 'Article'])
        
    def test_4_relation_object_restriction(self):
        self._setup_relation_description()
        rset = self.req.execute('Any X WHERE X is Blog, X talks_about Y, Y content %(c)s',
                                {'c': 'very interesting'})
        self._check_rset_size(rset, 1, 1)
        self.assertEquals(rset[0], [self.blog.eid])
        self.assertUnorderedIterableEquals(rset.description[0], ['Blog'])
        
    def test_4_relation_subject_object_restriction(self):
        article2 = self.add_entity('Article', content=u'very interesting')
        rset = self.req.execute('Any X,XC WHERE X is Blog, X content XC, X content %(xc)s, '
                                'X talks_about Y, Y content %(c)s',
                                {'xc': 'hop', 'c': 'very interesting'})
        self._check_rset_size(rset, 1, 2)
        self.assertEquals(rset[0], [self.blog.eid, self.blog.content])
        self.assertUnorderedIterableEquals(rset.description[0], ['Blog', 'String'])
        
    def test_4_relation_subject_object_restriction_no_res(self):
        article2 = self.add_entity('Article', content=u'very interesting')
        rset = self.req.execute('Any X,XC WHERE X is Blog, X content XC, X content %(xc)s, '
                                'X talks_about Y, Y content %(c)s',
                                {'xc': 'hip', 'c': 'very interesting'})
        self.assertEquals(len(rset), 0)
        
    def test_4_relation_subject_object_restriction_no_res_2(self):
        rset = self.req.execute('Any X,XC WHERE X is Blog, X content XC, X content %(xc)s, '
                                'X talks_about Y, Y content %(c)s',
                                {'xc': 'hop', 'c': 'not interesting'})
        self.assertEquals(len(rset), 0)
        
    def test_4_relation_restriction_7(self):
        self._setup_relation_description()
        rset = self.req.execute('Any XC,XD,YC WHERE X talks_about Y, Y eid %(x)s,'
                                'X content XC, X diem XD, Y content YC',
                                {'x': self.article.eid})
        self._check_rset_size(rset, 1, 3)
        self.assertEquals(rset[0], [self.blog.content, self.blog.diem, self.article.content])
        self.assertUnorderedIterableEquals(rset.description[0], ['String', 'Date', 'String'])
        
    def test_4_relation_restriction_8(self):
        self._setup_relation_description()
        rset = self.req.execute('Any X,Y WHERE X cites Y, Y eid %(x)s', {'x': self.blog.eid})
        self.assertEquals(len(rset), 0)

    def test_4_relation_restriction_9(self):
        article2 = self.add_entity('Article', content=u'hop')
        self.req.execute('SET X talks_about Y WHERE X eid %(x)s, Y eid %(y)s',
                         {'x': self.blog.eid, 'y': article2.eid})
        rset = self.req.execute('Any X,Y WHERE X talks_about Y, X eid %(x)s, Y eid %(y)s',
                                {'x': self.blog.eid, 'y': article2.eid})
        self._check_rset_size(rset, 1, 2)
        
    def test_4_ambiguous_subject_relation(self):
        ye = self.add_entity('YamsEntity')
        self.req.execute('SET X ambiguous_relation Y WHERE X eid %(x)s, Y eid %(y)s',
                         {'x': ye.eid, 'y': self.blog.eid})
        self.req.execute('SET X ambiguous_relation Y WHERE X eid %(x)s, Y eid %(y)s',
                         {'x': ye.eid, 'y': self.article.eid})
        self.commit()
        #ye = self.vreg.etype_class('YamsEntity ')(req, None)
        #ye.to_gae_model()['s_ambiguous_relation'] = [self.blog.key(), self.article.key()]
        #ye.put()
        rset = self.req.execute('Any X WHERE Y ambiguous_relation X')
        self._check_rset_size(rset, 2, 1)
        self.assertUnorderedIterableEquals([r[0] for r in rset], [self.blog.eid, self.article.eid])
        self.assertUnorderedIterableEquals([r[0] for r in rset.description], ['Blog', 'Article'])
        rset = self.req.execute('Any X WHERE Y ambiguous_relation X, Y eid %(x)s', {'x': ye.eid})
        self._check_rset_size(rset, 2, 1)
        self.assertUnorderedIterableEquals([r[0] for r in rset], [self.blog.eid, self.article.eid])
        self.assertUnorderedIterableEquals([r[0] for r in rset.description], ['Blog', 'Article'])
        
    def test_4_relation_selection(self):
        req = self.request()
        rset = req.execute('Any N WHERE G content N, U talks_about G, U eid %(u)s', {'u': self.blog.eid})
        self._check_rset_size(rset, 1, 1)
        self.assertEquals(rset[0][0], 'very interesting')


    def test_5_orderby(self):
        self._setup_relation_description()
        rset = self.req.execute('Any X,XC ORDERBY XC WHERE X is Blog, X content XC')
        self._check_rset_size(rset, 3, 2)
        self.assertEquals(rset.rows,
                          [[self.blog3.eid, 'hep'],
                           [self.blog2.eid, 'hip'],
                           [self.blog.eid, 'hop']])
                           
    def test_5_orderby_desc(self):
        self._setup_relation_description()
        rset = self.req.execute('Any X,XC ORDERBY XC DESC WHERE X is Blog, X content XC')
        self._check_rset_size(rset, 3, 2)
        self.assertEquals(rset.rows,
                          [[self.blog.eid, 'hop'],
                           [self.blog2.eid, 'hip'],
                           [self.blog3.eid, 'hep']])

    def test_5_orderby_several_terms(self):
        self._setup_relation_description()
        rset = self.req.execute('Any X,XC,XI ORDERBY XI,XC WHERE X is Blog, X content XC, X itemtype XI')
        self._check_rset_size(rset, 3, 3)
        self.assertEquals(rset.rows,
                          [[self.blog3.eid, 'hep', 'business'],
                           [self.blog2.eid, 'hip', 'personal'],
                           [self.blog.eid, 'hop', 'personal']])

    def test_5_orderby_several_terms_mixed_implicit(self):
        self._setup_relation_description()
        rset = self.req.execute('Any X,XC,XI ORDERBY XI,XC DESC WHERE X is Blog, X content XC, X itemtype XI')
        self._check_rset_size(rset, 3, 3)
        self.assertEquals(rset.rows,
                          [[self.blog3.eid, 'hep', 'business'],
                           [self.blog.eid, 'hop', 'personal'],
                           [self.blog2.eid, 'hip', 'personal']])

    def test_5_orderby_several_terms_explicit_order(self):
        self._setup_relation_description()
        rset = self.req.execute('Any X,XC,XI ORDERBY XI DESC,XC DESC WHERE X is Blog, X content XC, X itemtype XI')
        self._check_rset_size(rset, 3, 3)
        self.assertEquals(rset.rows,
                          [[self.blog.eid, 'hop', 'personal'],
                           [self.blog2.eid, 'hip', 'personal'],
                           [self.blog3.eid, 'hep', 'business']])
        
    def test_5_orderby_several_terms_mixed_order(self):
        self._setup_relation_description()
        rset = self.req.execute('Any X,XC,XI ORDERBY XI ASC,XC DESC WHERE X is Blog, X content XC, X itemtype XI')
        self._check_rset_size(rset, 3, 3)
        self.assertEquals(rset.rows,
                          [[self.blog3.eid, 'hep', 'business'],
                           [self.blog.eid, 'hop', 'personal'],
                           [self.blog2.eid, 'hip', 'personal']])


    def test_5_orderby_lower(self):
        blog2 = self.add_entity('Blog', itemtype=u'business', content=u'Hup')
        rset = self.req.execute('Any X ORDERBY LOWER(XC) '
                                'WHERE X is Blog, X content XC')
        self._check_rset_size(rset, 2, 1)
        self.assertEquals(rset.rows, [[self.blog.eid], [blog2.eid]])
        rset = self.req.execute('Any X ORDERBY LOWER(XC) DESC'
                                'WHERE X is Blog, X content XC')
        self._check_rset_size(rset, 2, 1)
        self.assertEquals(rset.rows, [[blog2.eid], [self.blog.eid]])

    def test_5_orderby_stored_proc(self):
        blog2 = self.add_entity('Blog', itemtype=u'business', content=u'hop')
        rset = self.req.execute('Any X ORDERBY ITEMTYPE_SORT_VALUE(XIT) '
                                'WHERE X is Blog, X itemtype XIT')
        self._check_rset_size(rset, 2, 1)
        self.assertEquals(rset.rows, [[blog2.eid], [self.blog.eid]])
        rset = self.req.execute('Any X ORDERBY ITEMTYPE_SORT_VALUE(XIT) DESC'
                                'WHERE X is Blog, X itemtype XIT')
        self._check_rset_size(rset, 2, 1)
        self.assertEquals(rset.rows, [[self.blog.eid], [blog2.eid]])
                          
        
    def test_6_limit(self):
        self._setup_relation_description()
        rset = self.req.execute('Any X LIMIT 2 WHERE X is Blog')
        self._check_rset_size(rset, 2, 1)
        
    def test_6_offset(self):
        self._setup_relation_description()
        rset = self.req.execute('Any XC ORDERBY XC DESC OFFSET 1 WHERE X is Blog, X content XC')
        self._check_rset_size(rset, 2, 1)
        self.assertEquals(rset.rows, [['hip'], ['hep']])
        
    def test_6_limit_and_orderby(self):
        self._setup_relation_description()
        rset = self.req.execute('Any XC ORDERBY XC LIMIT 2 WHERE X is Blog, X content XC')
        self._check_rset_size(rset, 2, 1)
        self.assertEquals(rset.rows, [['hep'], ['hip']])
        
    def test_6_limit_offset_and_orderby(self):
        self._setup_relation_description()
        rset = self.req.execute('Any XC ORDERBY XC LIMIT 2 OFFSET 0 WHERE X is Blog, X content XC')
        self._check_rset_size(rset, 2, 1)
        self.assertEquals(rset.rows, [['hep'], ['hip']])
        rset = self.req.execute('Any XC ORDERBY XC LIMIT 2 OFFSET 1 WHERE X is Blog, X content XC')
        self._check_rset_size(rset, 2, 1)
        self.assertEquals(rset.rows, [['hip'], ['hop']])
        rset = self.req.execute('Any XC ORDERBY XC LIMIT 2 OFFSET 2 WHERE X is Blog, X content XC')
        self._check_rset_size(rset, 1, 1)
        self.assertEquals(rset.rows, [['hop']])
        rset = self.req.execute('Any XC ORDERBY XC LIMIT 2 OFFSET 3 WHERE X is Blog, X content XC')
        self.failIf(rset)
        

    def test_7_simple_datetimecast(self):
        self._setup_relation_description()
        _today = today()
        _tomorrow = _today + 1
        rset = self.req.execute('Any X WHERE X is Blog, X creation_date >= "%s"'
                                % _tomorrow.strftime('%Y-%m-%d'))
        self.failUnless(len(rset) == 0)
        rset = self.req.execute('Any X WHERE X is Blog, X creation_date >= "%s"'
                                % _today.strftime('%Y-%m-%d'))
        self._check_rset_size(rset, 3, 1)
        rset = self.req.execute('Any X WHERE X is Blog, X creation_date <= "%s"'
                                % _tomorrow.strftime('%Y-%m-%d'))
        self._check_rset_size(rset, 3, 1)
        
    def test_7_identity_relation(self):
        rset = self.req.execute('Any X WHERE X identity Y, X eid %(x)s, Y eid %(y)s',
                                {'x': self.user.eid, 'y': self.user.eid})
        self._check_rset_size(rset, 1, 1)
        rset = self.req.execute('Any Y WHERE X identity Y, X eid %(x)s',
                                {'x': self.user.eid})
        self._check_rset_size(rset, 1, 1)
        self.assertEquals(rset.rows, [[self.user.eid]])
        blog2 = self.add_entity('Blog', itemtype=u'personal', content=u'hip')
        rset = self.req.execute('Any X WHERE X identity Y, X eid %(x)s, Y eid %(y)s',
                                {'x': self.blog.eid, 'y': blog2.eid})
        self.failIf(rset)
        
    def test_8_not_relation_1(self):
        rset = self.req.execute('Any X WHERE X identity U, NOT U in_group G, '
                                'G name "guests", X eid %(x)s, U eid %(u)s',
                                {'x': self.user.eid, 'u': self.user.eid})
        self._check_rset_size(rset, 1, 1)
        self.assertEquals(rset.rows, [[self.user.eid]])        

    def test_8_not_relation_linked_subject(self):
        rset = self.req.execute('Any X WHERE NOT X talks_about Y, Y eid %(y)s',
                                {'y': self.article.eid})
        self.failIf(rset)
        blog2 = self.add_entity('Blog', content=u'hop', itemtype=u'personal')
        self.commit()
        rset = self.req.execute('Any X WHERE NOT X talks_about Y, Y eid %(y)s',
                                {'y': self.article.eid})        
        self._check_rset_size(rset, 1, 1)
        self.assertEquals(rset.rows, [[blog2.eid]])

    def test_8_not_relation_linked_object(self):
        rset = self.req.execute('Any Y WHERE NOT X talks_about Y, X eid %(x)s',
                                {'x': self.blog.eid})
        self.failIf(rset)
        article2 = self.add_entity('Article', content=u'hop')
        self.commit()
        rset = self.req.execute('Any Y WHERE NOT X talks_about Y, X eid %(x)s',
                                {'x': self.blog.eid})
        self._check_rset_size(rset, 1, 1)
        self.assertEquals(rset.rows, [[article2.eid]])

    def test_8_not_relation_linked_attr(self):
        self.skip('not yet implemented')
        # TODO: this should generated 
        # Query(X)[s_talks_about] > "hop" || Query(X)[s_talks_about] < "hop"
        article2 = self.add_entity('Article', content=u'hop')
        self.req.execute('SET X talks_about Y WHERE X eid %(x)s, Y eid %(y)s',
                         {'x': self.blog.eid, 'y': article2.eid})
        self.commit()
        rset = self.req.execute('Any X WHERE NOT X talks_about Y, Y content "hop"')
        self._check_rset_size(rset, 1, 2)
        self.assertEquals(rset.rows, [[self.blog.eid, self.article.eid]])

    def test_8_not_relation_unlinked_subject(self):
        blog2 = self.add_entity('Blog', content=u'hop', itemtype=u'personal')
        self.commit()
        rset = self.req.execute('Any X WHERE NOT X talks_about Y')
        self._check_rset_size(rset, 1, 1)
        self.assertEquals(rset.rows, [[blog2.eid]])

    def test_8_not_relation_unlinked_object(self):
        article2 = self.add_entity('Article', content=u'hop')
        self.commit()
        rset = self.req.execute('Any Y WHERE NOT X talks_about Y')
        self._check_rset_size(rset, 1, 1)
        self.assertEquals(rset.rows, [[article2.eid]])
        
    def test_8_not_relation_final_1(self):
        rset = self.req.execute('Any G WHERE G is EGroup, NOT G name "guests"')
        self._check_rset_size(rset, 2, 1)
        self.assertUnorderedIterableEquals([g.name for g in rset.entities()],
                                           ['users', 'managers'])        
        
    def test_8_not_relation_final_2(self):
        rset = self.req.execute('Any GN WHERE G is EGroup, NOT G name "guests", G name GN')
        self._check_rset_size(rset, 2, 1)
        self.assertUnorderedIterableEquals([gn for gn, in rset.rows],
                                           ['users', 'managers'])


    def test_9_exists(self):
        blog2 = self.add_entity('Article', content=u'hop')
        article2 = self.add_entity('Article', content=u'hop')
        self.req.execute('SET X talks_about Y WHERE X eid %(x)s, Y eid %(y)s',
                         {'x': self.blog.eid, 'y': article2.eid})
        self.commit()
        rset = self.req.execute('Any X WHERE X is Blog, EXISTS(X talks_about Y)')
        self._check_rset_size(rset, 1, 1)
        self.assertEquals(rset.rows, [[self.blog.eid]])
        
        
    def test_error_unknown_eid(self):
        rset = self.req.execute('Any X WHERE X eid %(x)s', {'x': '1234'})
        self.assertEquals(len(rset), 0)
        self.blog.delete()
        rset = self.req.execute('Any X WHERE X eid %(x)s', {'x': self.blog.eid})
        self.assertEquals(len(rset), 0)

    def test_nonregr_inlined_relation(self):
        eid = self.execute('INSERT YamsEntity X: X inlined_relation Y WHERE Y eid %(y)s',
                           {'y': self.blog.eid})[0][0]
        self.commit()
        rset = self.execute('Any X WHERE Y inlined_relation X, Y eid %(y)s', {'y': eid})
        self._check_rset_size(rset, 1, 1)
        self.assertEquals(rset[0][0], self.blog.eid)
        
if __name__ == '__main__':
    unittest_main()
