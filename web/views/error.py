"""Set of HTML errors views. Error view are generally implemented
as startup views and are used for standard error pages (404, 500, etc.)

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.view import StartupView

class FourOhFour(StartupView):
    id = '404'

    def call(self):
        _ = self.req._
        self.w(u"<h1>%s</h1>" % _('this resource does not exist'))


class ErrorOccured(StartupView):
    id = '500'

    def call(self):
        _ = self.req._
        self.w(u"<h1>%s</h1>" %
               _('an error occured, the request cannot be fulfilled'))
    

