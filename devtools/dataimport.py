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
  ctl.askerror = 1
  ctl.generators = GENERATORS
  ctl.store._checkpoint = checkpoint
  ctl.store._rql = rql
  ctl.data['utilisateurs'] = lazytable(utf8csvreader(open('users.csv')))
  # run
  ctl.run()
  sys.exit(0)


.. BUG fichier à une colonne pose un problème de parsing
.. TODO rollback()
"""
__docformat__ = "restructuredtext en"

import sys
import csv
import traceback
import os.path as osp
from StringIO import StringIO

from logilab.common import shellutils
from logilab.common.deprecation import deprecated

def ucsvreader_pb(filepath, encoding='utf-8', separator=',', quote='"',
                  skipfirst=False, withpb=True):
    """same as ucsvreader but a progress bar is displayed as we iter on rows"""
    if not osp.exists(filepath):
        raise Exception("file doesn't exists: %s" % filepath)
    rowcount = int(shellutils.Execute('wc -l "%s"' % filepath).out.strip().split()[0])
    if skipfirst:
        rowcount -= 1
    if withpb:
        pb = shellutils.ProgressBar(rowcount, 50)
    for urow in ucsvreader(file(filepath), encoding, separator, quote, skipfirst):
        yield urow
        if withpb:
            pb.update()
    print ' %s rows imported' % rowcount

def ucsvreader(stream, encoding='utf-8', separator=',', quote='"',
               skipfirst=False):
    """A csv reader that accepts files with any encoding and outputs unicode
    strings
    """
    it = iter(csv.reader(stream, delimiter=separator, quotechar=quote))
    if skipfirst:
        it.next()
    for row in it:
        yield [item.decode(encoding) for item in row]

utf8csvreader = deprecated('use ucsvreader instead')(ucsvreader)

def commit_every(nbit, store, it):
    for i, x in enumerate(it):
        yield x
        if nbit is not None and i % nbit:
            store.checkpoint()
    if nbit is not None:
        store.checkpoint()

def lazytable(reader):
    """The first row is taken to be the header of the table and
    used to output a dict for each row of data.

    >>> data = lazytable(utf8csvreader(open(filename)))
    """
    header = reader.next()
    for row in reader:
        yield dict(zip(header, row))

def mk_entity(row, map):
    """Return a dict made from sanitized mapped values.

    ValidationError can be raised on unexpected values found in checkers

    >>> row = {'myname': u'dupont'}
    >>> map = [('myname', u'name', (capitalize_if_unicase,))]
    >>> mk_entity(row, map)
    {'name': u'Dupont'}
    >>> row = {'myname': u'dupont', 'optname': u''}
    >>> map = [('myname', u'name', (capitalize_if_unicase,)),
    ...        ('optname', u'MARKER', (optional,))]
    >>> mk_entity(row, map)
    {'name': u'Dupont'}
    """
    res = {}
    assert isinstance(row, dict)
    assert isinstance(map, list)
    for src, dest, funcs in map:
        assert not (required in funcs and optional in funcs), "optional and required checks are exclusive"
        res[dest] = row[src]
        try:
            for func in funcs:
                res[dest] = func(res[dest])
            if res[dest] is None:
                raise AssertionError('undetermined value')
        except AssertionError, err:
            if optional in funcs:
                # Forget this field if exception is coming from optional function
               del res[dest]
            else:
               raise AssertionError('error with "%s" field: %s' % (src, err))
    return res


# user interactions ############################################################

def tell(msg):
    print msg

def confirm(question):
    """A confirm function that asks for yes/no/abort and exits on abort."""
    answer = shellutils.ASK.ask(question, ('Y','n','abort'), 'Y')
    if answer == 'abort':
        sys.exit(1)
    return answer == 'Y'


class catch_error(object):
    """Helper for @contextmanager decorator."""

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


# base sanitizing functions ####################################################

def capitalize_if_unicase(txt):
    if txt.isupper() or txt.islower():
        return txt.capitalize()
    return txt

def uppercase(txt):
    return txt.upper()

def lowercase(txt):
    return txt.lower()

def no_space(txt):
    return txt.replace(' ','')

def no_uspace(txt):
    return txt.replace(u'\xa0','')

def no_dash(txt):
    return txt.replace('-','')

def decimal(value):
    """cast to float but with comma replacement

    We take care of some locale format as replacing ',' by '.'"""
    value = value.replace(',', '.')
    try:
        return float(value)
    except Exception, err:
        raise AssertionError(err)

def integer(value):
    try:
        return int(value)
    except Exception, err:
        raise AssertionError(err)

def strip(txt):
    return txt.strip()

def yesno(value):
    """simple heuristic that returns boolean value

    >>> yesno("Yes")
    True
    >>> yesno("oui")
    True
    >>> yesno("1")
    True
    >>> yesno("11")
    True
    >>> yesno("")
    False
    >>> yesno("Non")
    False
    >>> yesno("blablabla")
    False
    """
    if value:
        return value.lower()[0] in 'yo1'
    return False

def isalpha(value):
    if value.isalpha():
        return value
    raise AssertionError("not all characters in the string alphabetic")

def optional(value):
    """validation error will not been raised if you add this checker in chain"""
    return value

def required(value):
    """raise AssertionError is value is empty

    This check should be often found in last position in the chain.
    """
    if bool(value):
        return value
    raise AssertionError("required")

@deprecated('use required(value)')
def nonempty(value):
    return required(value)

@deprecated('use integer(value)')
def alldigits(txt):
    if txt.isdigit():
        return txt
    else:
        return u''


# base integrity checking functions ############################################

def check_doubles(buckets):
    """Extract the keys that have more than one item in their bucket."""
    return [(key, len(value)) for key,value in buckets.items() if len(value) > 1]

def check_doubles_not_none(buckets):
    """Extract the keys that have more than one item in their bucket."""
    return [(key, len(value)) for key,value in buckets.items() if key is not None and len(value) > 1]


# object stores #################################################################

class ObjectStore(object):
    """Store objects in memory for *faster* validation (development mode)

    But it will not enforce the constraints of the schema and hence will miss some problems

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
        """Add new relation (reverse type support is available)

        >>> 1,2 = eid_from, eid_to
        >>> self.relate(eid_from, 'in_group', eid_to)
        1, 'in_group', 2
        >>> self.relate(eid_from, 'reverse_in_group', eid_to)
        2, 'in_group', 1
        """
        if rtype.startswith('reverse_'):
            eid_from, eid_to = eid_to, eid_from
            rtype = rtype[8:]
        relation = eid_from, rtype, eid_to
        self.relations.add(relation)
        return relation

    def build_index(self, name, type, func=None):
        index = {}
        if func is None or not callable(func):
            func = lambda x: x['eid']
        for eid in self.types[type]:
            index.setdefault(func(self.eids[eid]), []).append(eid)
        assert index, "new index '%s' cannot be empty" % name
        self.indexes[name] = index

    def build_rqlindex(self, name, type, key, rql, rql_params=False, func=None):
        """build an index by rql query

        rql should return eid in first column
        ctl.store.build_index('index_name', 'users', 'login', 'Any U WHERE U is CWUser')
        """
        rset = self.rql(rql, rql_params or {})
        for entity in rset.entities():
            getattr(entity, key) # autopopulate entity with key attribute
            self.eids[entity.eid] = dict(entity)
            if entity.eid not in self.types.setdefault(type, []):
                self.types[type].append(entity.eid)
        assert self.types[type], "new index type '%s' cannot be empty (0 record found)" % type

        # Build index with specified key
        func = lambda x: x[key]
        self.build_index(name, type, func)

    @deprecated('get_many() deprecated. Use fetch() instead')
    def get_many(self, name, key):
        return self.fetch(name, key, unique=False)

    @deprecated('get_one() deprecated. Use fetch(..., unique=True) instead')
    def get_one(self, name, key):
        return self.fetch(name, key, unique=True)

    def fetch(self, name, key, unique=False, decorator=None):
        """
            decorator is a callable method or an iterator of callable methods (usually a lambda function)
            decorator=lambda x: x[:1] (first value is returned)

            We can use validation check function available in _entity
        """
        eids = self.indexes[name].get(key, [])
        if decorator is not None:
            if not hasattr(decorator, '__iter__'):
                decorator = (decorator,)
            for f in decorator:
                eids = f(eids)
        if unique:
            assert len(eids) == 1, u'expected a single one value for key "%s" in index "%s". Got %i' % (key, name, len(eids))
            eids = eids[0] # FIXME maybe it's better to keep an iterator here ?
        return eids

    def find(self, type, key, value):
        for idx in self.types[type]:
            item = self.items[idx]
            if item[key] == value:
                yield item

    def rql(self, *args):
        if self._rql is not None:
            return self._rql(*args)

    def checkpoint(self):
        pass


