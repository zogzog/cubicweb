"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from yams.buildobjs import EntityType, RelationType, SubjectRelation
from cubicweb.schema import ERQLExpression

class ToTo(EntityType):
    __permissions__ = {
        'read': ('managers',),
        'add': ('managers',),
        'update': ('managers',),
        'delete': ('managers',),
        }
    toto = SubjectRelation('TuTu')

class TuTu(EntityType):
    __permissions__ = {
        'read': ('managers',),
        'add': ('managers',),
        'update': ('managers',),
        'delete': ('managers',),
        }

class toto(RelationType):
    __permissions__ = {
        'read': ('managers', ),
        'add': ('managers', ERQLExpression('S bla Y'),),
        'delete': ('managers',),
        }
