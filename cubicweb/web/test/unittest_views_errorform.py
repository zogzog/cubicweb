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
import re
import sys

from logilab.common.testlib import unittest_main

from cubicweb import Forbidden
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.view import StartupView
from cubicweb.web import Redirect


class ErrorViewTC(CubicWebTC):
    def setUp(self):
        super(ErrorViewTC, self).setUp()
        self.vreg.config['submit-mail'] = "test@logilab.fr"
        self.vreg.config['print-traceback'] = "yes"

    def test_error_generation(self):
        """
        tests
        """

        class MyWrongView(StartupView):
            __regid__ = 'my-view'
            def call(self):
                raise ValueError('This is wrong')

        with self.temporary_appobjects(MyWrongView):
            with self.admin_access.web_request() as req:
                try:
                    self.view('my-view', req=req)
                except Exception as e:
                    req.data['excinfo'] = sys.exc_info()
                    req.data['ex'] = e
                    html = self.view('error', req=req)
                    self.assertTrue(re.search(b'^<input name="__signature" type="hidden" '
                                              b'value="[0-9a-f]{128}" />$',
                                              html.source, re.M))


    def test_error_submit_nosig(self):
        """
        tests that the reportbug controller refuses submission if
        there is not content signature
        """
        with self.admin_access.web_request() as req:
            req.form = {'description': u'toto'}
            with self.assertRaises(Forbidden) as cm:
                self.ctrl_publish(req, 'reportbug')

    def test_error_submit_wrongsig(self):
        """
        tests that the reportbug controller refuses submission if the
        content signature is invalid
        """
        with self.admin_access.web_request() as req:
            req.form = {'__signature': 'X',
                        'description': u'toto'}
            with self.assertRaises(Forbidden) as cm:
                self.ctrl_publish(req, 'reportbug')

    def test_error_submit_ok(self):
        """
        tests that the reportbug controller accept the email submission if the
        content signature is valid
        """
        with self.admin_access.web_request() as req:
            sign = self.vreg.config.sign_text('toto')
            req.form = {'__signature': sign,
                        'description': u'toto'}
            with self.assertRaises(Redirect) as cm:
                self.ctrl_publish(req, 'reportbug')

if __name__ == '__main__':
    unittest_main()
