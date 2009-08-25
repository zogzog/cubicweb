"""authentication using google authentication service

:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb.web.views.basecomponents import UserLink
from cubicweb.web.views.actions import LogoutAction

from google.appengine.api import users


class GACWUserLink(UserLink):

    def anon_user_link(self):
        self.w(self.req._('anonymous'))
        self.w(u'&#160;[<a class="logout" href="%s">%s</a>]'
               % (users.create_login_url(self.req.url()), self.req._('login')))

class GAELogoutAction(LogoutAction):

    def url(self):
        return users.create_logout_url(self.req.build_url('logout') )

def registration_callback(vreg):
    if hasattr(vreg.config, 'has_resource'):
        vreg.register(GACWUserLink, clear=True)
        vreg.register(GAELogoutAction, clear=True)
