"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from yams.buildobjs import EntityType, RelationType, String
from cubicweb.schema import RRQLExpression

class ToTo(EntityType):
    permissions = {
        'read': ('managers',),
        'add': ('managers',),
        'update': ('managers',),
        'delete': ('managers',),
        }
    attr = String()

class attr(RelationType):
    permissions = {
        'read': ('managers', ),
        'add': ('managers', RRQLExpression('S bla Y'),),
        'delete': ('managers',),
        }
