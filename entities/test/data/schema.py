"""entities tests schema

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from yams.buildobjs import EntityType, String
from cubicweb.schema import make_workflowable

class Company(EntityType):
    name = String()

class Division(Company):
    __specializes_schema__ = True

class SubDivision(Division):
    __specializes_schema__ = True


from cubicweb.schemas import bootstrap, Bookmark
make_workflowable(bootstrap.CWGroup)
make_workflowable(Bookmark.Bookmark)
