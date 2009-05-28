"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""


class YamsEntity(EntityType):
    if 'Blog' in defined_types and 'Article' in defined_types:
        ambiguous_relation = SubjectRelation(('Blog', 'Article'))
    if 'Blog' in defined_types:
        inlined_relation = SubjectRelation('Blog', cardinality='?*')

class inlined_relation(RelationType):
    inlined = True

