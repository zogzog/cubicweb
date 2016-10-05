# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Postgres specific store"""

from __future__ import print_function

import warnings
import os.path as osp
from io import StringIO
from time import asctime
from datetime import date, datetime, time
from collections import defaultdict

from six import string_types, integer_types, text_type, add_metaclass
from six.moves import cPickle as pickle, range

from logilab.common.deprecation import class_deprecated

from cubicweb.utils import make_uid
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.dataimport.stores import NoHookRQLObjectStore


def _execmany_thread_not_copy_from(cu, statement, data, table=None,
                                   columns=None, encoding='utf-8'):
    """ Execute thread without copy from
    """
    cu.executemany(statement, data)


def _execmany_thread_copy_from(cu, statement, data, table,
                               columns, encoding='utf-8'):
    """ Execute thread with copy from
    """
    try:
        buf = _create_copyfrom_buffer(data, columns, encoding=encoding)
    except ValueError:
        _execmany_thread_not_copy_from(cu, statement, data)
    else:
        if columns is None:
            cu.copy_from(buf, table, null=u'NULL')
        else:
            cu.copy_from(buf, table, null=u'NULL', columns=columns)


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
                print('unable to copy data into table %s' % table)
                # Error in import statement, save data in dump_output_dir
                if dump_output_dir is not None:
                    pdata = {'data': data, 'statement': statement,
                             'time': asctime(), 'columns': columns}
                    filename = make_uid()
                    try:
                        with open(osp.join(dump_output_dir,
                                           '%s.pickle' % filename), 'wb') as fobj:
                            pickle.dump(pdata, fobj)
                    except IOError:
                        print('ERROR while pickling in', dump_output_dir, filename+'.pickle')
                cnx.rollback()
                raise
    finally:
        cnx.commit()
        cu.close()


def _copyfrom_buffer_convert_None(value, **opts):
    '''Convert None value to "NULL"'''
    return u'NULL'

def _copyfrom_buffer_convert_number(value, **opts):
    '''Convert a number into its string representation'''
    return text_type(value)

def _copyfrom_buffer_convert_string(value, **opts):
    '''Convert string value.
    '''
    escape_chars = ((u'\\', u'\\\\'), (u'\t', u'\\t'), (u'\r', u'\\r'),
                    (u'\n', u'\\n'))
    for char, replace in escape_chars:
        value = value.replace(char, replace)
    return value

def _copyfrom_buffer_convert_date(value, **opts):
    '''Convert date into "YYYY-MM-DD"'''
    # Do not use strftime, as it yields issue with date < 1900
    # (http://bugs.python.org/issue1777412)
    return u'%04d-%02d-%02d' % (value.year, value.month, value.day)

def _copyfrom_buffer_convert_datetime(value, **opts):
    '''Convert date into "YYYY-MM-DD HH:MM:SS.UUUUUU"'''
    # Do not use strftime, as it yields issue with date < 1900
    # (http://bugs.python.org/issue1777412)
    return u'%s %s' % (_copyfrom_buffer_convert_date(value, **opts),
                       _copyfrom_buffer_convert_time(value, **opts))

def _copyfrom_buffer_convert_time(value, **opts):
    '''Convert time into "HH:MM:SS.UUUUUU"'''
    return u'%02d:%02d:%02d.%06d' % (value.hour, value.minute,
                                     value.second, value.microsecond)

# (types, converter) list.
_COPYFROM_BUFFER_CONVERTERS = [
    (type(None), _copyfrom_buffer_convert_None),
    (integer_types + (float,), _copyfrom_buffer_convert_number),
    (string_types, _copyfrom_buffer_convert_string),
    (datetime, _copyfrom_buffer_convert_datetime),
    (date, _copyfrom_buffer_convert_date),
    (time, _copyfrom_buffer_convert_time),
]

