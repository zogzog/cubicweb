# coding: utf-8
# copyright 2015-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.

import logging
from datetime import datetime
from collections import defaultdict
from io import StringIO
from itertools import chain

from six.moves import range

import pytz

from yams.constraints import SizeConstraint

from cubicweb.schema import PURE_VIRTUAL_RTYPES
from cubicweb.server.schema2sql import rschema_has_table
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.dataimport import stores, pgstore
from cubicweb.utils import make_uid


class MassiveObjectStore(stores.RQLObjectStore):
    """
    Store for massive import of data, with delayed insertion of meta data.

    WARNINGS:

    - This store may only be used with PostgreSQL for now, as it relies
      on the COPY FROM method, and on specific PostgreSQL tables to get all
      the indexes.

    - This store can only insert relations that are not inlined (i.e.,
      which do *not* have inlined=True in their definition in the schema), unless they are
      specified as entity attributes.

    It should be used as follows:

       store = MassiveObjectStore(cnx)
       store.init_rtype_table('Person', 'lives_in', 'Location')
       ...

       store.prepare_insert_entity('Person', subj_iid_attribute=person_iid, ...)
       store.prepare_insert_entity('Location', obj_iid_attribute=location_iid, ...)
       ...

       # subj_iid_attribute and obj_iid_attribute are argument names
       # chosen by the user (e.g. "cwuri"). These names can be identical.
       # person_iid and location_iid are unique IDs and depend on the data
       # (e.g URI).
       store.flush()
       store.relate_by_iid(person_iid, 'lives_in', location_iid)
       # For example:
       store.prepare_insert_entity('Person',
                                   cwuri='http://dbpedia.org/toto',
                                   name='Toto')
       store.prepare_insert_entity('Location',
                                   uri='http://geonames.org/11111',
                                   name='Somewhere')
       store.flush()
       store.relate_by_iid('http://dbpedia.org/toto',
                           'lives_in',
                           'http://geonames.org/11111')
       # Finally
       store.convert_relations('Person', 'lives_in', 'Location',
                               'subj_iid_attribute', 'obj_iid_attribute')
       # For the previous example:
       store.convert_relations('Person', 'lives_in', 'Location', 'cwuri', 'uri')
       ...
       store.commit()
       store.finish()
    """
    # max size of the iid, used to create the iid_eid conversion table
    iid_maxsize = 1024

    def __init__(self, cnx,
                 on_commit_callback=None, on_rollback_callback=None,
                 slave_mode=False,
                 source=None,
                 eids_seq_range=10000):
        """ Create a MassiveObject store, with the following attributes:

        - cnx: CubicWeb cnx
        - eids_seq_range: size of eid range reserved by the store for each batch
        """
        super(MassiveObjectStore, self).__init__(cnx)
        self.on_commit_callback = on_commit_callback
        self.on_rollback_callback = on_rollback_callback
        self.slave_mode = slave_mode
        self.eids_seq_range = eids_seq_range

        self.logger = logging.getLogger('dataimport.massive_store')
        self.sql = cnx.system_sql
        self.schema = self._cnx.vreg.schema
        self.default_values = get_default_values(self.schema)
        self.get_next_eid = lambda g=self._get_eid_gen(): next(g)
        self._dbh = PGHelper(cnx)

        cnx.read_security = False
        cnx.write_security = False

        self._data_entities = defaultdict(list)
        self._data_relations = defaultdict(list)
        self._initialized = set()
        # uri handling
        self._data_uri_relations = defaultdict(list)
        # etypes for which we have a uri_eid_%(etype)s table
        self._init_uri_eid = set()
        # etypes for which we have a uri_eid_%(e)s_idx index
        self._uri_eid_inserted = set()
        # set of rtypes for which we have a %(rtype)s_relation_iid_tmp table
        self._uri_rtypes = set()

        self._now = datetime.now(pytz.utc)
        self._default_cwuri = make_uid('_auto_generated')

        if not self.slave_mode:
            # drop constraint and metadata table, they will be recreated when self.finish() is
            # called
            self._drop_all_constraints()
            self._drop_metatables_constraints()
        if source is None:
            source = cnx.repo.system_source
        self.source = source

    # URI related things #######################################################

    def init_rtype_table(self, etype_from, rtype, etype_to):
        """ Build temporary table for standard rtype """
        # Create an uri_eid table for each etype for a better control of which etype is concerned by
        # a particular possibly multivalued relation.
        for etype in (etype_from, etype_to):
            if etype and etype not in self._init_uri_eid:
                self._init_uri_eid.add(etype)
                self.sql('CREATE TABLE IF NOT EXISTS uri_eid_%(e)s'
                         '(uri character varying(%(size)s), eid integer)'
                         % {'e': etype.lower(), 'size': self.iid_maxsize})
        if rtype not in self._uri_rtypes:
            # Create the temporary table
            if not self.schema.rschema(rtype).inlined:
                self.sql('CREATE TABLE IF NOT EXISTS %(r)s_relation_iid_tmp'
                         '(uri_from character varying(%(s)s), uri_to character varying(%(s)s))'
                         % {'r': rtype, 's': self.iid_maxsize})
                self._uri_rtypes.add(rtype)
            else:
                self.logger.warning("inlined relation %s: cannot insert it", rtype)

    def relate_by_iid(self, iid_from, rtype, iid_to):
        """Add new relation based on the internal id (iid)
        of the entities (not the eid)"""
        # Push data
        if isinstance(iid_from, unicode):
            iid_from = iid_from.encode('utf-8')
        if isinstance(iid_to, unicode):
            iid_to = iid_to.encode('utf-8')
        self._data_uri_relations[rtype].append({'uri_from': iid_from, 'uri_to': iid_to})

    def flush_relations(self):
        """ Flush the relations data
        """
        for rtype, data in self._data_uri_relations.items():
            if not data:
                self.logger.info('No data for rtype %s', rtype)
            buf = StringIO('\n'.join(['%(uri_from)s\t%(uri_to)s' % d for d in data]))
            if not buf:
                self.logger.info('Empty Buffer for rtype %s', rtype)
                continue
            cursor = self._cnx.cnxset.cu
            if not self.schema.rschema(rtype).inlined:
                cursor.copy_from(buf, '%s_relation_iid_tmp' % rtype.lower(),
                                 null='NULL', columns=('uri_from', 'uri_to'))
            else:
                self.logger.warning("inlined relation %s: cannot insert it", rtype)
            buf.close()
            # Clear data cache
            self._data_uri_relations[rtype] = []

    def fill_uri_eid_table(self, etype, uri_label):
        """ Fill the uri_eid table
        """
        if etype not in self._uri_eid_inserted:
            self._uri_eid_inserted.add(etype)
            self.logger.info('Fill uri_eid for etype %s', etype)
            self.sql('INSERT INTO uri_eid_%(e)s SELECT cw_%(l)s, cw_eid FROM cw_%(e)s'
                     % {'l': uri_label, 'e': etype.lower()})
            self.sql('CREATE INDEX uri_eid_%(e)s_idx ON uri_eid_%(e)s(uri)'
                     % {'e': etype.lower()})

    def convert_relations(self, etype_from, rtype, etype_to,
                          uri_label_from='cwuri', uri_label_to='cwuri'):
        """ Flush the converted relations
        """
        # Always flush relations to be sure
        self.logger.info('Convert relations %s %s %s', etype_from, rtype, etype_to)
        self.flush_relations()
        if uri_label_from:
            self.fill_uri_eid_table(etype_from, uri_label_from)
        if uri_label_to:
            self.fill_uri_eid_table(etype_to, uri_label_to)
        if self.schema.rschema(rtype).inlined:
            self.logger.warning("Can't insert inlined relation %s", rtype)
            return
        if uri_label_from and uri_label_to:
            sql = '''INSERT INTO %(r)s_relation (eid_from, eid_to) SELECT DISTINCT O1.eid, O2.eid
            FROM %(r)s_relation_iid_tmp AS T, uri_eid_%(ef)s as O1, uri_eid_%(et)s as O2
            WHERE O1.uri=T.uri_from AND O2.uri=T.uri_to AND NOT EXISTS (
            SELECT 1 FROM %(r)s_relation AS TT WHERE TT.eid_from=O1.eid AND TT.eid_to=O2.eid);
            '''
        elif uri_label_to:
            sql = '''INSERT INTO %(r)s_relation (eid_from, eid_to) SELECT DISTINCT
            CAST(T.uri_from AS INTEGER), O1.eid
            FROM %(r)s_relation_iid_tmp AS T, uri_eid_%(et)s as O1
            WHERE O1.uri=T.uri_to AND NOT EXISTS (
            SELECT 1 FROM %(r)s_relation AS TT WHERE
            TT.eid_from=CAST(T.uri_from AS INTEGER) AND TT.eid_to=O1.eid);
            '''
        elif uri_label_from:
            sql = '''INSERT INTO %(r)s_relation (eid_from, eid_to) SELECT DISTINCT O1.eid, T.uri_to
            O1.eid, CAST(T.uri_to AS INTEGER)
            FROM %(r)s_relation_iid_tmp AS T, uri_eid_%(ef)s as O1
            WHERE O1.uri=T.uri_from AND NOT EXISTS (
            SELECT 1 FROM %(r)s_relation AS TT WHERE
            TT.eid_from=O1.eid AND TT.eid_to=CAST(T.uri_to AS INTEGER));
            '''
        try:
            self.sql(sql % {'r': rtype.lower(),
                            'et': etype_to.lower() if etype_to else u'',
                            'ef': etype_from.lower() if etype_from else u''})
        except Exception as ex:
            self.logger.error("Can't insert relation %s: %s", rtype, ex)

    # SQL UTILITIES #########################################################

    def _drop_all_constraints(self):
        etypes_tables = ('cw_%s' % eschema.type.lower() for eschema in self.schema.entities()
                         if not eschema.final)
        rtypes_tables = ('%s_relation' % rschema.type.lower() for rschema in self.schema.relations()
                         if rschema_has_table(rschema, skip_relations=PURE_VIRTUAL_RTYPES))
        # Create a table to save the constraints, it allows reloading even after crash
        self.sql('CREATE TABLE IF NOT EXISTS cwmassive_constraints'
                 '(origtable text, query text, type varchar(256))')
        for tablename in chain(etypes_tables, rtypes_tables, ('entities',)):
            constraints = self._dbh.table_constraints(tablename)
            for name, query in constraints.items():
                self.sql('INSERT INTO cwmassive_constraints VALUES (%(e)s, %(c)s, %(t)s)',
                         {'e': tablename, 'c': query, 't': 'constraint'})
                self.sql('ALTER TABLE %s DROP CONSTRAINT %s' % (tablename, name))

    def _reapply_all_constraints(self):
        if not self._dbh.table_exists('cwmassive_constraints'):
            self.logger.info('The table cwmassive_constraints does not exist')
            return
        cu = self.sql("SELECT query FROM cwmassive_constraints WHERE type='constraint'")
        for query, in cu.fetchall():
            self.sql(query)
            self.sql("DELETE FROM cwmassive_constraints WHERE type='constraint' AND query=%(q)s",
                     {'q': query})

    def drop_and_store_indexes(self, tablename):
        """Drop indexes and constraints"""
        # Create a table to save the constraints, it allows reloading even after crash
        self.sql('CREATE TABLE IF NOT EXISTS cwmassive_constraints'
                 '(origtable text, query text, type varchar(256))')
        indexes = self._dbh.table_indexes(tablename)
        for name, query in indexes.items():
            self.sql('INSERT INTO cwmassive_constraints VALUES (%(e)s, %(c)s, %(t)s)',
                     {'e': tablename, 'c': query, 't': 'index'})
            self.sql('DROP INDEX %s' % name)

    def reapply_constraint_index(self, tablename):
        if not self._dbh.table_exists('cwmassive_constraints'):
            self.logger.info('The table cwmassive_constraints does not exist')
            return
        cu = self.sql('SELECT query FROM cwmassive_constraints WHERE origtable = %(e)s',
                      {'e': tablename})
        for query, in cu.fetchall():
            self.sql(query)
            self.sql('DELETE FROM cwmassive_constraints WHERE origtable = %(e)s '
                     'AND query = %(q)s', {'e': tablename, 'q': query})

    def _drop_metatables_constraints(self):
        """ Drop all the constraints for the meta data"""
        for tablename in ('created_by_relation', 'owned_by_relation',
                          'is_instance_of_relation', 'is_relation',
                          'entities'):
            self.drop_and_store_indexes(tablename)

    def _create_metatables_constraints(self):
        """ Create all the constraints for the meta data"""
        for tablename in ('entities',
                          'created_by_relation', 'owned_by_relation',
                          'is_instance_of_relation', 'is_relation'):
            # Indexes and constraints
            self.reapply_constraint_index(tablename)

    def restart_eid_sequence(self, start_eid):
        self._cnx.system_sql(self._cnx.repo.system_source.dbhelper.sql_restart_numrange(
            'entities_id_seq', initial_value=start_eid))
        self._cnx.commit()

    # ENTITIES CREATION #####################################################

    def _get_eid_gen(self):
        """ Function getting the next eid. This is done by preselecting
        a given number of eids from the 'entities_id_seq', and then
        storing them"""
        while True:
            last_eid = self._cnx.repo.system_source.create_eid(self._cnx, self.eids_seq_range)
            for eid in range(last_eid - self.eids_seq_range + 1, last_eid + 1):
                yield eid

    def _apply_default_values(self, etype, kwargs):
        """Apply the default values for a given etype, attribute and value."""
        default_values = self.default_values[etype]
        missing_keys = set(default_values) - set(kwargs)
        kwargs.update((key, default_values[key]) for key in missing_keys)

    # store api ################################################################

    def prepare_insert_entity(self, etype, **kwargs):
        """Given an entity type, attributes and inlined relations, returns the inserted entity's
        eid.
        """
        if not self.slave_mode and etype not in self._initialized:
            self._initialized.add(etype)
            self.drop_and_store_indexes('cw_%s' % etype.lower())
            self.sql('CREATE TABLE IF NOT EXISTS cwmassive_initialized'
                     '(retype text, type varchar(128))')
            self.sql("INSERT INTO cwmassive_initialized VALUES (%(e)s, 'etype')", {'e': etype})
        # Add meta data if not given
        if 'modification_date' not in kwargs:
            kwargs['modification_date'] = self._now
        if 'creation_date' not in kwargs:
            kwargs['creation_date'] = self._now
        if 'cwuri' not in kwargs:
            kwargs['cwuri'] = self._default_cwuri + str(self._count_cwuri)
            self._count_cwuri += 1
        if 'eid' not in kwargs:
            # If eid is not given and the eids sequence is set,
            # use the value from the sequence
            kwargs['eid'] = self.get_next_eid()
        self._apply_default_values(etype, kwargs)
        self._data_entities[etype].append(kwargs)
        return kwargs.get('eid')

    def prepare_insert_relation(self, eid_from, rtype, eid_to, **kwargs):
        """Insert into the database a  relation ``rtype`` between entities with eids ``eid_from``
        and ``eid_to``.
        """
        if not self.slave_mode and rtype not in self._initialized:
            self._initialized.add(rtype)
            self.drop_and_store_indexes('%s_relation' % rtype.lower())
            self.sql('CREATE TABLE %s_relation_tmp (eid_from integer, eid_to integer)'
                     % rtype.lower())
            self.sql('CREATE TABLE IF NOT EXISTS cwmassive_initialized'
                     '(retype text, type varchar(128))')
            self.sql("INSERT INTO cwmassive_initialized VALUES (%(e)s, 'rtype')", {'e': rtype})
        self._data_relations[rtype].append({'eid_from': eid_from, 'eid_to': eid_to})

    def flush(self):
        """Flush the data"""
        self.flush_entities()
        self.flush_internal_relations()
        self.flush_relations()

    def commit(self):
        """Commit the database transaction."""
        self.on_commit()
        super(MassiveObjectStore, self).commit()

    def finish(self):
        """Remove temporary tables and columns."""
        self.logger.info("Start cleaning")
        if self.slave_mode:
            raise RuntimeError('Store cleanup is not allowed in slave mode')
        self.logger.info("Start cleaning")
        # Cleanup relations tables
        for etype in self._init_uri_eid:
            self.sql('DROP TABLE uri_eid_%s' % etype.lower())
        # Remove relations tables
        for rtype in self._uri_rtypes:
            self.sql('DROP TABLE %(r)s_relation_iid_tmp' % {'r': rtype})
        # Create meta constraints (entities, is_instance_of, ...)
        self._create_metatables_constraints()
        # Get all the initialized etypes/rtypes
        if self._dbh.table_exists('cwmassive_initialized'):
            cu = self.sql('SELECT retype, type FROM cwmassive_initialized')
            for retype, _type in cu.fetchall():
                self.logger.info('Cleanup for %s' % retype)
                if _type == 'etype':
                    # Cleanup entities tables - Recreate indexes
                    self.reapply_constraint_index('cw_%s' % etype.lower())
                elif _type == 'rtype':
                    # Cleanup relations tables
                    self._cleanup_relations(retype)
                self.sql('DELETE FROM cwmassive_initialized WHERE retype = %(e)s',
                         {'e': retype})
        self._reapply_all_constraints()
        # Delete the meta data table
        for table_name in ('cwmassive_initialized', 'cwmassive_constraints', 'cwmassive_metadata'):
            self.sql('DROP TABLE IF EXISTS %s' % table_name)
        self.commit()

    # FLUSH #################################################################

    def on_commit(self):
        if self.on_commit_callback:
            self.on_commit_callback()

    def on_rollback(self, exc, etype, data):
        if self.on_rollback_callback:
            self.on_rollback_callback(exc, etype, data)
            self._cnx.rollback()
        else:
            raise exc

    def flush_internal_relations(self):
        """ Flush the relations data
        """
        for rtype, data in self._data_relations.items():
            if not data:
                # There is no data for these etype for this flush round.
                continue
            buf = pgstore._create_copyfrom_buffer(data, ('eid_from', 'eid_to'))
            if not buf:
                # The buffer is empty. This is probably due to error in _create_copyfrom_buffer
                raise ValueError
            cursor = self._cnx.cnxset.cu
            # Push into the tmp table
            cursor.copy_from(buf, '%s_relation_tmp' % rtype.lower(),
                             null='NULL', columns=('eid_from', 'eid_to'))
            # Clear data cache
            self._data_relations[rtype] = []

    def flush_entities(self):
        """ Flush the entities data
        """
        for etype, data in self._data_entities.items():
            if not data:
                # There is no data for these etype for this flush round.
                continue
            # XXX It may be interresting to directly infer the columns' names from the schema
            # XXX For now, the _create_copyfrom_buffer does a "row[column]"
            # which can lead to a key error.
            # Thus we should create dictionary with all the keys.
            columns = set()
            for d in data:
                columns.update(d.keys())
            _data = []
            _base_data = dict.fromkeys(columns)
            for d in data:
                _d = _base_data.copy()
                _d.update(d)
                _data.append(_d)
            buf = pgstore._create_copyfrom_buffer(_data, columns)
            if not buf:
                # The buffer is empty. This is probably due to error in _create_copyfrom_buffer
                raise ValueError('Error in buffer creation for etype %s' % etype)
            columns = ['cw_%s' % attr for attr in columns]
            cursor = self._cnx.cnxset.cu
            try:
                cursor.copy_from(buf, 'cw_%s' % etype.lower(), null='NULL', columns=columns)
            except Exception as exc:
                self.on_rollback(exc, etype, data)
            # Clear data cache
            self._data_entities[etype] = []
        if not self.slave_mode:
            self.flush_meta_data()

    def flush_meta_data(self):
        """ Flush the meta data (entities table, is_instance table, ...)
        """
        if self.slave_mode:
            raise RuntimeError('Flushing meta data is not allow in slave mode')
        if not self._dbh.table_exists('cwmassive_initialized'):
            self.logger.info('No information available for initialized etypes/rtypes')
            return
        # Keep the correctly flush meta data in database
        self.sql('CREATE TABLE IF NOT EXISTS cwmassive_metadata (etype text)')
        cu = self.sql('SELECT etype FROM cwmassive_metadata')
        already_flushed = set(e for e, in cu.fetchall())
        cu = self.sql('SELECT retype FROM cwmassive_initialized WHERE type = %(t)s',
                      {'t': 'etype'})
        all_etypes = set(e for e, in cu.fetchall())
        for etype in all_etypes:
            if etype not in already_flushed:
                # Deals with meta data
                self.logger.info('Flushing meta data for %s' % etype)
                self.insert_massive_meta_data(etype)
                self.sql('INSERT INTO cwmassive_metadata VALUES (%(e)s)', {'e': etype})

    def _cleanup_relations(self, rtype):
        """ Cleanup rtype table """
        # Push into relation table while removing duplicate
        self.sql('INSERT INTO %(r)s_relation (eid_from, eid_to) SELECT DISTINCT '
                 'T.eid_from, T.eid_to FROM %(r)s_relation_tmp AS T '
                 'WHERE NOT EXISTS (SELECT 1 FROM %(r)s_relation AS TT WHERE '
                 'TT.eid_from=T.eid_from AND TT.eid_to=T.eid_to);' % {'r': rtype})
        # Drop temporary relation table
        self.sql('DROP TABLE %(r)s_relation_tmp' % {'r': rtype.lower()})
        # Create indexes and constraints
        tablename = '%s_relation' % rtype.lower()
        self.reapply_constraint_index(tablename)

    def insert_massive_meta_data(self, etype):
        """ Massive insertion of meta data for a given etype, based on SQL statements.
        """
        # Push data - Use coalesce to avoid NULL (and get 0), if there is no
        # entities of this type in the entities table.
        # Meta data relations
        self.metagen_push_relation(etype, self._cnx.user.eid, 'created_by_relation')
        self.metagen_push_relation(etype, self._cnx.user.eid, 'owned_by_relation')
        self.metagen_push_relation(etype, self.source.eid, 'cw_source_relation')
        eschema = self.schema[etype].eid
        self.metagen_push_relation(etype, eschema.eid, 'is_relation')
        for parent_eschema in eschema.ancestors() + [eschema]:
            self.metagen_push_relation(etype, parent_eschema.eid, 'is_instance_of_relation')
        self.sql("INSERT INTO entities (eid, type, asource, extid) "
                 "SELECT cw_eid, '%s', 'system', NULL FROM cw_%s "
                 "WHERE NOT EXISTS (SELECT 1 FROM entities WHERE eid=cw_eid)"
                 % (etype, etype.lower()))

    def metagen_push_relation(self, etype, eid_to, rtype):
        self.sql("INSERT INTO %s (eid_from, eid_to) SELECT cw_eid, %s FROM cw_%s "
                 "WHERE NOT EXISTS (SELECT 1 FROM entities WHERE eid=cw_eid)"
                 % (rtype, eid_to, etype.lower()))


