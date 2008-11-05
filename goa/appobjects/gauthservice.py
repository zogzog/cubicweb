"""authentication using google authentication service

:organization: Logilab
:copyright: 2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.common.registerers import priority_registerer
from cubicweb.web.views.basecomponents import UserLink
from cubicweb.web.views.actions import LogoutAction

from google.appengine.api import users


class use_google_auth_registerer(priority_registerer):
    """register object if use-google-auth is true"""
    
    def do_it_yourself(self, registered):
        if not hasattr(self.config, 'has_resource'):
            return
        return super(use_google_auth_registerer, self).do_it_yourself(registered)


class GAEUserLink(UserLink):
    __registerer__ = use_google_auth_registerer

    def anon_user_link(self):
        self.w(self.req._('anonymous'))
        self.w(u'&nbsp;[<a class="logout" href="%s">%s</a>]'
               % (users.create_login_url(self.req.url()), self.req._('login')))

class GAELogoutAction(LogoutAction):
    __registerer__ = use_google_auth_registerer

    def url(self):
        return users.create_logout_url(self.req.build_url('logout') )
