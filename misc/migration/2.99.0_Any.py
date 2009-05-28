"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from cubicweb import CW_MIGRATION_MAP

for pk, in rql('Any K WHERE X is CWProperty, X pkey IN (%s), X pkey K'
               % ','.join("'system.version.%s'" % cube for cube in CW_MIGRATION_MAP),
               ask_confirm=False):
    cube = pk.split('.')[-1]
    newk = pk.replace(cube, CW_MIGRATION_MAP[cube])
    rql('SET X pkey %(newk)s WHERE X pkey %(oldk)s',
        {'oldk': pk, 'newk': newk}, ask_confirm=False)
    print 'renamed', pk, 'to', newk

add_entity_type('CWCache')
