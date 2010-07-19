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
"""

"""
from cubicweb.web import Redirect
from cubicweb.web.application import CubicWebPublisher

# proof of concept : monkey patch publish method so that if we are in an
# anonymous session and __fblogin is found is req.form, the user with the
# given login is created if necessary and then a session is opened for that
# user
# NOTE: this require "cookie" authentication mode
def auto_login_publish(self, path, req):
    if (not req.cnx or req.cnx.anonymous_connection) and req.form.get('__fblogin'):
        login = password = req.form.pop('__fblogin')
        self.repo.register_user(login, password)
        req.form['__login'] = login
        req.form['__password'] = password
        if req.cnx:
            req.cnx.close()
        req.cnx = None
        try:
            self.session_handler.set_session(req)
        except Redirect:
            pass
        assert req.user.login == login
    return orig_publish(self, path, req)

orig_publish = CubicWebPublisher.main_publish
CubicWebPublisher.main_publish = auto_login_publish