class RQLObjectStore(ObjectStore):
    """ObjectStore that works with an actual RQL repository (production mode)"""
    _rql = None # bw compat

    def __init__(self, session=None, checkpoint=None):
        ObjectStore.__init__(self)
        if session is not None:
            if not hasattr(session, 'set_pool'):
                # connection
                cnx = session
                session = session.request()
                session.set_pool = lambda : None
                checkpoint = checkpoint or cnx.commit
            self.session = session
            self.checkpoint = checkpoint or session.commit
        elif checkpoint is not None:
            self.checkpoint = checkpoint

    def rql(self, *args):
        if self._rql is not None:
            return self._rql(*args)
        self.session.set_pool()
        return self.session.execute(*args)

    def create_entity(self, *args, **kwargs):
        self.session.set_pool()
        entity = self.session.create_entity(*args, **kwargs)
        self.eids[entity.eid] = entity
        self.types.setdefault(args[0], []).append(entity.eid)
        return entity

    def _put(self, type, item):
        query = ('INSERT %s X: ' % type) + ', '.join(['X %s %%(%s)s' % (key,key) for key in item])
        return self.rql(query, item)[0][0]

    def relate(self, eid_from, rtype, eid_to):
        # if reverse relation is found, eids are exchanged
        eid_from, rtype, eid_to = super(RQLObjectStore, self).relate(eid_from, rtype, eid_to)
        self.rql('SET X %s Y WHERE X eid %%(x)s, Y eid %%(y)s' % rtype,
                  {'x': int(eid_from), 'y': int(eid_to)}, ('x', 'y'))


