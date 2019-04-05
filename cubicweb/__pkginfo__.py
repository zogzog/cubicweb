# pylint: disable=W0622,C0103
# copyright 2003-2014 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""cubicweb global packaging information for the cubicweb knowledge management
software
"""

modname = distname = "cubicweb"

numversion = (3, 26, 9)
version = '.'.join(str(num) for num in numversion)

description = "a repository of entities / relations for knowledge management"
author = "Logilab"
author_email = "contact@logilab.fr"
web = 'https://www.cubicweb.org'
license = 'LGPL'

classifiers = [
    'Environment :: Web Environment',
    'Framework :: CubicWeb',
    'Programming Language :: Python',
    'Programming Language :: JavaScript',
]

# data files that shall be copied into the main package directory
package_data = {
    'cubicweb.web.views': ['*.pt'],
    'cubicweb.pyramid': ['development.ini.tmpl'],
}
