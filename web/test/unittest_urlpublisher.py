# -*- coding: utf-8 -*-
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
"""Unit tests for url publishing service"""

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
        req = self.request()
        self.create_user(req, u'ÿsaÿe')
        b = req.create_entity('BlogEntry', title=u'hell\'o', content=u'blabla')
        c = req.create_entity('Tag', name=u'yo') # take care: Tag's name normalized to lower case
        self.execute('SET C tags B WHERE C eid %(c)s, B eid %(b)s', {'c':c.eid, 'b':b.eid})

    def process(self, url):
        req = self.req = self.request()
        return self.app.url_resolver.process(req, url)

    def test_raw_path(self):
        """tests raw path resolution'"""
        self.assertEqual(self.process('view'), ('view', None))
        self.assertEqual(self.process('edit'), ('edit', None))
        self.assertRaises(NotFound, self.process, 'whatever')

    def test_eid_path(self):
        """tests eid path resolution"""
        self.assertIsInstance(self.process('123')[1], ResultSet)
        self.assertEqual(len(self.process('123')[1]), 1)
        self.assertRaises(NotFound, self.process, '123/345')
        self.assertRaises(NotFound, self.process, 'not_eid')

    def test_rest_path_etype(self):
        """tests the rest path resolution"""
        ctrl, rset = self.process('CWEType')
        self.assertEqual(ctrl, 'view')
        self.assertEqual(rset.description[0][0], 'CWEType')
        self.assertEqual(rset.printable_rql(),
                          "Any X,AA,AB ORDERBY AA WHERE X is_instance_of CWEType, X name AA, X modification_date AB")

    def test_rest_path_by_attr(self):
        ctrl, rset = self.process('CWUser/login/admin')
        self.assertEqual(ctrl, 'view')
        self.assertEqual(len(rset), 1)
        self.assertEqual(rset.description[0][0], 'CWUser')
        self.assertEqual(rset.printable_rql(), 'Any X,AA,AB,AC,AD WHERE X is_instance_of CWUser, X login AA, X firstname AB, X surname AC, X modification_date AD, X login "admin"')

    def test_rest_path_unique_attr(self):
        ctrl, rset = self.process('cwuser/admin')
        self.assertEqual(ctrl, 'view')
        self.assertEqual(len(rset), 1)
        self.assertEqual(rset.description[0][0], 'CWUser')
        self.assertEqual(rset.printable_rql(), 'Any X,AA,AB,AC,AD WHERE X is_instance_of CWUser, X login AA, X firstname AB, X surname AC, X modification_date AD, X login "admin"')

    def test_rest_path_eid(self):
        ctrl, rset = self.process('cwuser/eid/%s' % self.user().eid)
        self.assertEqual(ctrl, 'view')
        self.assertEqual(len(rset), 1)
        self.assertEqual(rset.description[0][0], 'CWUser')
        self.assertEqual(rset.printable_rql(), 'Any X,AA,AB,AC,AD WHERE X is_instance_of CWUser, X login AA, X firstname AB, X surname AC, X modification_date AD, X eid %s' % rset[0][0])

    def test_rest_path_non_ascii_paths(self):
        ctrl, rset = self.process('CWUser/login/%C3%BFsa%C3%BFe')
        self.assertEqual(ctrl, 'view')
        self.assertEqual(len(rset), 1)
        self.assertEqual(rset.description[0][0], 'CWUser')
        self.assertEqual(rset.printable_rql(), u'Any X,AA,AB,AC,AD WHERE X is_instance_of CWUser, X login AA, X firstname AB, X surname AC, X modification_date AD, X login "\xffsa\xffe"')

    def test_rest_path_quoted_paths(self):
        ctrl, rset = self.process('BlogEntry/title/hell%27o')
        self.assertEqual(ctrl, 'view')
        self.assertEqual(len(rset), 1)
        self.assertEqual(rset.description[0][0], 'BlogEntry')
        self.assertEqual(rset.printable_rql(), u'Any X,AA,AB,AC WHERE X is_instance_of BlogEntry, X creation_date AA, X title AB, X modification_date AC, X title "hell\'o"')

    def test_rest_path_errors(self):
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
        self.assertEqual(ctrl, 'view')
        self.assertEqual(rset, None)
        self.assertEqual(self.req.form, {'etype' : "Task", 'vid' : "creation"})
        self.assertRaises(NotFound, self.process, 'add/foo/bar')


    def test_nonascii_path(self):
        oldrules = SimpleReqRewriter.rules
        SimpleReqRewriter.rules = [(re.compile('/\w+', re.U), dict(vid='foo')),]
        try:
            path = str(FakeRequest().url_quote(u'été'))
            ctrl, rset = self.process(path)
            self.assertEqual(rset, None)
            self.assertEqual(self.req.form, {'vid' : "foo"})
        finally:
            SimpleReqRewriter.rules = oldrules


if __name__ == '__main__':
    unittest_main()
