"""html view for workflow related entities

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.selectors import implements
from cubicweb.common.view import EntityView

class CellView(EntityView):
    id = 'cell'
    __select__ = implements('TrInfo')
    
    def cell_call(self, row, col, cellvid=None):
        entity = self.entity(row, col)
        self.w(entity.printable_value('comment'))


class StateInContextView(EntityView):
    """convenience trick, State's incontext view should not be clickable"""
    id = 'incontext'
    __select__ = implements('State')
    
    def cell_call(self, row, col):
        self.w(html_escape(self.view('textincontext', self.rset,
                                     row=row, col=col)))

