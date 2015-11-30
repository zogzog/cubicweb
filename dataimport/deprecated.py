# copyright 2003-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Old and deprecated dataimport API that provides tools to import tabular data.


Example of use (run this with `cubicweb-ctl shell instance import-script.py`):

.. sourcecode:: python

  from cubicweb.dataimport import *
  # define data generators
  GENERATORS = []

  USERS = [('Prenom', 'firstname', ()),
           ('Nom', 'surname', ()),
           ('Identifiant', 'login', ()),
           ]

  def gen_users(ctl):
      for row in ctl.iter_and_commit('utilisateurs'):
          entity = mk_entity(row, USERS)
          entity['upassword'] = 'motdepasse'
          ctl.check('login', entity['login'], None)
          entity = ctl.store.prepare_insert_entity('CWUser', **entity)
          email = ctl.store.prepare_insert_entity('EmailAddress', address=row['email'])
          ctl.store.prepare_insert_relation(entity, 'use_email', email)
          ctl.store.rql('SET U in_group G WHERE G name "users", U eid %(x)s', {'x': entity})

  CHK = [('login', check_doubles, 'Utilisateurs Login',
          'Deux utilisateurs ne devraient pas avoir le meme login.'),
         ]

  GENERATORS.append( (gen_users, CHK) )

  # create controller
  ctl = CWImportController(RQLObjectStore(cnx))
  ctl.askerror = 1
  ctl.generators = GENERATORS
  ctl.data['utilisateurs'] = lazytable(ucsvreader(open('users.csv')))
  # run
  ctl.run()

