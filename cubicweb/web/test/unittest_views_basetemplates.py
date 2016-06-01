# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.devtools.htmlparser import XMLValidator


class LogFormTemplateTC(CubicWebTC):

    def _login_labels(self):
        valid = self.content_type_validators.get('text/html', XMLValidator)()
        req = self.requestcls(self.vreg, url='login')
        page = valid.parse_string(self.vreg['views'].main_template(req, 'login'))
        return page.find_tag('label')

    def test_label(self):
        self.set_option('allow-email-login', 'yes')
        self.assertEqual(self._login_labels(), ['login or email', 'password'])
        self.set_option('allow-email-login', 'no')
        self.assertEqual(self._login_labels(), ['login', 'password'])

    def test_display_message(self):
        with self.admin_access.web_request() as req:
            req.set_message(u'houla hop')
            page = self.view('logform', req=req, id='loginBox', klass='', template=None)
            self.assertIn(u'houla hop', page.raw_text)


class MainNoTopTemplateTC(CubicWebTC):

    def test_valid_xhtml(self):
        with self.admin_access.web_request() as req:
            self.view('index', template='main-no-top', req=req)


if __name__ == '__main__':
    from logilab.common.testlib import unittest_main
    unittest_main()
