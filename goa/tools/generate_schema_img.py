# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""

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
