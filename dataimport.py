# -*- coding: utf-8 -*-
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
"""This module provides tools to import tabular data.



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
  ctl = CWImportController(RQLObjectStore(cnx))
  ctl.askerror = 1
  ctl.generators = GENERATORS
  ctl.data['utilisateurs'] = lazytable(utf8csvreader(open('users.csv')))
  # run
  ctl.run()

.. BUG file with one column are not parsable
.. TODO rollback() invocation is not possible yet
"""
__docformat__ = "restructuredtext en"

import sys
import csv
import traceback
import os.path as osp
from StringIO import StringIO
from copy import copy

from logilab.common import shellutils
from logilab.common.date import strptime
from logilab.common.decorators import cached
from logilab.common.deprecation import deprecated

from cubicweb.server.utils import eschema_eid

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

def commit_every(nbit, store, it):
    for i, x in enumerate(it):
        yield x
        if nbit is not None and i % nbit:
            store.commit()
    if nbit is not None:
        store.commit()

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
        res[dest] = row[src]
        try:
            for func in funcs:
                res[dest] = func(res[dest])
                if res[dest] is None:
                    break
        except ValueError, err:
            raise ValueError('error with %r field: %s' % (src, err))
    return res


# user interactions ############################################################

def tell(msg):
    print msg

def confirm(question):
    """A confirm function that asks for yes/no/abort and exits on abort."""
    answer = shellutils.ASK.ask(question, ('Y', 'n', 'abort'), 'Y')
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


# base sanitizing/coercing functions ###########################################

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

def required(value):
    """raise ValueError is value is empty

    This check should be often found in last position in the chain.
    """
    if value:
        return value
    raise ValueError("required")

def todatetime(format='%d/%m/%Y'):
    """return a transformation function to turn string input value into a
    `datetime.datetime` instance, using given format.

    Follow it by `todate` or `totime` functions from `logilab.common.date` if
    you want a `date`/`time` instance instead of `datetime`.
    """
    def coerce(value):
        return strptime(value, format)
    return coerce

def call_transform_method(methodname, *args, **kwargs):
    """return value returned by calling the given method on input"""
    def coerce(value):
        return getattr(value, methodname)(*args, **kwargs)
    return coerce

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

def check_doubles(buckets):
    """Extract the keys that have more than one item in their bucket."""
    return [(k, len(v)) for k, v in buckets.items() if len(v) > 1]

def check_doubles_not_none(buckets):
    """Extract the keys that have more than one item in their bucket."""
    return [(k, len(v)) for k, v in buckets.items()
            if k is not None and len(v) > 1]


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
        self._commit = None

    def _put(self, type, item):
        self.items.append(item)
        return len(self.items) - 1

    def add(self, type, item):
        assert isinstance(item, dict), 'item is not a dict but a %s' % type(item)
        eid = item['eid'] = self._put(type, item)
        self.eids[eid] = item
        self.types.setdefault(type, []).append(eid)

    def relate(self, eid_from, rtype, eid_to, inlined=False):
        """Add new relation"""
        relation = eid_from, rtype, eid_to
        self.relations.add(relation)
        return relation

    def commit(self):
        """this commit method do nothing by default

        This is voluntary to use the frequent autocommit feature in CubicWeb
        when you are using hooks or another

        If you want override commit method, please set it by the
        constructor
        """
        pass

    def rql(self, *args):
        if self._rql is not None:
            return self._rql(*args)

    @property
    def nb_inserted_entities(self):
        return len(self.eids)
    @property
    def nb_inserted_types(self):
        return len(self.types)
    @property
    def nb_inserted_relations(self):
        return len(self.relations)

    @deprecated("[3.7] index support will disappear")
    def build_index(self, name, type, func=None, can_be_empty=False):
        """build internal index for further search"""
        index = {}
        if func is None or not callable(func):
            func = lambda x: x['eid']
        for eid in self.types[type]:
            index.setdefault(func(self.eids[eid]), []).append(eid)
        if not can_be_empty:
            assert index, "new index '%s' cannot be empty" % name
        self.indexes[name] = index

    @deprecated("[3.7] index support will disappear")
    def build_rqlindex(self, name, type, key, rql, rql_params=False,
                       func=None, can_be_empty=False):
        """build an index by rql query

        rql should return eid in first column
        ctl.store.build_index('index_name', 'users', 'login', 'Any U WHERE U is CWUser')
        """
        self.types[type] = []
        rset = self.rql(rql, rql_params or {})
        if not can_be_empty:
            assert rset, "new index type '%s' cannot be empty (0 record found)" % type
        for entity in rset.entities():
            getattr(entity, key) # autopopulate entity with key attribute
            self.eids[entity.eid] = dict(entity)
            if entity.eid not in self.types[type]:
                self.types[type].append(entity.eid)

        # Build index with specified key
        func = lambda x: x[key]
        self.build_index(name, type, func, can_be_empty=can_be_empty)

    @deprecated("[3.7] index support will disappear")
    def fetch(self, name, key, unique=False, decorator=None):
        """index fetcher method

        decorator is a callable method or an iterator of callable methods (usually a lambda function)
        decorator=lambda x: x[:1] (first value is returned)
        decorator=lambda x: x.lower (lowercased value is returned)

        decorator is handy when you want to improve index keys but without
        changing the original field

        Same check functions can be reused here.
        """
        eids = self.indexes[name].get(key, [])
        if decorator is not None:
            if not hasattr(decorator, '__iter__'):
                decorator = (decorator,)
            for f in decorator:
                eids = f(eids)
        if unique:
            assert len(eids) == 1, u'expected a single one value for key "%s" in index "%s". Got %i' % (key, name, len(eids))
            eids = eids[0]
        return eids

    @deprecated("[3.7] index support will disappear")
    def find(self, type, key, value):
        for idx in self.types[type]:
            item = self.items[idx]
            if item[key] == value:
                yield item

    @deprecated("[3.7] checkpoint() deprecated. use commit() instead")
    def checkpoint(self):
        self.commit()