def get_size_constraints(schema):
    """analyzes yams ``schema`` and returns the list of size constraints.

    The returned value is a dictionary mapping entity types to a
    sub-dictionnaries mapping attribute names -> max size.
    """
    size_constraints = {}
    # iterates on all entity types
    for eschema in schema.entities():
        # for each entity type, iterates on attribute definitions
        size_constraints[eschema.type] = eschema_constraints = {}
        for rschema, aschema in eschema.attribute_definitions():
            # for each attribute, if a size constraint is found,
            # append it to the size constraint list
            maxsize = None
            rdef = rschema.rdef(eschema, aschema)
            for constraint in rdef.constraints:
                if isinstance(constraint, SizeConstraint):
                    maxsize = constraint.max
                    eschema_constraints[rschema.type] = maxsize
    return size_constraints


def get_default_values(schema):
    """analyzes yams ``schema`` and returns the list of default values.

    The returned value is a dictionary mapping entity types to a
    sub-dictionnaries mapping attribute names -> default values.
    """
    default_values = {}
    # iterates on all entity types
    for eschema in schema.entities():
        # for each entity type, iterates on attribute definitions
        default_values[eschema.type] = eschema_constraints = {}
        for rschema, _ in eschema.attribute_definitions():
            # for each attribute, if a size constraint is found,
            # append it to the size constraint list
            if eschema.default(rschema.type) is not None:
                eschema_constraints[rschema.type] = eschema.default(rschema.type)
    return default_values