def _create_copyfrom_buffer(data, columns=None, **convert_opts):
    """
    Create a StringIO buffer for 'COPY FROM' command.
    Deals with Unicode, Int, Float, Date... (see ``converters``)

    :data: a sequence/dict of tuples
    :columns: list of columns to consider (default to all columns)
    :converter_opts: keyword arguements given to converters
    """
    # Create a list rather than directly create a StringIO
    # to correctly write lines separated by '\n' in a single step
    rows = []
    if columns is None:
        if isinstance(data[0], (tuple, list)):
            columns = list(range(len(data[0])))
        elif isinstance(data[0], dict):
            columns = data[0].keys()
        else:
            raise ValueError('Could not get columns: you must provide columns.')
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
            for types, converter in _COPYFROM_BUFFER_CONVERTERS:
                if isinstance(value, types):
                    value = converter(value, **convert_opts)
                    assert isinstance(value, text_type)
                    break
            else:
                raise ValueError("Unsupported value type %s" % type(value))
            # We push the value to the new formatted row
            # if the value is not None and could be converted to a string.
            formatted_row.append(value)
        rows.append('\t'.join(formatted_row))
    return StringIO('\n'.join(rows))


@add_metaclass(class_deprecated)
class SQLGenObjectStore(NoHookRQLObjectStore):
    """Controller of the data import process. This version is based
    on direct insertions throught SQL command (COPY FROM or execute many).

    >>> store = SQLGenObjectStore(cnx)
    >>> store.create_entity('Person', ...)
    >>> store.flush()
    """
    __deprecation_warning__ = '[3.23] this class is deprecated, use MassiveObjectStore instead'

    def __init__(self, cnx, dump_output_dir=None, nb_threads_statement=1):
        """
        Initialize a SQLGenObjectStore.

        Parameters:

          - cnx: connection on the cubicweb instance
          - dump_output_dir: a directory to dump failed statements
            for easier recovery. Default is None (no dump).
        """
        super(SQLGenObjectStore, self).__init__(cnx)
        ### hijack default source
        self._system_source = SQLGenSourceWrapper(
            self._system_source, cnx.vreg.schema,
            dump_output_dir=dump_output_dir)
        ### XXX This is done in super().__init__(), but should be
        ### redone here to link to the correct source
        self._add_relation = self._system_source.add_relation
        self.indexes_etypes = {}
        if nb_threads_statement != 1:
            warnings.warn('[3.21] SQLGenObjectStore is no longer threaded', DeprecationWarning)

    def flush(self):
        """Flush data to the database"""
        self._system_source.flush()

    def relate(self, subj_eid, rtype, obj_eid, **kwargs):
        if subj_eid is None or obj_eid is None:
            return
        # XXX Could subjtype be inferred ?
        self._add_relation(self._cnx, subj_eid, rtype, obj_eid,
                           self.rschema(rtype).inlined, **kwargs)
        if self.rschema(rtype).symmetric:
            self._add_relation(self._cnx, obj_eid, rtype, subj_eid,
                               self.rschema(rtype).inlined, **kwargs)

    def drop_indexes(self, etype):
        """Drop indexes for a given entity type"""
        if etype not in self.indexes_etypes:
            cu = self._cnx.cnxset.cu
            def index_to_attr(index):
                """turn an index name to (database) attribute name"""
                return index.replace(etype.lower(), '').replace('idx', '').strip('_')
            indices = [(index, index_to_attr(index))
                       for index in self._system_source.dbhelper.list_indices(cu, etype)
                       # Do not consider 'cw_etype_pkey' index
                       if not index.endswith('key')]
            self.indexes_etypes[etype] = indices
        for index, attr in self.indexes_etypes[etype]:
            self._cnx.system_sql('DROP INDEX %s' % index)

    def create_indexes(self, etype):
        """Recreate indexes for a given entity type"""
        for index, attr in self.indexes_etypes.get(etype, []):
            sql = 'CREATE INDEX %s ON cw_%s(%s)' % (index, etype, attr)
            self._cnx.system_sql(sql)


###########################################################################
## SQL Source #############################################################
###########################################################################