class RQLObjectStore(ObjectStore):
    """ObjectStore that works with an actual RQL repository (production mode)"""
    _rql = None # bw compat

    def __init__(self, session=None, commit=None):
        ObjectStore.__init__(self)
        if session is not None:
            if not hasattr(session, 'set_pool'):
                # connection
                cnx = session
                session = session.request()
                session.set_pool = lambda : None
                commit = commit or cnx.commit
            else:
                session.set_pool()
            self.session = session
            self._commit = commit or session.commit
        elif commit is not None:
            self._commit = commit
            # XXX .session

    @deprecated("[3.7] checkpoint() deprecated. use commit() instead")
    def checkpoint(self):
        self.commit()

    def commit(self):
        txuuid = self._commit()
        self.session.set_pool()
        return txuuid

    def rql(self, *args):
        if self._rql is not None:
            return self._rql(*args)
        return self.session.execute(*args)

    def create_entity(self, *args, **kwargs):
        entity = self.session.create_entity(*args, **kwargs)
        self.eids[entity.eid] = entity
        self.types.setdefault(args[0], []).append(entity.eid)
        return entity

    def _put(self, type, item):
        query = ('INSERT %s X: ' % type) + ', '.join('X %s %%(%s)s' % (k, k)
                                                     for k in item)
        return self.rql(query, item)[0][0]

    def relate(self, eid_from, rtype, eid_to, inlined=False):
        eid_from, rtype, eid_to = super(RQLObjectStore, self).relate(
            eid_from, rtype, eid_to)
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
            func_name = func.__name__
            self.tell("Run import function '%s'..." % func_name)
            try:
                func(self)
            except:
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
        txuuid = self.store.commit()
        self._print_stats()
        if self.errors:
            if self.askerror == 2 or (self.askerror and confirm('Display errors ?')):
                from pprint import pformat
                for errkey, error in self.errors.items():
                    self.tell("\n%s (%s): %d\n" % (error[0], errkey, len(error[1])))
                    self.tell(pformat(sorted(error[1])))
        if txuuid is not None:
            print 'transaction id:', txuuid
    def _print_stats(self):
        nberrors = sum(len(err[1]) for err in self.errors.values())
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
        return commit_every(self.commitevery, self.store, self.get_data(datakey))



from datetime import datetime
from cubicweb.schema import META_RTYPES, VIRTUAL_RTYPES


