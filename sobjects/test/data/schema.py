"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from yams.buildobjs import RelationDefinition

class comments(RelationDefinition):
    subject = 'Comment'
    object = 'Card'
    cardinality='1*'
    composite='object'

