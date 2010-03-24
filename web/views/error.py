"""Set of HTML errors views. Error view are generally implemented
as startup views and are used for standard error pages (404, 500, etc.)

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from cubicweb.view import StartupView

class FourOhFour(StartupView):
    __regid__ = '404'

    def call(self):
        _ = self._cw._
        self.w(u"<h1>%s</h1>" % _('this resource does not exist'))


class ErrorOccured(StartupView):
    __regid__ = '500'

    def call(self):
        _ = self._cw._
        self.w(u"<h1>%s</h1>" %
               _('an error occured, the request cannot be fulfilled'))
