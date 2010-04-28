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
"""authentication using google authentication service

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
