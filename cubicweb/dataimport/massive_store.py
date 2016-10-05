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

from base64 import b64encode
from copy import copy
from collections import defaultdict
from itertools import chain
import logging
from uuid import uuid4

from six import text_type
from six.moves import range

from cubicweb.dataimport import stores, pgstore


class MassiveObjectStore(stores.RQLObjectStore):
    """Store for massive import of data, with delayed insertion of meta data.

    WARNINGS:

    - This store may only be used with PostgreSQL for now, as it relies
      on the COPY FROM method, and on specific PostgreSQL tables to get all
      the indexes.

    - This store can only insert relations that are not inlined (i.e.,
      which do *not* have inlined=True in their definition in the schema),
      unless they are specified as entity attributes.

    It should be used as follows:

       store = MassiveObjectStore(cnx)
       eid_p = store.prepare_insert_entity('Person',
                                           cwuri=u'http://dbpedia.org/toto',
                                           name=u'Toto')
       eid_loc = store.prepare_insert_entity('Location',
                                             cwuri=u'http://geonames.org/11111',
                                             name=u'Somewhere')
       store.prepare_insert_relation(eid_p, 'lives_in', eid_loc)
       store.flush()
       ...
       store.commit()
       store.finish()

    Full-text indexation is not handled, you'll have to reindex the proper entity types by yourself
    if desired.
    """

    def __init__(self, cnx,
                 on_commit_callback=None, on_rollback_callback=None,
                 slave_mode=False,
                 eids_seq_range=10000,
                 metagen=None):
        """Create a MassiveObject store, with the following arguments:

        - `cnx`, a connection to the repository
        - `metagen`, optional :class:`MetadataGenerator` instance
        - `eids_seq_range`: size of eid range reserved by the store for each batch
        """
        super(MassiveObjectStore, self).__init__(cnx)

        self.uuid = text_type(uuid4()).replace('-', '')
        self.on_commit_callback = on_commit_callback
        self.on_rollback_callback = on_rollback_callback
        self.slave_mode = slave_mode
        self.eids_seq_range = eids_seq_range
        if metagen is None:
            metagen = stores.MetadataGenerator(cnx)
        self.metagen = metagen

        self.logger = logging.getLogger('dataimport.massive_store')
        self.sql = cnx.system_sql
        self.schema = cnx.vreg.schema
        self.default_values = get_default_values(self.schema)
        self.get_next_eid = lambda g=self._get_eid_gen(): next(g)
        self._dbh = PGHelper(cnx)

        self._data_entities = defaultdict(list)
        self._data_relations = defaultdict(list)
        self._initialized = set()
        self._constraints_dropped = self.slave_mode

    def _get_eid_gen(self):
        """ Function getting the next eid. This is done by preselecting
        a given number of eids from the 'entities_id_seq', and then
        storing them"""
        while True:
            last_eid = self._cnx.repo.system_source.create_eid(self._cnx, self.eids_seq_range)
            for eid in range(last_eid - self.eids_seq_range + 1, last_eid + 1):
                yield eid

    # master/slaves specific API

    def master_init(self):
        """Initialize database for massive insertion.

        This is expected to be called once, by the master store in master/slaves configuration.
        """
        assert not self.slave_mode
        if self not in self._initialized:
            self.sql('CREATE TABLE cwmassive_initialized'
                     '(retype text, type varchar(128), uuid varchar(32))')
            self._initialized.append(self)

    def master_init_etype(self, etype):
        """Initialize database for insertion of entities of the given etype.

        This is expected to be called once, usually by the master store in master/slaves
        configuration.
        """
        self._drop_metadata_constraints_if_necessary()
        tablename = 'cw_%s' % etype.lower()
        self._dbh.drop_constraints(tablename)
        self._dbh.drop_indexes(tablename)
        self.sql('CREATE TABLE IF NOT EXISTS cwmassive_initialized'
                 '(retype text, type varchar(128), uuid varchar(32))')
        self.sql("INSERT INTO cwmassive_initialized VALUES (%(e)s, 'etype', %(uuid)s)",
                 {'e': etype, 'uuid': self.uuid})

    def master_insert_etype_metadata(self, etype):
        """Massive insertion of meta data for a given etype, based on SQL statements.

        In master/slabes configuration, you'll usually want to call it from the master once all
        slaves have finished (at least slaves won't call it automatically, so that's your
        reponsability).
        """
        # insert standard metadata relations
        for rtype, eid in self.metagen.base_etype_rels(etype).items():
            self._insert_meta_relation(etype, eid, '%s_relation' % rtype)
        # insert cw_source, is and is_instance_of relations (normally handled by the system source)
        self._insert_meta_relation(etype, self.metagen.source.eid, 'cw_source_relation')
        eschema = self.schema[etype]
        self._insert_meta_relation(etype, eschema.eid, 'is_relation')
        for parent_eschema in chain(eschema.ancestors(), [eschema]):
            self._insert_meta_relation(etype, parent_eschema.eid, 'is_instance_of_relation')
        # finally insert records into the entities table
        self.sql("INSERT INTO entities (eid, type, extid) "
                 "SELECT cw_eid, '%s', extid FROM cw_%s "
                 "WHERE NOT EXISTS (SELECT 1 FROM entities WHERE eid=cw_eid)"
                 % (etype, etype.lower()))

    # SQL utilities #########################################################

    def _drop_metadata_constraints_if_necessary(self):
        """Drop constraints and indexes for the metadata tables if necessary."""
        if not self._constraints_dropped:
            self._drop_metadata_constraints()
            self._constraints_dropped = True

    def _drop_metadata_constraints(self):
        """Drop constraints and indexes for the metadata tables.

        They will be recreated by the `finish` method.
        """
        rtypes = [rtype for rtype in self.metagen.meta_relations
                  if not self.schema.rschema(rtype).final]
        rtypes += ('is_instance_of', 'is', 'cw_source')
        for rtype in rtypes:
            self._dbh.drop_constraints(rtype + '_relation')
            self._dbh.drop_indexes(rtype + '_relation')
        # don't drop constraints for the entities table, the only one is the primary key's index on
        # eid and we want to keep it
        self._dbh.drop_indexes('entities')

    def restart_eid_sequence(self, start_eid):
        self.sql(self._cnx.repo.system_source.dbhelper.sql_restart_numrange(
            'entities_id_seq', initial_value=start_eid))
        self._cnx.commit()

    # store api ################################################################

    def prepare_insert_entity(self, etype, **data):
        """Given an entity type, attributes and inlined relations, returns the inserted entity's
        eid.
        """
        if not self.slave_mode and etype not in self._initialized:
            self._initialized.add(etype)
            self.master_init_etype(etype)
        if 'eid' not in data:
            # If eid is not given and the eids sequence is set, use the value from the sequence
            eid = self.get_next_eid()
            data['eid'] = eid
        self._data_entities[etype].append(data)
        return data['eid']

    def prepare_insert_relation(self, eid_from, rtype, eid_to, **kwargs):
        """Insert into the database a  relation ``rtype`` between entities with eids ``eid_from``
        and ``eid_to``.

        Relation must not be inlined.
        """
        if rtype not in self._initialized:
            if not self.slave_mode:
                self.master_init()
            assert not self._cnx.vreg.schema.rschema(rtype).inlined
            self._initialized.add(rtype)
            tablename = '%s_relation' % rtype.lower()
            tmp_tablename = '%s_%s' % (tablename, self.uuid)
            self.sql("INSERT INTO cwmassive_initialized VALUES (%(r)s, 'rtype', %(uuid)s)",
                     {'r': rtype, 'uuid': self.uuid})
            self.sql('CREATE TABLE %s(eid_from integer, eid_to integer)' % tmp_tablename)
        self._data_relations[rtype].append({'eid_from': eid_from, 'eid_to': eid_to})

    def flush(self):
        """Flush the data"""
        self.flush_entities()
        self.flush_relations()

    def commit(self):
        """Commit the database transaction."""
        self.on_commit()
        super(MassiveObjectStore, self).commit()

    def finish(self):
        """Remove temporary tables and columns."""
        if self.slave_mode:
            raise RuntimeError('Store cleanup is not allowed in slave mode')
        self.logger.info("Start cleaning")
        # Get all the initialized etypes/rtypes
        if self._dbh.table_exists('cwmassive_initialized'):
            cu = self.sql('SELECT retype, type, uuid FROM cwmassive_initialized')
            relations = defaultdict(list)
            for retype, _type, uuid in cu.fetchall():
                if _type == 'rtype':
                    relations[retype].append(uuid)
            # get back relation data from the temporary tables
            for rtype, uuids in relations.items():
                tablename = '%s_relation' % rtype.lower()
                self._dbh.drop_constraints(tablename)
                self._dbh.drop_indexes(tablename)
                for uuid in uuids:
                    tmp_tablename = '%s_%s' % (tablename, uuid)
                    # XXX no index on the original relation table, EXISTS subquery may be sloooow
                    self.sql('INSERT INTO %(table)s(eid_from, eid_to) SELECT DISTINCT '
                             'T.eid_from, T.eid_to FROM %(tmp_table)s AS T '
                             'WHERE NOT EXISTS (SELECT 1 FROM %(table)s AS TT WHERE '
                             'TT.eid_from=T.eid_from AND TT.eid_to=T.eid_to);'
                             % {'table': tablename, 'tmp_table': tmp_tablename})
                    # Drop temporary relation table and record from cwmassive_initialized
                    self.sql('DROP TABLE %(tmp_table)s' % {'tmp_table': tmp_tablename})
                    self.sql('DELETE FROM cwmassive_initialized '
                             'WHERE retype = %(rtype)s AND uuid = %(uuid)s',
                             {'rtype': retype, 'uuid': uuid})
        self._dbh.restore_indexes_and_constraints()
        # Delete the meta data table
        self.sql('DROP TABLE IF EXISTS cwmassive_initialized')
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

    def flush_relations(self):
        """Flush the relations data."""
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
            tablename = '%s_relation' % rtype.lower()
            tmp_tablename = '%s_%s' % (tablename, self.uuid)
            cursor.copy_from(buf, tmp_tablename, null='NULL', columns=('eid_from', 'eid_to'))
            # Clear data cache
            self._data_relations[rtype] = []

    def flush_entities(self):
        """Flush the entities data."""
        metagen = self.metagen
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
                columns.update(d)
            _base_data = dict.fromkeys(columns)
            _base_data.update(self.default_values[etype])
            _base_data.update(metagen.base_etype_attrs(etype))
            _data = []
            for d in data:
                _d = _base_data.copy()
                _d.update(d)
                metagen.init_entity_attrs(etype, _d['eid'], _d)
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
                self.master_insert_etype_metadata(etype)

    def _insert_meta_relation(self, etype, eid_to, rtype):
        self.sql("INSERT INTO %s (eid_from, eid_to) SELECT cw_eid, %s FROM cw_%s "
                 "WHERE NOT EXISTS (SELECT 1 FROM entities WHERE eid=cw_eid)"
                 % (rtype, eid_to, etype.lower()))


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

    def drop_indexes(self, tablename):
        """Drop indexes and constraints, storing them in a table for later restore."""
        # Create a table to save the constraints, it allows reloading even after crash
        self.sql('CREATE TABLE IF NOT EXISTS cwmassive_constraints(sql TEXT, insert_order SERIAL)')
        indexes = self.table_indexes(tablename)
        for name, query in indexes.items():
            self.sql('INSERT INTO cwmassive_constraints(sql) VALUES (%(sql)s)', {'sql': query})
            self.sql('DROP INDEX %s' % name)

    def drop_constraints(self, tablename):
        self.sql('CREATE TABLE IF NOT EXISTS cwmassive_constraints(sql TEXT, insert_order SERIAL)')
        constraints = self.table_constraints(tablename)
        for name, query in constraints.items():
            self.sql('INSERT INTO cwmassive_constraints(sql) VALUES (%(sql)s)', {'sql': query})
            self.sql('ALTER TABLE %s DROP CONSTRAINT %s' % (tablename, name))

    def restore_indexes_and_constraints(self):
        """Restore indexes and constraints."""
        if not self.table_exists('cwmassive_constraints'):
            return
        cu = self.sql('SELECT sql, insert_order FROM cwmassive_constraints '
                      'ORDER BY insert_order DESC')
        for query, order in cu.fetchall():
            self.sql(query)
            self.sql('DELETE FROM cwmassive_constraints WHERE insert_order=%(order)s',
                     {'order': order})
        self.sql('DROP TABLE cwmassive_constraints')

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
