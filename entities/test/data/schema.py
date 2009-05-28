"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
class Company(EntityType):
    name = String()

class Division(Company):
    __specializes_schema__ = True

class SubDivision(Division):
    __specializes_schema__ = True

