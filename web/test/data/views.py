"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from cubicweb.web import Redirect
from cubicweb.web.application import CubicWebPublisher

# proof of concept : monkey patch publish method so that if we are in an
# anonymous session and __fblogin is found is req.form, the user with the
# given login is created if necessary and then a session is opened for that
# user
# NOTE: this require "cookie" authentication mode
def auto_login_publish(self, path, req):
    if (req.cnx is None or req.cnx.anonymous_connection) and req.form.get('__fblogin'):
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