class SQLGenSourceWrapper(object):

    def __init__(self, system_source, schema,
                 dump_output_dir=None):
        self.system_source = system_source
        # Explicitely backport attributes from system source
        self._storage_handler = self.system_source._storage_handler
        self.preprocess_entity = self.system_source.preprocess_entity
        self.sqlgen = self.system_source.sqlgen
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
        self.init_statement_lists()
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

    def init_statement_lists(self):
        self._sql_entities = defaultdict(list)
        self._sql_relations = {}
        self._sql_inlined_relations = {}
        self._sql_eids = defaultdict(list)
        # keep track, for each eid of the corresponding data dict
        self._sql_eid_insertdicts = {}

    def flush(self):
        print('starting flush')
        _entities_sql = self._sql_entities
        _relations_sql = self._sql_relations
        _inlined_relations_sql = self._sql_inlined_relations
        _insertdicts = self._sql_eid_insertdicts
        try:
            # try, for each inlined_relation, to find if we're also creating
            # the host entity (i.e. the subject of the relation).
            # In that case, simply update the insert dict and remove
            # the need to make the
            # UPDATE statement
            for statement, datalist in _inlined_relations_sql.items():
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
            _execmany_thread(self.system_source.get_connection,
                             list(self._sql_eids.items())
                             + list(_entities_sql.items())
                             + list(_relations_sql.items())
                             + list(_inlined_relations_sql.items()),
                             dump_output_dir=self.dump_output_dir,
                             support_copy_from=self.support_copy_from,
                             encoding=self.dbencoding)
        finally:
            _entities_sql.clear()
            _relations_sql.clear()
            _insertdicts.clear()
            _inlined_relations_sql.clear()

    def add_relation(self, cnx, subject, rtype, object,
                     inlined=False, **kwargs):
        if inlined:
            _sql = self._sql_inlined_relations
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
                                     '``subjtype``' % rtype)
            statement = self.sqlgen.update(SQL_PREFIX + subjtype,
                                           data, ['cw_eid'])
        else:
            _sql = self._sql_relations
            data = {'eid_from': subject, 'eid_to': object}
            statement = self.sqlgen.insert('%s_relation' % rtype, data)
        if statement in _sql:
            _sql[statement].append(data)
        else:
            _sql[statement] = [data]

    def add_entity(self, cnx, entity):
        with self._storage_handler(cnx, entity, 'added'):
            attrs = self.preprocess_entity(entity)
            rtypes = self._inlined_rtypes_cache.get(entity.cw_etype, ())
            if isinstance(rtypes, str):
                rtypes = (rtypes,)
            for rtype in rtypes:
                if rtype not in attrs:
                    attrs[rtype] = None
            sql = self.sqlgen.insert(SQL_PREFIX + entity.cw_etype, attrs)
            self._sql_eid_insertdicts[entity.eid] = attrs
            self._append_to_entities(sql, attrs)

    def _append_to_entities(self, sql, attrs):
        self._sql_entities[sql].append(attrs)

    def _handle_insert_entity_sql(self, cnx, sql, attrs):
        self._sql_eids[sql].append(attrs)

    def _handle_is_relation_sql(self, cnx, sql, attrs):
        self._append_to_entities(sql, attrs)

    def _handle_is_instance_of_sql(self, cnx, sql, attrs):
        self._append_to_entities(sql, attrs)

    def _handle_source_relation_sql(self, cnx, sql, attrs):
        self._append_to_entities(sql, attrs)

    # add_info is _copypasted_ from the one in NativeSQLSource. We want it
    # there because it will use the _handlers of the SQLGenSourceWrapper, which
    # are not like the ones in the native source.
    def add_info(self, cnx, entity, source):
        """add type and source info for an eid into the system table"""
        # begin by inserting eid/type/source into the entities table
        attrs = {'type': entity.cw_etype, 'eid': entity.eid}
        self._handle_insert_entity_sql(cnx, self.sqlgen.insert('entities', attrs), attrs)
        # insert core relations: is, is_instance_of and cw_source
        self._handle_is_relation_sql(cnx, 'INSERT INTO is_relation(eid_from,eid_to) VALUES (%s,%s)',
                                     (entity.eid, entity.e_schema.eid))
        for eschema in entity.e_schema.ancestors() + [entity.e_schema]:
            self._handle_is_relation_sql(cnx,
                                         'INSERT INTO is_instance_of_relation(eid_from,eid_to) VALUES (%s,%s)',
                                         (entity.eid, eschema.eid))
        self._handle_is_relation_sql(cnx, 'INSERT INTO cw_source_relation(eid_from,eid_to) VALUES (%s,%s)',
                                     (entity.eid, source.eid))
        # now we can update the full text index
        if self.do_fti and self.need_fti_indexation(entity.cw_etype):
            self.index_entity(cnx, entity=entity)
