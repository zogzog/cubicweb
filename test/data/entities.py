"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
from cubicweb.entities import AnyEntity, fetch_config

class Societe(AnyEntity):
    __regid__ = 'Societe'
    fetch_attrs = ('nom',)

class Personne(Societe):
    """customized class forne Person entities"""
    __regid__ = 'Personne'
    fetch_attrs, fetch_order = fetch_config(['nom', 'prenom'])
    rest_attr = 'nom'


class Note(AnyEntity):
    __regid__ = 'Note'
