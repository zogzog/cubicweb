# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""some constants and classes to define schema permissions"""



from cubicweb.schema import RO_REL_PERMS, RO_ATTR_PERMS, \
     PUB_SYSTEM_ENTITY_PERMS, PUB_SYSTEM_REL_PERMS, \
     ERQLExpression, RRQLExpression

# permissions for "meta" entity type (readable by anyone, can only be
# added/deleted by managers)
META_ETYPE_PERMS = PUB_SYSTEM_ENTITY_PERMS # XXX deprecates
# permissions for "meta" relation type (readable by anyone, can only be
# added/deleted by managers)
META_RTYPE_PERMS = PUB_SYSTEM_REL_PERMS # XXX deprecates
# permissions for relation type that should only set by hooks using unsafe
# execute, readable by anyone
HOOKS_RTYPE_PERMS = RO_REL_PERMS # XXX deprecates
