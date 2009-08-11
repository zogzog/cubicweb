# -*- coding: utf-8 -*-
"""Unit tests for url publishing service

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

import re

from logilab.common.testlib import unittest_main

from cubicweb.rset import ResultSet
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.devtools.fake import FakeRequest
from cubicweb.web import NotFound, Redirect
from cubicweb.web.views.urlrewrite import SimpleReqRewriter


class URLPublisherTC(CubicWebTC):
    """test suite for QSPreProcessor"""

    def setup_database(self):
        self.create_user(u'ÿsaÿe')
        b = self.add_entity('BlogEntry', title=u'hell\'o', content=u'blabla')
        c = self.add_entity('Tag', name=u'yo') # take care: Tag's name normalized to lower case
        self.execute('SET C tags B WHERE C eid %(c)s, B eid %(b)s', {'c':c.eid, 'b':b.eid}, 'b')

    def process(self, url):
        req = self.req = self.request()
        return self.app.url_resolver.process(req, url)

    def test_raw_path(self):
        """tests raw path resolution'"""
        self.assertEquals(self.process('view'), ('view', None))
        self.assertEquals(self.process('edit'), ('edit', None))
        self.assertRaises(NotFound, self.process, 'whatever')

    def test_eid_path(self):
        """tests eid path resolution"""
        self.assertIsInstance(self.process('123')[1], ResultSet)
        self.assertEquals(len(self.process('123')[1]), 1)
        self.assertRaises(NotFound, self.process, '123/345')
        self.assertRaises(NotFound, self.process, 'not_eid')

    def test_rest_path(self):
        """tests the rest path resolution"""
        ctrl, rset = self.process('CWUser')
        self.assertEquals(ctrl, 'view')
        self.assertEquals(rset.description[0][0], 'CWUser')
        self.assertEquals(rset.printable_rql(),
                          "Any X,AA,AB,AC,AD ORDERBY AA WHERE X is CWUser, X login AA, X firstname AB, X surname AC, X modification_date AD")
        ctrl, rset = self.process('CWUser/login/admin')
        self.assertEquals(ctrl, 'view')
        self.assertEquals(len(rset), 1)
        self.assertEquals(rset.description[0][0], 'CWUser')
        self.assertEquals(rset.printable_rql(), 'Any X WHERE X is CWUser, X login "admin"')
        ctrl, rset = self.process('cwuser/admin')
        self.assertEquals(ctrl, 'view')
        self.assertEquals(len(rset), 1)
        self.assertEquals(rset.description[0][0], 'CWUser')
        self.assertEquals(rset.printable_rql(), 'Any X WHERE X is CWUser, X login "admin"')
        ctrl, rset = self.process('cwuser/eid/%s'%rset[0][0])
        self.assertEquals(ctrl, 'view')
        self.assertEquals(len(rset), 1)
        self.assertEquals(rset.description[0][0], 'CWUser')
        self.assertEquals(rset.printable_rql(), 'Any X WHERE X is CWUser, X eid 5')
        # test non-ascii paths
        ctrl, rset = self.process('CWUser/login/%C3%BFsa%C3%BFe')
        self.assertEquals(ctrl, 'view')
        self.assertEquals(len(rset), 1)
        self.assertEquals(rset.description[0][0], 'CWUser')
        self.assertEquals(rset.printable_rql(), u'Any X WHERE X is CWUser, X login "ÿsaÿe"')
        # test quoted paths
        ctrl, rset = self.process('BlogEntry/title/hell%27o')
        self.assertEquals(ctrl, 'view')
        self.assertEquals(len(rset), 1)
        self.assertEquals(rset.description[0][0], 'BlogEntry')
        self.assertEquals(rset.printable_rql(), u'Any X WHERE X is BlogEntry, X title "hell\'o"')
        # errors
        self.assertRaises(NotFound, self.process, 'CWUser/eid/30000')
        self.assertRaises(NotFound, self.process, 'Workcases')
        self.assertRaises(NotFound, self.process, 'CWUser/inexistant_attribute/joe')

    def test_action_path(self):
        """tests the action path resolution"""
        self.assertRaises(Redirect, self.process, '1/edit')
        self.assertRaises(Redirect, self.process, 'Tag/name/yo/edit')
        self.assertRaises(Redirect, self.process, 'Tag/yo/edit')
        self.assertRaises(NotFound, self.process, 'view/edit')
        self.assertRaises(NotFound, self.process, '1/non_action')
        self.assertRaises(NotFound, self.process, 'CWUser/login/admin/non_action')


    def test_regexp_path(self):
        """tests the regexp path resolution"""
        ctrl, rset = self.process('add/Task')
        self.assertEquals(ctrl, 'view')
        self.assertEquals(rset, None)
        self.assertEquals(self.req.form, {'etype' : "Task", 'vid' : "creation"})
        self.assertRaises(NotFound, self.process, 'add/foo/bar')


    def test_nonascii_path(self):
        oldrules = SimpleReqRewriter.rules
        SimpleReqRewriter.rules = [(re.compile('/\w+', re.U), dict(vid='foo')),]
        try:
            path = str(FakeRequest().url_quote(u'été'))
            ctrl, rset = self.process(path)
            self.assertEquals(rset, None)
            self.assertEquals(self.req.form, {'vid' : "foo"})
        finally:
            SimpleReqRewriter.rules = oldrules


if __name__ == '__main__':
    unittest_main()
