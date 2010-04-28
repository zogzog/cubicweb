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
"""map standard cubicweb schema to xml vocabularies

"""

from yams import xy

xy.register_prefix('http://purl.org/dc/elements/1.1/', 'dc')
xy.register_prefix('http://xmlns.com/foaf/0.1/', 'foaf')
xy.register_prefix('http://usefulinc.com/ns/doap#', 'doap')

xy.add_equivalence('creation_date', 'dc:date')
xy.add_equivalence('created_by', 'dc:creator')
xy.add_equivalence('description', 'dc:description')
xy.add_equivalence('CWUser', 'foaf:Person')
xy.add_equivalence('CWUser login', 'dc:title')
xy.add_equivalence('CWUser surname', 'foaf:Person foaf:name')
