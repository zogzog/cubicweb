"""map standard cubicweb schema to xml vocabularies

:organization: Logilab
:copyright: 2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

from yams import xy

xy.register_prefix('http://purl.org/dc/elements/1.1/', 'dc')
xy.register_prefix('http://xmlns.com/foaf/0.1/', 'foaf')
xy.register_prefix('http://usefulinc.com/ns/doap#', 'doap')

xy.add_equivalence('creation_date', 'dc:date')
xy.add_equivalence('created_by', 'dc:creator')
xy.add_equivalence('description', 'dc:description')
xy.add_equivalence('CWUser', 'foaf:Person')
xy.add_equivalence('CWUser.login', 'dc:title')
xy.add_equivalence('CWUser.surname', 'foaf:Person.foaf:name')
