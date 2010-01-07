# -*- coding: utf-8 -*-
"""This module provides tools to import tabular data.

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses


Example of use (run this with `cubicweb-ctl shell instance import-script.py`):

.. sourcecode:: python

  from cubicweb.devtools.dataimport import *
  # define data generators
  GENERATORS = []

  USERS = [('Prenom', 'firstname', ()),
           ('Nom', 'surname', ()),
           ('Identifiant', 'login', ()),
           ]

  def gen_users(ctl):
      for row in ctl.get_data('utilisateurs'):
          entity = mk_entity(row, USERS)
          entity['upassword'] = u'motdepasse'
          ctl.check('login', entity['login'], None)
          ctl.store.add('CWUser', entity)
          email = {'address': row['email']}
          ctl.store.add('EmailAddress', email)
          ctl.store.relate(entity['eid'], 'use_email', email['eid'])
          ctl.store.rql('SET U in_group G WHERE G name "users", U eid %(x)s', {'x':entity['eid']})

  CHK = [('login', check_doubles, 'Utilisateurs Login',
          'Deux utilisateurs ne devraient pas avoir le même login.'),
         ]

  GENERATORS.append( (gen_users, CHK) )

  # create controller
  ctl = CWImportController(RQLObjectStore())
  ctl.askerror = True
  ctl.generators = GENERATORS
  ctl.store._checkpoint = checkpoint
  ctl.store._rql = rql
  ctl.data['utilisateurs'] = lazytable(utf8csvreader(open('users.csv')))
  # run
  ctl.run()
  sys.exit(0)

"""
__docformat__ = "restructuredtext en"

import sys, csv, traceback

from logilab.common import shellutils

def utf8csvreader(file, encoding='utf-8', separator=',', quote='"'):
    """A csv reader that accepts files with any encoding and outputs
    unicode strings."""
    for row in csv.reader(file, delimiter=separator, quotechar=quote):
        yield [item.decode(encoding) for item in row]

def lazytable(reader):
    """The first row is taken to be the header of the table and
    used to output a dict for each row of data.

    >>> data = lazytable(utf8csvreader(open(filename)))
    """
    header = reader.next()
    for row in reader:
        yield dict(zip(header, row))

def tell(msg):
    print msg

# base sanitizing functions #####

def capitalize_if_unicase(txt):
    if txt.isupper() or txt.islower():
        return txt.capitalize()
    return txt

def no_space(txt):
    return txt.replace(' ','')

def no_uspace(txt):
    return txt.replace(u'\xa0','')

def no_dash(txt):
    return txt.replace('-','')

def alldigits(txt):
    if txt.isdigit():
        return txt
    else:
        return u''

def strip(txt):
    return txt.strip()

# base checks #####

def check_doubles(buckets):
    """Extract the keys that have more than one item in their bucket."""
    return [(key, len(value)) for key,value in buckets.items() if len(value) > 1]

# make entity helper #####

def mk_entity(row, map):
    """Return a dict made from sanitized mapped values.

    >>> row = {'myname': u'dupont'}
    >>> map = [('myname', u'name', (capitalize_if_unicase,))]
    >>> mk_entity(row, map)
    {'name': u'Dupont'}
    """
    res = {}
    for src, dest, funcs in map:
        res[dest] = row[src]
        for func in funcs:
            res[dest] = func(res[dest])
    return res

# object stores

