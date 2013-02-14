# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from logilab.common.testlib import unittest_main
from logilab.mtconverter import html_unescape

from cubicweb import Forbidden, ValidationError
from cubicweb.devtools.testlib import CubicWebTC
from cubicweb.utils import json
from cubicweb.view import StartupView, TRANSITIONAL_DOCTYPE_NOEXT
from cubicweb.web import Redirect
from cubicweb.web.htmlwidgets import TableWidget
from cubicweb.web.views import vid_from_rset

import re
import hmac

class ErrorViewTC(CubicWebTC):
    def setUp(self):
        super(ErrorViewTC, self).setUp()
        self.req = self.request()
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
            try:
                self.view('my-view')
            except Exception as e:
                import sys
                self.req.data['excinfo'] = sys.exc_info()
                self.req.data['ex'] = e
                html = self.view('error', req=self.req)
                self.failUnless(re.search(r'^<input name="__signature" type="hidden" value="[0-9a-f]{32}" />$',
                                          html.source, re.M))


    def test_error_submit_nosig(self):
        """
        tests that the reportbug controller refuses submission if
        there is not content signature
        """

        self.req.form = {'description': u'toto',
                         }
        with self.assertRaises(Forbidden) as cm:
            self.ctrl_publish(self.req, 'reportbug')

    def test_error_submit_wrongsig(self):
        """
        tests that the reportbug controller refuses submission if the
        content signature is invalid
        """

        self.req.form = {'__signature': 'X',
                         'description': u'toto',
                         }
        with self.assertRaises(Forbidden) as cm:
            self.ctrl_publish(self.req, 'reportbug')

    def test_error_submit_ok(self):
        """
        tests that the reportbug controller accept the email submission if the
        content signature is valid
        """

        sign = self.vreg.config.sign_text('toto')
        self.req.form = {'__signature': sign,
                         'description': u'toto',
                         }
        with self.assertRaises(Redirect) as cm:
            self.ctrl_publish(self.req, 'reportbug')

if __name__ == '__main__':
    unittest_main()
