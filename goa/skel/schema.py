"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from cubicweb.schema import format_constraint

class Blog(EntityType):
    title = String(maxsize=50, required=True)
    description = String()

class BlogEntry(EntityType):
    title = String(maxsize=100, required=True)
    publish_date = Date(default='TODAY')
    text_format = String(meta=True, internationalizable=True, maxsize=50,
                         default='text/rest', constraints=[format_constraint])
    text = String(fulltextindexed=True)
    category = String(vocabulary=('important','business'))
    entry_of = SubjectRelation('Blog', cardinality='?*')
