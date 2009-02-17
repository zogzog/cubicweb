"""authentication using google authentication service

:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.web.views.basecomponents import UserLink
from cubicweb.web.views.actions import LogoutAction

from google.appengine.api import users


class GAEUserLink(UserLink):

    def anon_user_link(self):
        self.w(self.req._('anonymous'))
        self.w(u'&nbsp;[<a class="logout" href="%s">%s</a>]'
               % (users.create_login_url(self.req.url()), self.req._('login')))

class GAELogoutAction(LogoutAction):

    def url(self):
        return users.create_logout_url(self.req.build_url('logout') )
    
def registration_callback(vreg):
    if hasattr(vreg.config, 'has_resource'):
        vreg.register(GAEUserLink, clear=True)
        vreg.register(GAELogoutAction, clear=True)
