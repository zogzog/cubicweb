"""only for unit tests !

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from cubicweb.view import EntityView
from cubicweb.selectors import implements

HTML_PAGE = u"""<html>
  <body>
    <h1>Hello World !</h1>
  </body>
</html>
"""

class SimpleView(EntityView):
    id = 'simple'
    __select__ = implements('Bug',)

    def call(self, **kwargs):
        self.cell_call(0, 0)

    def cell_call(self, row, col):
        self.w(HTML_PAGE)

class RaisingView(EntityView):
    id = 'raising'
    __select__ = implements('Bug',)

    def cell_call(self, row, col):
        raise ValueError()