class NoHookRQLObjectStore(RQLObjectStore):
    """ObjectStore that works with an actual RQL repository (production mode)"""
    _rql = None # bw compat

    def __init__(self, session, metagen=None, baseurl=None):
        super(NoHookRQLObjectStore, self).__init__(session)
        self.source = session.repo.system_source
        self.rschema = session.repo.schema.rschema
        self.add_relation = self.source.add_relation
        if metagen is None:
            metagen = MetaGenerator(session, baseurl)
        self.metagen = metagen
        self._nb_inserted_entities = 0
        self._nb_inserted_types = 0
        self._nb_inserted_relations = 0
        self.rql = session.execute
        # deactivate security
        session.set_read_security(False)
        session.set_write_security(False)

    def create_entity(self, etype, **kwargs):
        for k, v in kwargs.iteritems():
            kwargs[k] = getattr(v, 'eid', v)
        entity, rels = self.metagen.base_etype_dicts(etype)
        entity = copy(entity)
        entity._related_cache = {}
        self.metagen.init_entity(entity)
        entity.update(kwargs)
        entity.edited_attributes = set(entity)
        session = self.session
        self.source.add_entity(session, entity)
        self.source.add_info(session, entity, self.source, None, complete=False)
        for rtype, targeteids in rels.iteritems():
            # targeteids may be a single eid or a list of eids
            inlined = self.rschema(rtype).inlined
            try:
                for targeteid in targeteids:
                    self.add_relation(session, entity.eid, rtype, targeteid,
                                      inlined)
            except TypeError:
                self.add_relation(session, entity.eid, rtype, targeteids,
                                  inlined)
        self._nb_inserted_entities += 1
        return entity

    def relate(self, eid_from, rtype, eid_to):
        assert not rtype.startswith('reverse_')
        self.add_relation(self.session, eid_from, rtype, eid_to,
                          self.rschema(rtype).inlined)
        self._nb_inserted_relations += 1

    @property
    def nb_inserted_entities(self):
        return self._nb_inserted_entities
    @property
    def nb_inserted_types(self):
        return self._nb_inserted_types
    @property
    def nb_inserted_relations(self):
        return self._nb_inserted_relations

    def _put(self, type, item):
        raise RuntimeError('use create entity')


class MetaGenerator(object):
    def __init__(self, session, baseurl=None):
        self.session = session
        self.source = session.repo.system_source
        self.time = datetime.now()
        if baseurl is None:
            config = session.vreg.config
            baseurl = config['base-url'] or config.default_base_url()
        if not baseurl[-1] == '/':
            baseurl += '/'
        self.baseurl =  baseurl
        # attributes/relations shared by all entities of the same type
        self.etype_attrs = []
        self.etype_rels = []
        # attributes/relations specific to each entity
        self.entity_attrs = ['cwuri']
        #self.entity_rels = [] XXX not handled (YAGNI?)
        schema = session.vreg.schema
        rschema = schema.rschema
        for rtype in META_RTYPES:
            if rtype in ('eid', 'cwuri') or rtype in VIRTUAL_RTYPES:
                continue
            if rschema(rtype).final:
                self.etype_attrs.append(rtype)
            else:
                self.etype_rels.append(rtype)
        if not schema._eid_index:
            # test schema loaded from the fs
            self.gen_is = self.test_gen_is
            self.gen_is_instance_of = self.test_gen_is_instanceof

    @cached
    def base_etype_dicts(self, etype):
        entity = self.session.vreg['etypes'].etype_class(etype)(self.session)
        # entity are "surface" copied, avoid shared dict between copies
        del entity.cw_extra_kwargs
        for attr in self.etype_attrs:
            entity[attr] = self.generate(entity, attr)
        rels = {}
        for rel in self.etype_rels:
            rels[rel] = self.generate(entity, rel)
        return entity, rels

    def init_entity(self, entity):
        entity.eid = self.source.create_eid(self.session)
        for attr in self.entity_attrs:
            entity[attr] = self.generate(entity, attr)

    def generate(self, entity, rtype):
        return getattr(self, 'gen_%s' % rtype)(entity)

    def gen_cwuri(self, entity):
        return u'%seid/%s' % (self.baseurl, entity.eid)

    def gen_creation_date(self, entity):
        return self.time
    def gen_modification_date(self, entity):
        return self.time

    def gen_is(self, entity):
        return entity.e_schema.eid
    def gen_is_instance_of(self, entity):
        eids = []
        for etype in entity.e_schema.ancestors() + [entity.e_schema]:
            eids.append(entity.e_schema.eid)
        return eids

    def gen_created_by(self, entity):
        return self.session.user.eid
    def gen_owned_by(self, entity):
        return self.session.user.eid

    # implementations of gen_is / gen_is_instance_of to use during test where
    # schema has been loaded from the fs (hence entity type schema eids are not
    # known)
    def test_gen_is(self, entity):
        return eschema_eid(self.session, entity.e_schema)
    def test_gen_is_instanceof(self, entity):
        eids = []
        for eschema in entity.e_schema.ancestors() + [entity.e_schema]:
            eids.append(eschema_eid(self.session, eschema))
        return eids
