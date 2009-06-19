"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
import sys
from os.path import dirname, abspath, join
from yams import schema2dot
from cubicweb.web.views.schema import SKIP_TYPES

APPLROOT = abspath(join(dirname(abspath(__file__)), '..'))

try:
    import custom
except ImportError:
    sys.path.insert(0, APPLROOT)
    import custom


schema = custom.SCHEMA
skip_rels = ('owned_by', 'created_by', 'identity', 'is', 'is_instance_of')
path = join(APPLROOT, 'data', 'schema.png')
schema2dot.schema2dot(schema, path, #size=size,
                      skiptypes=SKIP_TYPES)
print 'generated', path
path = join(APPLROOT, 'data', 'metaschema.png')
schema2dot.schema2dot(schema, path)
print 'generated', path