class ObjectStore(object):
    """Store objects in memory for faster testing. Will not
    enforce the constraints of the schema and hence will miss
    some problems.

    >>> store = ObjectStore()
    >>> user = {'login': 'johndoe'}
    >>> store.add('CWUser', user)
    >>> group = {'name': 'unknown'}
    >>> store.add('CWUser', group)
    >>> store.relate(user['eid'], 'in_group', group['eid'])
    """

    def __init__(self):
        self.items = []
        self.eids = {}
        self.types = {}
        self.relations = set()
        self.indexes = {}
        self._rql = None
        self._checkpoint = None

    def _put(self, type, item):
        self.items.append(item)
        return len(self.items) - 1

    def add(self, type, item):
        assert isinstance(item, dict), 'item is not a dict but a %s' % type(item)
        eid = item['eid'] = self._put(type, item)
        self.eids[eid] = item
        self.types.setdefault(type, []).append(eid)

    def relate(self, eid_from, rtype, eid_to):
        eids_valid = (eid_from < len(self.items) and eid_to <= len(self.items))
        assert eids_valid, 'eid error %s %s' % (eid_from, eid_to)
        self.relations.add( (eid_from, rtype, eid_to) )

    def build_index(self, name, type, func):
        index = {}
        for eid in self.types[type]:
            index.setdefault(func(self.eids[eid]), []).append(eid)
        self.indexes[name] = index

    def get_many(self, name, key):
        return self.indexes[name].get(key, [])

    def get_one(self, name, key):
        eids = self.indexes[name].get(key, [])
        assert len(eids) == 1, 'expected a single one got %i' % len(eids)
        return eids[0]

    def find(self, type, key, value):
        for idx in self.types[type]:
            item = self.items[idx]
            if item[key] == value:
                yield item

    def rql(self, query, args):
        if self._rql:
            return self._rql(query, args)

    def checkpoint(self):
        if self._checkpoint:
            self._checkpoint()

class RQLObjectStore(ObjectStore):
    """ObjectStore that works with an actual RQL repository."""

    def _put(self, type, item):
        query = ('INSERT %s X: ' % type) + ', '.join(['X %s %%(%s)s' % (key,key) for key in item])
        return self.rql(query, item)[0][0]

    def relate(self, eid_from, rtype, eid_to):
        query = 'SET X %s Y WHERE X eid %%(from)s, Y eid %%(to)s' % rtype
        self.rql(query, {'from': int(eid_from), 'to': int(eid_to)})
        self.relations.add( (eid_from, rtype, eid_to) )

# import controller #####

class CWImportController(object):
    """Controller of the data import process.

    >>> ctl = CWImportController(store)
    >>> ctl.generators = list_of_data_generators
    >>> ctl.data = dict_of_data_tables
    >>> ctl.run()
    """

    def __init__(self, store):
        self.store = store
        self.generators = None
        self.data = {}
        self.errors = None
        self.askerror = False
        self._tell = tell

    def check(self, type, key, value):
        self._checks.setdefault(type, {}).setdefault(key, []).append(value)

    def check_map(self, entity, key, map, default):
        try:
            entity[key] = map[entity[key]]
        except KeyError:
            self.check(key, entity[key], None)
            entity[key] = default

    def run(self):
        self.errors = {}
        for func, checks in self.generators:
            self._checks = {}
            func_name = func.__name__[4:]
            question = 'Importation de %s' % func_name
            self.tell(question)
            try:
                func(self)
            except:
                import StringIO
                tmp = StringIO.StringIO()
                traceback.print_exc(file=tmp)
                print tmp.getvalue()
                self.errors[func_name] = ('Erreur lors de la transformation',
                                          tmp.getvalue().splitlines())
            for key, func, title, help in checks:
                buckets = self._checks.get(key)
                if buckets:
                    err = func(buckets)
                    if err:
                        self.errors[title] = (help, err)
            self.store.checkpoint()
        errors = sum(len(err[1]) for err in self.errors.values())
        self.tell('Importation terminée. (%i objets, %i types, %i relations et %i erreurs).'
                  % (len(self.store.eids), len(self.store.types),
                     len(self.store.relations), errors))
        if self.errors and self.askerror and confirm('Afficher les erreurs ?'):
            import pprint
            pprint.pprint(self.errors)

    def get_data(self, key):
        return self.data.get(key)

    def index(self, name, key, value):
        self.store.indexes.setdefault(name, {}).setdefault(key, []).append(value)

    def tell(self, msg):
        self._tell(msg)

def confirm(question):
    """A confirm function that asks for yes/no/abort and exits on abort."""
    answer = shellutils.ASK.ask(question, ('Y','n','abort'), 'Y')
    if answer == 'abort':
        sys.exit(1)
    return answer == 'Y'
