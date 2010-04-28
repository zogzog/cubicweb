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
class Schema :

    def __init__(self, schema) :
        self._schema = schema

    def get_attrs(self, entity) :
        return self._schema[entity][0]

    def get_relations(self, entity) :
        return self._schema[entity][1]

    def get_attr_index(self, entity, attr) :
        return list(self._schema[entity][0]).index(attr)

SCHEMA = Schema({'societe': ( ('nom','ville'),
                              [('concerne_par','affaire'),
                               ] ),
                 'affaire': ( ('ref',),
                              [('concerne','societe'),
                               ('concerne_par', 'document')
                               ] ),
                 'document':( ('fichier', 'annee','mois','jour','type'),
                              [('concerne','affaire'),
                               ] ),
                 })



DATA = { 'societe': [ ('CETIAD', 'Dijon'),
                      ('EDF_R&D', 'Clamart'),
                      ('Logilab', 'Paris'),
                      ],
         'affaire': [ ('CTIA01', 'CETIAD'),
                      ('EDFR01', 'EDF_R&D'),
                      ('EDFR02', 'EDF_R&D'),
                      ],
         'document':[ ('CTIA01-040906-PRE-1-01.pdf','2004','09','06','PRE','CTIA01'),
                      ('EDFR01-050201-CLI-1-01.pdf','2005','02','01','CLI','EDFR01'),
                      ('EDFR01-050322-OFR-1-01.pdf','2005','03','22','OFR','EDFR01'),
                      ],
         }

def get_data(entity, where=[]) :
    for value in DATA[entity] :
        for index, val in where :
            if value[index] != val :
                break
        else :
            yield value

class PathParser :

    def __init__(self, schema, path) :
        self.schema = schema
        self.path = path
        self._components = iter([comp for comp in self.path.split('/') if comp])
        self._entity = None
        self._attr = None
        self._rel = None
        self._restrictions = []

    def parse(self) :
        self._entity = self._components.next()
        try:
            self.process_entity()
        except StopIteration :
            pass

    def process_entity(self) :
        _next = self._components.next()
        if _next in self.schema.get_attrs(self._entity) :
            self._attr = _next
            _next = self._components.next()
            self._restrictions.append( (self._entity, self._attr, _next) )
            self._attr = None
            self._rel = None
            self.process_entity()

    def get_list(self) :
        if self._rel :
            return
        elif self._attr :
            where = []
            for e,a,v in self._restrictions :
                i = self.schema.get_attr_index(e, a)
                where.append( (i,v) )
            i = self.schema.get_attr_index(self._entity, self._attr)
            for values in get_data(self._entity,where) :
                yield values[i]+'/'
        else :
            attr_restrict = [a for e,a,v in self._restrictions]
            for attr in self.schema.get_attrs(self._entity) :
                if attr not in attr_restrict :
                    yield attr+'/'
            for data in DATA[self._entity]:
                yield data[0]
            for nom, entity in self.schema.get_relations(self._entity) :
                yield nom+'/'
                yield entity+'/'

def ls(path) :
    p = PathParser(SCHEMA,path)
    p.parse()
    return list(p.get_list())


class SytPathParser :

    def __init__(self, schema, path) :
        self.schema = schema
        self.path = path
        self._components = iter([comp for comp in self.path.split('/') if comp])
        self._e_type = None
        self._restrictions = []
        self._alphabet = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

    def parse(self):
        self._var = self._alphabet.pop(0)
        self._e_type = self._components.next()
        e_type = self._e_type.capitalize()
        self._restrictions.append('%s is %s' % (self._var, e_type))
        try:
            self.process_entity()
        except StopIteration :
            pass
        return 'Any %s WHERE %s' % (self._var, ', '.join(self._restrictions))

    def process_entity(self) :
        _next = self._components.next()
        if _next in self.schema.get_attrs(self._e_type) :
            attr = _next
            try:
                _next = self._components.next()
                self._restrictions.append('%s %s %s' % (self._var, attr, _next))
            except StopIteration:
                a_var = self._alphabet.pop(0)
                self._restrictions.append('%s %s %s' % (self._var, attr, a_var) )
                self._var = a_var
                raise
        elif _next in [r for r,e in self.schema.get_relations(self._e_type)]:
            rel = _next
            r_var = self._alphabet.pop(0)
            self._restrictions.append('%s %s %s' % (self._var, rel, r_var))
            self._var = r_var
            try:
                _next = self._components.next()
                self._restrictions.append('%s is %s' % (r_var, _next.capitalize()))
            except StopIteration:
                raise
        self.process_entity()


def to_rql(path) :
    p = SytPathParser(SCHEMA,path)
    return p.parse()