# the import controller ########################################################

class CWImportController(object):
    """Controller of the data import process.

    >>> ctl = CWImportController(store)
    >>> ctl.generators = list_of_data_generators
    >>> ctl.data = dict_of_data_tables
    >>> ctl.run()
    """

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
        print tmp.getvalue()
        # use a list to avoid counting a <nb lines> errors instead of one
        errorlog = self.errors.setdefault(key, [])
        if msg is None:
            errorlog.append(tmp.getvalue().splitlines())
        else:
            errorlog.append( (msg, tmp.getvalue().splitlines()) )

    def run(self):
        self.errors = {}
        for func, checks in self.generators:
            self._checks = {}
            func_name = func.__name__[4:]  # XXX
            self.tell("Import '%s'..." % func_name)
            try:
                func(self)
            except:
                if self.catcherrors:
                    self.record_error(func_name, 'While calling %s' % func.__name__)
                else:
                    raise
            for key, func, title, help in checks:
                buckets = self._checks.get(key)
                if buckets:
                    err = func(buckets)
                    if err:
                        self.errors[title] = (help, err)
        self.store.checkpoint()
        nberrors = sum(len(err[1]) for err in self.errors.values())
        self.tell('\nImport completed: %i entities, %i types, %i relations and %i errors'
                  % (len(self.store.eids), len(self.store.types),
                     len(self.store.relations), nberrors))
        if self.errors:
            if self.askerror==2 or (self.askerror and confirm('Display errors ?')):
                from pprint import pformat
                for errkey, error in self.errors.items():
                    self.tell("\n%s (%s): %d\n" % (error[0], errkey, len(error[1])))
                    self.tell(pformat(sorted(error[1])))

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
        return commit_every(self.commitevery, self.store, self.get_data(datakey))
