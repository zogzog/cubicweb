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
"""Set of HTML errors views. Error view are generally implemented
as startup views and are used for standard error pages (404, 500, etc.)

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
