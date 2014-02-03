# -*- coding: utf-8 -*-
# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
          entity = ctl.store.create_entity('CWUser', **entity)
          email = ctl.store.create_entity('EmailAddress', address=row['email'])
          ctl.store.relate(entity.eid, 'use_email', email.eid)
          ctl.store.rql('SET U in_group G WHERE G name "users", U eid %(x)s', {'x':entity['eid']})

  CHK = [('login', check_doubles, 'Utilisateurs Login',
          'Deux utilisateurs ne devraient pas avoir le même login.'),
         ]

  GENERATORS.append( (gen_users, CHK) )

  # create controller
  if 'cnx' in globals():
      ctl = CWImportController(RQLObjectStore(cnx))
  else:
      print 'debug mode (not connected)'
      print 'run through cubicweb-ctl shell to access an instance'
      ctl = CWImportController(ObjectStore())
  ctl.askerror = 1
  ctl.generators = GENERATORS
  ctl.data['utilisateurs'] = lazytable(ucsvreader(open('users.csv')))
  # run
  ctl.run()

.. BUG file with one column are not parsable
.. TODO rollback() invocation is not possible yet
"""
__docformat__ = "restructuredtext en"

import csv
import sys
import threading
import traceback
import warnings
import cPickle
import os.path as osp
import inspect
from collections import defaultdict
from copy import copy
from datetime import date, datetime
from time import asctime
from StringIO import StringIO

from logilab.common import shellutils, attrdict
from logilab.common.date import strptime
from logilab.common.decorators import cached
from logilab.common.deprecation import deprecated

from cubicweb import QueryError
from cubicweb.utils import make_uid
from cubicweb.schema import META_RTYPES, VIRTUAL_RTYPES
from cubicweb.server.edition import EditedEntity
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.server.utils import eschema_eid


def count_lines(stream_or_filename):
    if isinstance(stream_or_filename, basestring):
        f = open(stream_or_filename)
    else:
        f = stream_or_filename
        f.seek(0)
    for i, line in enumerate(f):
        pass
    f.seek(0)
    return i+1

def ucsvreader_pb(stream_or_path, encoding='utf-8', separator=',', quote='"',
                  skipfirst=False, withpb=True, skip_empty=True):
    """same as :func:`ucsvreader` but a progress bar is displayed as we iter on rows"""
    if isinstance(stream_or_path, basestring):
        if not osp.exists(stream_or_path):
            raise Exception("file doesn't exists: %s" % stream_or_path)
        stream = open(stream_or_path)
    else:
        stream = stream_or_path
    rowcount = count_lines(stream)
    if skipfirst:
        rowcount -= 1
    if withpb:
        pb = shellutils.ProgressBar(rowcount, 50)
    for urow in ucsvreader(stream, encoding, separator, quote,
                           skipfirst=skipfirst, skip_empty=skip_empty):
        yield urow
        if withpb:
            pb.update()
    print ' %s rows imported' % rowcount

def ucsvreader(stream, encoding='utf-8', separator=',', quote='"',
               skipfirst=False, ignore_errors=False, skip_empty=True):
    """A csv reader that accepts files with any encoding and outputs unicode
    strings

    if skip_empty (the default), lines without any values specified (only
    separators) will be skipped. This is useful for Excel exports which may be
    full of such lines.
    """
    it = iter(csv.reader(stream, delimiter=separator, quotechar=quote))
    if not ignore_errors:
        if skipfirst:
            it.next()
        for row in it:
            decoded = [item.decode(encoding) for item in row]
            if not skip_empty or any(decoded):
                yield [item.decode(encoding) for item in row]
    else:
        # Skip first line
        try:
            row = it.next()
        except csv.Error:
            pass
        # Safe version, that can cope with error in CSV file
        while True:
            try:
                row = it.next()
            # End of CSV, break
            except StopIteration:
                break
            # Error in CSV, ignore line and continue
            except csv.Error:
                continue
            decoded = [item.decode(encoding) for item in row]
            if not skip_empty or any(decoded):
                yield decoded


def callfunc_every(func, number, iterable):
    """yield items of `iterable` one by one and call function `func`
    every `number` iterations. Always call function `func` at the end.
    """
    for idx, item in enumerate(iterable):
        yield item
        if not idx % number:
            func()
    func()

def lazytable(reader):
    """The first row is taken to be the header of the table and
    used to output a dict for each row of data.

    >>> data = lazytable(ucsvreader(open(filename)))
    """
    header = reader.next()
    for row in reader:
        yield dict(zip(header, row))

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
            raise ValueError('error with %r field: %s' % (src, err)), None, sys.exc_info()[-1]
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
    """raise ValueError if value is empty

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