.. BUG file with one column are not parsable
.. TODO rollback() invocation is not possible yet
"""
from __future__ import print_function

import sys
import traceback
from io import StringIO

from six import add_metaclass

from logilab.common import attrdict, shellutils
from logilab.common.date import strptime
from logilab.common.deprecation import deprecated, class_deprecated

from cubicweb import QueryError
from cubicweb.dataimport import callfunc_every


@deprecated('[3.21] deprecated')
def lazytable(reader):
    """The first row is taken to be the header of the table and
    used to output a dict for each row of data.

    >>> data = lazytable(ucsvreader(open(filename)))
    """
    header = next(reader)
    for row in reader:
        yield dict(zip(header, row))


@deprecated('[3.21] deprecated')
def lazydbtable(cu, table, headers, orderby=None):
    """return an iterator on rows of a sql table. On each row, fetch columns
    defined in headers and return values as a dictionary.

    >>> data = lazydbtable(cu, 'experimentation', ('id', 'nickname', 'gps'))
    """
    sql = 'SELECT %s FROM %s' % (','.join(headers), table,)
    if orderby:
        sql += ' ORDER BY %s' % ','.join(orderby)
    cu.execute(sql)
    while True:
        row = cu.fetchone()
        if row is None:
            break
        yield dict(zip(headers, row))


@deprecated('[3.21] deprecated')
def tell(msg):
    print(msg)


@deprecated('[3.21] deprecated')
def confirm(question):
    """A confirm function that asks for yes/no/abort and exits on abort."""
    answer = shellutils.ASK.ask(question, ('Y', 'n', 'abort'), 'Y')
    if answer == 'abort':
        sys.exit(1)
    return answer == 'Y'


@add_metaclass(class_deprecated)
class catch_error(object):
    """Helper for @contextmanager decorator."""
    __deprecation_warning__ = '[3.21] deprecated'

    def __init__(self, ctl, key='unexpected error', msg=None):
        self.ctl = ctl
        self.key = key
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if type is not None:
            if issubclass(type, (KeyboardInterrupt, SystemExit)):
                return # re-raise
            if self.ctl.catcherrors:
                self.ctl.record_error(self.key, None, type, value, traceback)
                return True # silent

@deprecated('[3.21] deprecated')
def mk_entity(row, map):
    """Return a dict made from sanitized mapped values.

    ValueError can be raised on unexpected values found in checkers

    >>> row = {'myname': u'dupont'}
    >>> map = [('myname', u'name', (call_transform_method('title'),))]
    >>> mk_entity(row, map)
    {'name': u'Dupont'}
    >>> row = {'myname': u'dupont', 'optname': u''}
    >>> map = [('myname', u'name', (call_transform_method('title'),)),
    ...        ('optname', u'MARKER', (optional,))]
    >>> mk_entity(row, map)
    {'name': u'Dupont', 'optname': None}
    """
    res = {}
    assert isinstance(row, dict)
    assert isinstance(map, list)
    for src, dest, funcs in map:
        try:
            res[dest] = row[src]
        except KeyError:
            continue
        try:
            for func in funcs:
                res[dest] = func(res[dest])
                if res[dest] is None:
                    break
        except ValueError as err:
            exc = ValueError('error with %r field: %s' % (src, err))
            exc.__traceback__ = sys.exc_info()[-1]
            raise exc
    return res


# base sanitizing/coercing functions ###########################################

@deprecated('[3.21] deprecated')
def optional(value):
    """checker to filter optional field

    If value is undefined (ex: empty string), return None that will
    break the checkers validation chain

    General use is to add 'optional' check in first condition to avoid
    ValueError by further checkers

    >>> MAPPER = [(u'value', 'value', (optional, int))]
    >>> row = {'value': u'XXX'}
    >>> mk_entity(row, MAPPER)
    {'value': None}
    >>> row = {'value': u'100'}
    >>> mk_entity(row, MAPPER)
    {'value': 100}
    """
    if value:
        return value
    return None


@deprecated('[3.21] deprecated')
def required(value):
    """raise ValueError if value is empty

    This check should be often found in last position in the chain.
    """
    if value:
        return value
    raise ValueError("required")


@deprecated('[3.21] deprecated')
def todatetime(format='%d/%m/%Y'):
    """return a transformation function to turn string input value into a
    `datetime.datetime` instance, using given format.

    Follow it by `todate` or `totime` functions from `logilab.common.date` if
    you want a `date`/`time` instance instead of `datetime`.
    """
    def coerce(value):
        return strptime(value, format)
    return coerce


@deprecated('[3.21] deprecated')
def call_transform_method(methodname, *args, **kwargs):
    """return value returned by calling the given method on input"""
    def coerce(value):
        return getattr(value, methodname)(*args, **kwargs)
    return coerce


@deprecated('[3.21] deprecated')
def call_check_method(methodname, *args, **kwargs):
    """check value returned by calling the given method on input is true,
    else raise ValueError
    """
    def check(value):
        if getattr(value, methodname)(*args, **kwargs):
            return value
        raise ValueError('%s not verified on %r' % (methodname, value))
    return check


# base integrity checking functions ############################################

@deprecated('[3.21] deprecated')
def check_doubles(buckets):
    """Extract the keys that have more than one item in their bucket."""
    return [(k, len(v)) for k, v in buckets.items() if len(v) > 1]


@deprecated('[3.21] deprecated')
def check_doubles_not_none(buckets):
    """Extract the keys that have more than one item in their bucket."""
    return [(k, len(v)) for k, v in buckets.items()
            if k is not None and len(v) > 1]


@add_metaclass(class_deprecated)
class ObjectStore(object):
    """Store objects in memory for *faster* validation (development mode)

    But it will not enforce the constraints of the schema and hence will miss some problems

    >>> store = ObjectStore()
    >>> user = store.prepare_insert_entity('CWUser', login=u'johndoe')
    >>> group = store.prepare_insert_entity('CWUser', name=u'unknown')
    >>> store.prepare_insert_relation(user, 'in_group', group)
    """
    __deprecation_warning__ = '[3.21] use the new importer API'

    def __init__(self):
        self.items = []
        self.eids = {}
        self.types = {}
        self.relations = set()
        self.indexes = {}

    def prepare_insert_entity(self, etype, **data):
        """Given an entity type, attributes and inlined relations, return an eid for the entity that
        would be inserted with a real store.
        """
        data = attrdict(data)
        data['eid'] = eid = len(self.items)
        self.items.append(data)
        self.eids[eid] = data
        self.types.setdefault(etype, []).append(eid)
        return eid

    def prepare_update_entity(self, etype, eid, **kwargs):
        """Given an entity type and eid, updates the corresponding fake entity with specified
        attributes and inlined relations.
        """
        assert eid in self.types[etype], 'Trying to update with wrong type %s' % etype
        data = self.eids[eid]
        data.update(kwargs)

    def prepare_insert_relation(self, eid_from, rtype, eid_to, **kwargs):
        """Store into the `relations` attribute that a relation ``rtype`` exists between entities
        with eids ``eid_from`` and ``eid_to``.
        """
        relation = eid_from, rtype, eid_to
        self.relations.add(relation)
        return relation

    def flush(self):
        """Nothing to flush for this store."""
        pass

    def commit(self):
        """Nothing to commit for this store."""
        return

    def finish(self):
        """Nothing to do once import is terminated for this store."""
        pass

    @property
    def nb_inserted_entities(self):
        return len(self.eids)

    @property
    def nb_inserted_types(self):
        return len(self.types)

    @property
    def nb_inserted_relations(self):
        return len(self.relations)

    @deprecated('[3.21] use prepare_insert_entity instead')
    def create_entity(self, etype, **data):
        self.prepare_insert_entity(etype, **data)
        return attrdict(data)

    @deprecated('[3.21] use prepare_insert_relation instead')
    def relate(self, eid_from, rtype, eid_to, **kwargs):
        self.prepare_insert_relation(eid_from, rtype, eid_to, **kwargs)


@add_metaclass(class_deprecated)
class CWImportController(object):
    """Controller of the data import process.

    >>> ctl = CWImportController(store)
    >>> ctl.generators = list_of_data_generators
    >>> ctl.data = dict_of_data_tables
    >>> ctl.run()
    """
    __deprecation_warning__ = '[3.21] use the new importer API'

    def __init__(self, store, askerror=0, catcherrors=None, tell=tell,
                 commitevery=50):
        self.store = store
        self.generators = None
        self.data = {}
        self.errors = None
        self.askerror = askerror
        if  catcherrors is None:
            catcherrors = askerror
        self.catcherrors = catcherrors
        self.commitevery = commitevery # set to None to do a single commit
        self._tell = tell

    def check(self, type, key, value):
        self._checks.setdefault(type, {}).setdefault(key, []).append(value)

    def check_map(self, entity, key, map, default):
        try:
            entity[key] = map[entity[key]]
        except KeyError:
            self.check(key, entity[key], None)
            entity[key] = default

    def record_error(self, key, msg=None, type=None, value=None, tb=None):
        tmp = StringIO()
        if type is None:
            traceback.print_exc(file=tmp)
        else:
            traceback.print_exception(type, value, tb, file=tmp)
        # use a list to avoid counting a <nb lines> errors instead of one
        errorlog = self.errors.setdefault(key, [])
        if msg is None:
            errorlog.append(tmp.getvalue().splitlines())
        else:
            errorlog.append( (msg, tmp.getvalue().splitlines()) )

    def run(self):
        self.errors = {}
        if self.commitevery is None:
            self.tell('Will commit all or nothing.')
        else:
            self.tell('Will commit every %s iterations' % self.commitevery)
        for func, checks in self.generators:
            self._checks = {}
            func_name = func.__name__
            self.tell("Run import function '%s'..." % func_name)
            try:
                func(self)
            except Exception:
                if self.catcherrors:
                    self.record_error(func_name, 'While calling %s' % func.__name__)
                else:
                    self._print_stats()
                    raise
            for key, func, title, help in checks:
                buckets = self._checks.get(key)
                if buckets:
                    err = func(buckets)
                    if err:
                        self.errors[title] = (help, err)
        try:
            txuuid = self.store.commit()
            if txuuid is not None:
                self.tell('Transaction commited (txuuid: %s)' % txuuid)
        except QueryError as ex:
            self.tell('Transaction aborted: %s' % ex)
        self._print_stats()
        if self.errors:
            if self.askerror == 2 or (self.askerror and confirm('Display errors ?')):
                from pprint import pformat
                for errkey, error in self.errors.items():
                    self.tell("\n%s (%s): %d\n" % (error[0], errkey, len(error[1])))
                    self.tell(pformat(sorted(error[1])))

    def _print_stats(self):
        nberrors = sum(len(err) for err in self.errors.values())
        self.tell('\nImport statistics: %i entities, %i types, %i relations and %i errors'
                  % (self.store.nb_inserted_entities,
                     self.store.nb_inserted_types,
                     self.store.nb_inserted_relations,
                     nberrors))

    def get_data(self, key):
        return self.data.get(key)

    def index(self, name, key, value, unique=False):
        """create a new index

        If unique is set to True, only first occurence will be kept not the following ones
        """
        if unique:
            try:
                if value in self.store.indexes[name][key]:
                    return
            except KeyError:
                # we're sure that one is the first occurence; so continue...
                pass
        self.store.indexes.setdefault(name, {}).setdefault(key, []).append(value)

    def tell(self, msg):
        self._tell(msg)

    def iter_and_commit(self, datakey):
        """iter rows, triggering commit every self.commitevery iterations"""
        if self.commitevery is None:
            return self.get_data(datakey)
        else:
            return callfunc_every(self.store.commit,
                                  self.commitevery,
                                  self.get_data(datakey))
