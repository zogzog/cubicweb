# -*- coding: utf-8 -*-
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
        with self.admin_access.repo_cnx() as cnx:
            self.create_user(cnx, u'ÿsaÿe')
            b = cnx.create_entity('BlogEntry', title=u'hell\'o', content=u'blabla')
            # take care: Tag's name normalized to lower case
            c = cnx.create_entity('Tag', name=u'yo')
            cnx.execute('SET C tags B WHERE C eid %(c)s, B eid %(b)s',
                        {'c':c.eid, 'b':b.eid})
            cnx.commit()

    def process(self, req, url):
        return self.app.url_resolver.process(req, url)

    def test_raw_path(self):
        """tests raw path resolution'"""
        with self.admin_access.web_request() as req:
            self.assertEqual(self.process(req, 'view'), ('view', None))
            self.assertEqual(self.process(req, 'edit'), ('edit', None))
            self.assertRaises(NotFound, self.process, req, 'whatever')

    def test_eid_path(self):
        """tests eid path resolution"""
        with self.admin_access.web_request() as req:
            self.assertIsInstance(self.process(req, '123')[1], ResultSet)
            self.assertEqual(len(self.process(req, '123')[1]), 1)
            self.assertRaises(NotFound, self.process, req, '123/345')
            self.assertRaises(NotFound, self.process, req, 'not_eid')

    def test_rest_path_etype(self):
        """tests the rest path resolution"""
        with self.admin_access.web_request() as req:
            ctrl, rset = self.process(req, 'CWEType')
            self.assertEqual(ctrl, 'view')
            self.assertEqual(rset.description[0][0], 'CWEType')
            self.assertEqual("Any X,AA,AB ORDERBY AA WHERE X is_instance_of CWEType, "
                             "X name AA, X modification_date AB",
                             rset.printable_rql())

    def test_rest_path_by_attr(self):
        with self.admin_access.web_request() as req:
            ctrl, rset = self.process(req, 'CWUser/login/admin')
            self.assertEqual(ctrl, 'view')
            self.assertEqual(len(rset), 1)
            self.assertEqual(rset.description[0][0], 'CWUser')
            self.assertEqual('Any X,AA,AB,AC,AD WHERE X is_instance_of CWUser, '
                             'X login AA, X firstname AB, X surname AC, '
                             'X modification_date AD, X login "admin"',
                             rset.printable_rql())

    def test_rest_path_unique_attr(self):
        with self.admin_access.web_request() as req:
            ctrl, rset = self.process(req, 'cwuser/admin')
            self.assertEqual(ctrl, 'view')
            self.assertEqual(len(rset), 1)
            self.assertEqual(rset.description[0][0], 'CWUser')
            self.assertEqual('Any X,AA,AB,AC,AD WHERE X is_instance_of CWUser, '
                             'X login AA, X firstname AB, X surname AC, '
                             'X modification_date AD, X login "admin"',
                             rset.printable_rql())

    def test_rest_path_eid(self):
        with self.admin_access.web_request() as req:
            ctrl, rset = self.process(req, 'cwuser/eid/%s' % self.user(req).eid)
            self.assertEqual(ctrl, 'view')
            self.assertEqual(len(rset), 1)
            self.assertEqual(rset.description[0][0], 'CWUser')
            self.assertEqual('Any X,AA,AB,AC,AD WHERE X is_instance_of CWUser, '
                             'X login AA, X firstname AB, X surname AC, '
                             'X modification_date AD, X eid %s' % rset[0][0],
                             rset.printable_rql())

    def test_rest_path_non_ascii_paths(self):
        with self.admin_access.web_request() as req:
            ctrl, rset = self.process(req, 'CWUser/login/%C3%BFsa%C3%BFe')
            self.assertEqual(ctrl, 'view')
            self.assertEqual(len(rset), 1)
            self.assertEqual(rset.description[0][0], 'CWUser')
            self.assertEqual(u'Any X,AA,AB,AC,AD WHERE X is_instance_of CWUser, '
                             u'X login AA, X firstname AB, X surname AC, '
                             u'X modification_date AD, X login "\xffsa\xffe"',
                             rset.printable_rql())

    def test_rest_path_quoted_paths(self):
        with self.admin_access.web_request() as req:
            ctrl, rset = self.process(req, 'BlogEntry/title/hell%27o')
            self.assertEqual(ctrl, 'view')
            self.assertEqual(len(rset), 1)
            self.assertEqual(rset.description[0][0], 'BlogEntry')
            self.assertEqual(u'Any X,AA,AB,AC WHERE X is_instance_of BlogEntry, '
                             'X creation_date AA, X title AB, X modification_date AC, '
                             'X title "hell\'o"',
                             rset.printable_rql())

    def test_rest_path_errors(self):
        with self.admin_access.web_request() as req:
            self.assertRaises(NotFound, self.process, req, 'CWUser/eid/30000')
            self.assertRaises(NotFound, self.process, req, 'Workcases')
            self.assertRaises(NotFound, self.process, req, 'CWUser/inexistant_attribute/joe')

    def test_action_path(self):
        """tests the action path resolution"""
        with self.admin_access.web_request() as req:
            self.assertRaises(Redirect, self.process, req, '1/edit')
            self.assertRaises(Redirect, self.process, req, 'Tag/name/yo/edit')
            self.assertRaises(Redirect, self.process, req, 'Tag/yo/edit')
            self.assertRaises(NotFound, self.process, req, 'view/edit')
            self.assertRaises(NotFound, self.process, req, '1/non_action')
            self.assertRaises(NotFound, self.process, req, 'CWUser/login/admin/non_action')


    def test_regexp_path(self):
        """tests the regexp path resolution"""
        with self.admin_access.web_request() as req:
            ctrl, rset = self.process(req, 'add/Task')
            self.assertEqual(ctrl, 'view')
            self.assertEqual(rset, None)
            self.assertEqual(req.form, {'etype' : "Task", 'vid' : "creation"})
            self.assertRaises(NotFound, self.process, req, 'add/foo/bar')

    def test_nonascii_path(self):
        oldrules = SimpleReqRewriter.rules
        SimpleReqRewriter.rules = [(re.compile('/\w+', re.U), dict(vid='foo')),]
        with self.admin_access.web_request() as req:
            try:
                path = str(FakeRequest().url_quote(u'été'))
                ctrl, rset = self.process(req, path)
                self.assertEqual(rset, None)
                self.assertEqual(req.form, {'vid' : "foo"})
            finally:
                SimpleReqRewriter.rules = oldrules


if __name__ == '__main__':
    unittest_main()