# sql generator utility functions #############################################


def _import_statements(sql_connect, statements, nb_threads=3,
                       dump_output_dir=None,
                       support_copy_from=True, encoding='utf-8'):
    """
    Import a bunch of sql statements, using different threads.
    """
    try:
        chunksize = (len(statements) / nb_threads) + 1
        threads = []
        for i in xrange(nb_threads):
            chunks = statements[i*chunksize:(i+1)*chunksize]
            thread = threading.Thread(target=_execmany_thread,
                                      args=(sql_connect, chunks,
                                            dump_output_dir,
                                            support_copy_from,
                                            encoding))
            thread.start()
            threads.append(thread)
        for t in threads:
            t.join()
    except Exception:
        print 'Error in import statements'

def _execmany_thread_not_copy_from(cu, statement, data, table=None,
                                   columns=None, encoding='utf-8'):
    """ Execute thread without copy from
    """
    cu.executemany(statement, data)

def _execmany_thread_copy_from(cu, statement, data, table,
                               columns, encoding='utf-8'):
    """ Execute thread with copy from
    """
    buf = _create_copyfrom_buffer(data, columns, encoding)
    if buf is None:
        _execmany_thread_not_copy_from(cu, statement, data)
    else:
        if columns is None:
            cu.copy_from(buf, table, null='NULL')
        else:
            cu.copy_from(buf, table, null='NULL', columns=columns)

def _execmany_thread(sql_connect, statements, dump_output_dir=None,
                     support_copy_from=True, encoding='utf-8'):
    """
    Execute sql statement. If 'INSERT INTO', try to use 'COPY FROM' command,
    or fallback to execute_many.
    """
    if support_copy_from:
        execmany_func = _execmany_thread_copy_from
    else:
        execmany_func = _execmany_thread_not_copy_from
    cnx = sql_connect()
    cu = cnx.cursor()
    try:
        for statement, data in statements:
            table = None
            columns = None
            try:
                if not statement.startswith('INSERT INTO'):
                    cu.executemany(statement, data)
                    continue
                table = statement.split()[2]
                if isinstance(data[0], (tuple, list)):
                    columns = None
                else:
                    columns = list(data[0])
                execmany_func(cu, statement, data, table, columns, encoding)
            except Exception:
                print 'unable to copy data into table %s' % table
                # Error in import statement, save data in dump_output_dir
                if dump_output_dir is not None:
                    pdata = {'data': data, 'statement': statement,
                             'time': asctime(), 'columns': columns}
                    filename = make_uid()
                    try:
                        with open(osp.join(dump_output_dir,
                                           '%s.pickle' % filename), 'w') as fobj:
                            fobj.write(cPickle.dumps(pdata))
                    except IOError:
                        print 'ERROR while pickling in', dump_output_dir, filename+'.pickle'
                        pass
                cnx.rollback()
                raise
    finally:
        cnx.commit()
        cu.close()

def _create_copyfrom_buffer(data, columns, encoding='utf-8', replace_sep=None):
    """
    Create a StringIO buffer for 'COPY FROM' command.
    Deals with Unicode, Int, Float, Date...
    """
    # Create a list rather than directly create a StringIO
    # to correctly write lines separated by '\n' in a single step
    rows = []
    if isinstance(data[0], (tuple, list)):
        columns = range(len(data[0]))
    for row in data:
        # Iterate over the different columns and the different values
        # and try to convert them to a correct datatype.
        # If an error is raised, do not continue.
        formatted_row = []
        for col in columns:
            try:
                value = row[col]
            except KeyError:
                warnings.warn(u"Column %s is not accessible in row %s" 
                              % (col, row), RuntimeWarning)
                # XXX 'value' set to None so that the import does not end in 
                # error. 
                # Instead, the extra keys are set to NULL from the 
                # database point of view.
                value = None
            if value is None:
                value = 'NULL'
            elif isinstance(value, (long, int, float)):
                value = str(value)
            elif isinstance(value, (str, unicode)):
                # Remove separators used in string formatting
                for _char in (u'\t', u'\r', u'\n'):
                    if _char in value:
                        # If a replace_sep is given, replace
                        # the separator instead of returning None
                        # (and thus avoid empty buffer)
                        if replace_sep:
                            value = value.replace(_char, replace_sep)
                        else:
                            return
                value = value.replace('\\', r'\\')
                if value is None:
                    return
                if isinstance(value, unicode):
                    value = value.encode(encoding)
            elif isinstance(value, (date, datetime)):
                # Do not use strftime, as it yields issue
                # with date < 1900
                value = '%04d-%02d-%02d' % (value.year,
                                            value.month,
                                            value.day)
            else:
                return None
            # We push the value to the new formatted row
            # if the value is not None and could be converted to a string.
            formatted_row.append(value)
        rows.append('\t'.join(formatted_row))
    return StringIO('\n'.join(rows))


