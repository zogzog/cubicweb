"""html view for workflow related entities

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