class PGHelper(object):
    """This class provides some helper methods to manipulate a postgres database metadata (index and
    constraints).
    """

    def __init__(self, cnx):
        self.sql = cnx.system_sql
        # Deals with pg schema, see #3216686
        pg_schema = cnx.repo.config.system_source_config.get('db-namespace') or 'public'
        self.pg_schema = pg_schema

    def table_exists(self, tablename):
        """Return True if the given table already exists in the database."""
        cu = self.sql('SELECT 1 from information_schema.tables '
                      'WHERE table_name=%(t)s AND table_schema=%(s)s',
                      {'t': tablename, 's': self.pg_schema})
        return bool(cu.fetchone())

    def table_indexes_constraints(self, tablename):
        """Return one dictionary with all indexes by name, another with all constraints by name,
        for the given table.
        """
        indexes = self.table_indexes(tablename)
        constraints = self.table_constraints(tablename)
        _indexes = {}
        for name, query in indexes.items():
            # Remove pkey indexes (automatically created by constraints)
            # Specific cases of primary key, see #3224079
            if name not in constraints:
                _indexes[name] = query
        return _indexes, constraints

    def table_indexes(self, tablename):
        """Return a dictionary of indexes {index name: index sql}, constraints included."""
        indexes = {}
        for name in self._index_names(tablename):
            indexes[name] = self._index_sql(name)
        return indexes

    def table_constraints(self, tablename):
        """Return a dictionary of constraints {constraint name: constraint sql}."""
        constraints = {}
        for name in self._constraint_names(tablename):
            query = self._constraint_sql(name)
            constraints[name] = 'ALTER TABLE %s ADD CONSTRAINT %s %s' % (tablename, name, query)
        return constraints

    def _index_names(self, tablename):
        """Return the names of all indexes in the given table (including constraints.)"""
        cu = self.sql("SELECT c.relname FROM pg_catalog.pg_class c "
                      "JOIN pg_catalog.pg_index i ON i.indexrelid = c.oid "
                      "JOIN pg_catalog.pg_class c2 ON i.indrelid = c2.oid "
                      "LEFT JOIN pg_catalog.pg_user u ON u.usesysid = c.relowner "
                      "LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
                      "WHERE c.relkind IN ('i','') "
                      " AND c2.relname = %(t)s "
                      " AND i.indisprimary = FALSE "
                      " AND n.nspname NOT IN ('pg_catalog', 'pg_toast') "
                      " AND pg_catalog.pg_table_is_visible(c.oid);", {'t': tablename})
        return [name for name, in cu.fetchall()]

    def _constraint_names(self, tablename):
        """Return the names of all constraints in the given table."""
        cu = self.sql("SELECT i.conname FROM pg_catalog.pg_class c "
                      "JOIN pg_catalog.pg_constraint i ON i.conrelid = c.oid "
                      "JOIN pg_catalog.pg_class c2 ON i.conrelid=c2.oid "
                      "LEFT JOIN pg_catalog.pg_user u ON u.usesysid = c.relowner "
                      "LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace "
                      "WHERE c2.relname = %(t)s "
                      "AND n.nspname NOT IN ('pg_catalog', 'pg_toast') "
                      "AND pg_catalog.pg_table_is_visible(c.oid)", {'t': tablename})
        return [name for name, in cu.fetchall()]

    def _index_sql(self, name):
        """Return the SQL to be used to recreate the index of the given name."""
        return self.sql('SELECT pg_get_indexdef(c.oid) FROM pg_catalog.pg_class c '
                        'LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace '
                        'WHERE c.relname = %(r)s AND n.nspname=%(n)s',
                        {'r': name, 'n': self.pg_schema}).fetchone()[0]

    def _constraint_sql(self, name):
        """Return the SQL to be used to recreate the constraint."""
        return self.sql('SELECT pg_get_constraintdef(c.oid) FROM pg_catalog.pg_constraint c '
                        'LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.connamespace '
                        'WHERE c.conname = %(r)s AND n.nspname=%(n)s',
                        {'r': name, 'n': self.pg_schema}).fetchone()[0]
