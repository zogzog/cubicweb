"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from cubicweb.devtools.testlib import WebTest
from cubicweb.devtools.htmlparser import DTDValidator


class LogFormTemplateTC(WebTest):

    def _login_labels(self):
        valid = self.content_type_validators.get('text/html', DTDValidator)()
        page = valid.parse_string(self.vreg['views'].main_template(self.request(), 'login'))
        return page.find_tag('label')

    def test_label(self):
        self.set_option('allow-email-login', 'yes')
        self.assertEquals(self._login_labels(), ['login or email', 'password'])
        self.set_option('allow-email-login', 'no')
        self.assertEquals(self._login_labels(), ['login', 'password'])