# object stores #################################################################

class ObjectStore(object):
    """Store objects in memory for *faster* validation (development mode)

    But it will not enforce the constraints of the schema and hence will miss some problems

    >>> store = ObjectStore()
    >>> user = store.create_entity('CWUser', login=u'johndoe')
    >>> group = store.create_entity('CWUser', name=u'unknown')
    >>> store.relate(user.eid, 'in_group', group.eid)
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

    def create_entity(self, etype, **data):
        data = attrdict(data)
        data['eid'] = eid = self._put(etype, data)
        self.eids[eid] = data
        self.types.setdefault(etype, []).append(eid)
        return data

    @deprecated("[3.11] add is deprecated, use create_entity instead")
    def add(self, etype, item):
        assert isinstance(item, dict), 'item is not a dict but a %s' % type(item)
        data = self.create_entity(etype, **item)
        item['eid'] = data['eid']
        return item

    def relate(self, eid_from, rtype, eid_to, **kwargs):
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

    def flush(self):
        """The method is provided so that all stores share a common API.
        It just tries to call the commit method.
        """
        print 'starting flush'
        try:
            self.commit()
        except:
            print 'failed to flush'
        else:
            print 'flush done'

    def rql(self, *args):
        if self._rql is not None:
            return self._rql(*args)
        return []

    @property
    def nb_inserted_entities(self):
        return len(self.eids)
    @property
    def nb_inserted_types(self):
        return len(self.types)
    @property
    def nb_inserted_relations(self):
        return len(self.relations)

class RQLObjectStore(ObjectStore):
    """ObjectStore that works with an actual RQL repository (production mode)"""
    _rql = None # bw compat

    def __init__(self, session=None, commit=None):
        ObjectStore.__init__(self)
        if session is None:
            sys.exit('please provide a session of run this script with cubicweb-ctl shell and pass cnx as session')
        if not hasattr(session, 'set_cnxset'):
            if hasattr(session, 'request'):
                # connection object
                cnx = session
                session = session.request()
            else: # object is already a request
                cnx = session.cnx
            session.set_cnxset = lambda : None
            commit = commit or cnx.commit
        else:
            session.set_cnxset()
        self.session = session
        self._commit = commit or session.commit

    def commit(self):
        txuuid = self._commit()
        self.session.set_cnxset()
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
        query = 'INSERT %s X' % type
        if item:
            query += ': ' + ', '.join('X %s %%(%s)s' % (k, k)
                                      for k in item)
        return self.rql(query, item)[0][0]

    def relate(self, eid_from, rtype, eid_to, **kwargs):
        eid_from, rtype, eid_to = super(RQLObjectStore, self).relate(
            eid_from, rtype, eid_to, **kwargs)
        self.rql('SET X %s Y WHERE X eid %%(x)s, Y eid %%(y)s' % rtype,
                 {'x': int(eid_from), 'y': int(eid_to)})

    def find_entities(self, *args, **kwargs):
        return self.session.find_entities(*args, **kwargs)

    def find_one_entity(self, *args, **kwargs):
        return self.session.find_one_entity(*args, **kwargs)

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
        nberrors = sum(len(err) for err in self.errors.itervalues())
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
        session.read_security = False
        session.write_security = False

    def create_entity(self, etype, **kwargs):
        for k, v in kwargs.iteritems():
            kwargs[k] = getattr(v, 'eid', v)
        entity, rels = self.metagen.base_etype_dicts(etype)
        # make a copy to keep cached entity pristine
        entity = copy(entity)
        entity.cw_edited = copy(entity.cw_edited)
        entity.cw_clear_relation_cache()
        self.metagen.init_entity(entity)
        entity.cw_edited.update(kwargs, skipsec=False)
        session = self.session
        self.source.add_entity(session, entity)
        self.source.add_info(session, entity, self.source, None, complete=False)
        kwargs = dict()
        if inspect.getargspec(self.add_relation).keywords:
            kwargs['subjtype'] = entity.cw_etype
        for rtype, targeteids in rels.iteritems():
            # targeteids may be a single eid or a list of eids
            inlined = self.rschema(rtype).inlined
            try:
                for targeteid in targeteids:
                    self.add_relation(session, entity.eid, rtype, targeteid,
                                      inlined, **kwargs)
            except TypeError:
                self.add_relation(session, entity.eid, rtype, targeteids,
                                  inlined, **kwargs)
        self._nb_inserted_entities += 1
        return entity

    def relate(self, eid_from, rtype, eid_to, **kwargs):
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
    META_RELATIONS = (META_RTYPES
                      - VIRTUAL_RTYPES
                      - set(('eid', 'cwuri',
                             'is', 'is_instance_of', 'cw_source')))

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
        for rtype in self.META_RELATIONS:
            if rschema(rtype).final:
                self.etype_attrs.append(rtype)
            else:
                self.etype_rels.append(rtype)

    @cached
    def base_etype_dicts(self, etype):
        entity = self.session.vreg['etypes'].etype_class(etype)(self.session)
        # entity are "surface" copied, avoid shared dict between copies
        del entity.cw_extra_kwargs
        entity.cw_edited = EditedEntity(entity)
        for attr in self.etype_attrs:
            entity.cw_edited.edited_attribute(attr, self.generate(entity, attr))
        rels = {}
        for rel in self.etype_rels:
            rels[rel] = self.generate(entity, rel)
        return entity, rels

    def init_entity(self, entity):
        entity.eid = self.source.create_eid(self.session)
        for attr in self.entity_attrs:
            entity.cw_edited.edited_attribute(attr, self.generate(entity, attr))

    def generate(self, entity, rtype):
        return getattr(self, 'gen_%s' % rtype)(entity)

    def gen_cwuri(self, entity):
        return u'%seid/%s' % (self.baseurl, entity.eid)

    def gen_creation_date(self, entity):
        return self.time
    def gen_modification_date(self, entity):
        return self.time

    def gen_created_by(self, entity):
        return self.session.user.eid
    def gen_owned_by(self, entity):
        return self.session.user.eid


###########################################################################
## SQL object store #######################################################
###########################################################################
class SQLGenObjectStore(NoHookRQLObjectStore):
    """Controller of the data import process. This version is based
    on direct insertions throught SQL command (COPY FROM or execute many).

    >>> store = SQLGenObjectStore(session)
    >>> store.create_entity('Person', ...)
    >>> store.flush()
    """

    def __init__(self, session, dump_output_dir=None, nb_threads_statement=3):
        """
        Initialize a SQLGenObjectStore.

        Parameters:

          - session: session on the cubicweb instance
          - dump_output_dir: a directory to dump failed statements
            for easier recovery. Default is None (no dump).
          - nb_threads_statement: number of threads used
            for SQL insertion (default is 3).
        """
        super(SQLGenObjectStore, self).__init__(session)
        ### hijack default source
        self.source = SQLGenSourceWrapper(
            self.source, session.vreg.schema,
            dump_output_dir=dump_output_dir,
            nb_threads_statement=nb_threads_statement)
        ### XXX This is done in super().__init__(), but should be
        ### redone here to link to the correct source
        self.add_relation = self.source.add_relation
        self.indexes_etypes = {}

    def flush(self):
        """Flush data to the database"""
        self.source.flush()

    def relate(self, subj_eid, rtype, obj_eid, **kwargs):
        if subj_eid is None or obj_eid is None:
            return
        # XXX Could subjtype be inferred ?
        self.source.add_relation(self.session, subj_eid, rtype, obj_eid,
                                 self.rschema(rtype).inlined, **kwargs)

    def drop_indexes(self, etype):
        """Drop indexes for a given entity type"""
        if etype not in self.indexes_etypes:
            cu = self.session.cnxset['system']
            def index_to_attr(index):
                """turn an index name to (database) attribute name"""
                return index.replace(etype.lower(), '').replace('idx', '').strip('_')
            indices = [(index, index_to_attr(index))
                       for index in self.source.dbhelper.list_indices(cu, etype)
                       # Do not consider 'cw_etype_pkey' index
                       if not index.endswith('key')]
            self.indexes_etypes[etype] = indices
        for index, attr in self.indexes_etypes[etype]:
            self.session.system_sql('DROP INDEX %s' % index)

    def create_indexes(self, etype):
        """Recreate indexes for a given entity type"""
        for index, attr in self.indexes_etypes.get(etype, []):
            sql = 'CREATE INDEX %s ON cw_%s(%s)' % (index, etype, attr)
            self.session.system_sql(sql)


###########################################################################
## SQL Source #############################################################
###########################################################################

class SQLGenSourceWrapper(object):

    def __init__(self, system_source, schema,
                 dump_output_dir=None, nb_threads_statement=3):
        self.system_source = system_source
        self._sql = threading.local()
        # Explicitely backport attributes from system source
        self._storage_handler = self.system_source._storage_handler
        self.preprocess_entity = self.system_source.preprocess_entity
        self.sqlgen = self.system_source.sqlgen
        self.copy_based_source = self.system_source.copy_based_source
        self.uri = self.system_source.uri
        self.eid = self.system_source.eid
        # Directory to write temporary files
        self.dump_output_dir = dump_output_dir
        # Allow to execute code with SQLite backend that does
        # not support (yet...) copy_from
        # XXX Should be dealt with in logilab.database
        spcfrom = system_source.dbhelper.dbapi_module.support_copy_from
        self.support_copy_from = spcfrom
        self.dbencoding = system_source.dbhelper.dbencoding
        self.nb_threads_statement = nb_threads_statement
        # initialize thread-local data for main thread
        self.init_thread_locals()
        self._inlined_rtypes_cache = {}
        self._fill_inlined_rtypes_cache(schema)
        self.schema = schema
        self.do_fti = False

    def _fill_inlined_rtypes_cache(self, schema):
        cache = self._inlined_rtypes_cache
        for eschema in schema.entities():
            for rschema in eschema.ordered_relations():
                if rschema.inlined:
                    cache[eschema.type] = SQL_PREFIX + rschema.type

    def init_thread_locals(self):
        """initializes thread-local data"""
        self._sql.entities = defaultdict(list)
        self._sql.relations = {}
        self._sql.inlined_relations = {}
        # keep track, for each eid of the corresponding data dict
        self._sql.eid_insertdicts = {}

    def flush(self):
        print 'starting flush'
        _entities_sql = self._sql.entities
        _relations_sql = self._sql.relations
        _inlined_relations_sql = self._sql.inlined_relations
        _insertdicts = self._sql.eid_insertdicts
        try:
            # try, for each inlined_relation, to find if we're also creating
            # the host entity (i.e. the subject of the relation).
            # In that case, simply update the insert dict and remove
            # the need to make the
            # UPDATE statement
            for statement, datalist in _inlined_relations_sql.iteritems():
                new_datalist = []
                # for a given inlined relation,
                # browse each couple to be inserted
                for data in datalist:
                    keys = list(data)
                    # For inlined relations, it exists only two case:
                    # (rtype, cw_eid) or (cw_eid, rtype)
                    if keys[0] == 'cw_eid':
                        rtype = keys[1]
                    else:
                        rtype = keys[0]
                    updated_eid = data['cw_eid']
                    if updated_eid in _insertdicts:
                        _insertdicts[updated_eid][rtype] = data[rtype]
                    else:
                        # could not find corresponding insert dict, keep the
                        # UPDATE query
                        new_datalist.append(data)
                _inlined_relations_sql[statement] = new_datalist
            _import_statements(self.system_source.get_connection,
                               _entities_sql.items()
                               + _relations_sql.items()
                               + _inlined_relations_sql.items(),
                               dump_output_dir=self.dump_output_dir,
                               nb_threads=self.nb_threads_statement,
                               support_copy_from=self.support_copy_from,
                               encoding=self.dbencoding)
        except:
            print 'failed to flush'
        else:
            print 'flush done'
        finally:
            _entities_sql.clear()
            _relations_sql.clear()
            _insertdicts.clear()
            _inlined_relations_sql.clear()

    def add_relation(self, session, subject, rtype, object,
                     inlined=False, **kwargs):
        if inlined:
            _sql = self._sql.inlined_relations
            data = {'cw_eid': subject, SQL_PREFIX + rtype: object}
            subjtype = kwargs.get('subjtype')
            if subjtype is None:
                # Try to infer it
                targets = [t.type for t in
                           self.schema.rschema(rtype).subjects()]
                if len(targets) == 1:
                    subjtype = targets[0]
                else:
                    raise ValueError('You should give the subject etype for '
                                     'inlined relation %s'
                                     ', as it cannot be inferred: '
                                     'this type is given as keyword argument '
                                     '``subjtype``'% rtype)
            statement = self.sqlgen.update(SQL_PREFIX + subjtype,
                                           data, ['cw_eid'])
        else:
            _sql = self._sql.relations
            data = {'eid_from': subject, 'eid_to': object}
            statement = self.sqlgen.insert('%s_relation' % rtype, data)
        if statement in _sql:
            _sql[statement].append(data)
        else:
            _sql[statement] = [data]

    def add_entity(self, session, entity):
        with self._storage_handler(entity, 'added'):
            attrs = self.preprocess_entity(entity)
            rtypes = self._inlined_rtypes_cache.get(entity.cw_etype, ())
            if isinstance(rtypes, str):
                rtypes = (rtypes,)
            for rtype in rtypes:
                if rtype not in attrs:
                    attrs[rtype] = None
            sql = self.sqlgen.insert(SQL_PREFIX + entity.cw_etype, attrs)
            self._sql.eid_insertdicts[entity.eid] = attrs
            self._append_to_entities(sql, attrs)

    def _append_to_entities(self, sql, attrs):
        self._sql.entities[sql].append(attrs)

    def _handle_insert_entity_sql(self, session, sql, attrs):
        # We have to overwrite the source given in parameters
        # as here, we directly use the system source
        attrs['source'] = 'system'
        attrs['asource'] = self.system_source.uri
        self._append_to_entities(sql, attrs)

    def _handle_is_relation_sql(self, session, sql, attrs):
        self._append_to_entities(sql, attrs)

    def _handle_is_instance_of_sql(self, session, sql, attrs):
        self._append_to_entities(sql, attrs)

    def _handle_source_relation_sql(self, session, sql, attrs):
        self._append_to_entities(sql, attrs)

    # add_info is _copypasted_ from the one in NativeSQLSource. We want it
    # there because it will use the _handlers of the SQLGenSourceWrapper, which
    # are not like the ones in the native source.
    def add_info(self, session, entity, source, extid, complete):
        """add type and source info for an eid into the system table"""
        # begin by inserting eid/type/source/extid into the entities table
        if extid is not None:
            assert isinstance(extid, str)
            extid = b64encode(extid)
        uri = 'system' if source.copy_based_source else source.uri
        attrs = {'type': entity.cw_etype, 'eid': entity.eid, 'extid': extid,
                 'source': uri, 'asource': source.uri, 'mtime': datetime.utcnow()}
        self._handle_insert_entity_sql(session, self.sqlgen.insert('entities', attrs), attrs)
        # insert core relations: is, is_instance_of and cw_source
        try:
            self._handle_is_relation_sql(session, 'INSERT INTO is_relation(eid_from,eid_to) VALUES (%s,%s)',
                                         (entity.eid, eschema_eid(session, entity.e_schema)))
        except IndexError:
            # during schema serialization, skip
            pass
        else:
            for eschema in entity.e_schema.ancestors() + [entity.e_schema]:
                self._handle_is_relation_sql(session,
                                             'INSERT INTO is_instance_of_relation(eid_from,eid_to) VALUES (%s,%s)',
                                             (entity.eid, eschema_eid(session, eschema)))
        if 'CWSource' in self.schema and source.eid is not None: # else, cw < 3.10
            self._handle_is_relation_sql(session, 'INSERT INTO cw_source_relation(eid_from,eid_to) VALUES (%s,%s)',
                                         (entity.eid, source.eid))
        # now we can update the full text index
        if self.do_fti and self.need_fti_indexation(entity.cw_etype):
            if complete:
                entity.complete(entity.e_schema.indexable_attributes())
            self.index_entity(session, entity=entity)
