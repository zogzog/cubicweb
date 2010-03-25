# pylint: disable-msg=W0622
"""cubicweb-file packaging information

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

distname = "cubicweb-file"
modname = distname.split('-', 1)[1]

numversion = (1, 4, 3)
version = '.'.join(str(num) for num in numversion)

