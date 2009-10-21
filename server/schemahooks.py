"""schema hooks:

- synchronize the living schema object with the persistent schema
- perform physical update on the source when necessary

checking for schema consistency is done in hooks.py

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from yams.schema import BASE_TYPES
from yams.buildobjs import EntityType, RelationType, RelationDefinition
from yams.schema2sql import eschema2sql, rschema2sql, type_from_constraints

from logilab.common.decorators import clear_cache

from cubicweb import ValidationError, RepositoryError
from cubicweb.schema import META_RTYPES, VIRTUAL_RTYPES, CONSTRAINTS
from cubicweb.server import schemaserial as ss
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.server.pool import Operation, SingleLastOperation, PreCommitOperation
from cubicweb.server.hookhelper import (entity_attr, entity_name,
                                        check_internal_entity)


TYPE_CONVERTER = { # XXX
    'Boolean': bool,
    'Int': int,
    'Float': float,
    'Password': str,
    'String': unicode,
    'Date' : unicode,
    'Datetime' : unicode,
    'Time' : unicode,
    }

# core entity and relation types which can't be removed
CORE_ETYPES = list(BASE_TYPES) + ['CWEType', 'CWRType', 'CWUser', 'CWGroup',
                                  'CWConstraint', 'CWAttribute', 'CWRelation']
CORE_RTYPES = ['eid', 'creation_date', 'modification_date', 'cwuri',
               'login', 'upassword', 'name',
               'is', 'instanceof', 'owned_by', 'created_by', 'in_group',
               'relation_type', 'from_entity', 'to_entity',
               'constrainted_by',
               'read_permission', 'add_permission',
               'delete_permission', 'updated_permission',
               ]

def get_constraints(session, entity):
    constraints = []
    for cstreid in session.transaction_data.get(entity.eid, ()):
        cstrent = session.entity_from_eid(cstreid)
        cstr = CONSTRAINTS[cstrent.type].deserialize(cstrent.value)
        cstr.eid = cstreid
        constraints.append(cstr)
    return constraints

def add_inline_relation_column(session, etype, rtype):
    """add necessary column and index for an inlined relation"""
    table = SQL_PREFIX + etype
    column = SQL_PREFIX + rtype
    try:
        session.system_sql(str('ALTER TABLE %s ADD COLUMN %s integer'
                               % (table, column)), rollback_on_failure=False)
        session.info('added column %s to table %s', column, table)
    except:
        # silent exception here, if this error has not been raised because the
        # column already exists, index creation will fail anyway
        session.exception('error while adding column %s to table %s',
                          table, column)
    # create index before alter table which may expectingly fail during test
    # (sqlite) while index creation should never fail (test for index existence
    # is done by the dbhelper)
    session.pool.source('system').create_index(session, table, column)
    session.info('added index on %s(%s)', table, column)
    session.transaction_data.setdefault('createdattrs', []).append(
        '%s.%s' % (etype, rtype))


# operations for low-level database alteration  ################################

class DropTable(PreCommitOperation):
    """actually remove a database from the instance's schema"""
    table = None # make pylint happy
    def precommit_event(self):
        dropped = self.session.transaction_data.setdefault('droppedtables',
                                                           set())
        if self.table in dropped:
            return # already processed
        dropped.add(self.table)
        self.session.system_sql('DROP TABLE %s' % self.table)
        self.info('dropped table %s', self.table)


class DropRelationTable(DropTable):
    def __init__(self, session, rtype):
        super(DropRelationTable, self).__init__(
            session, table='%s_relation' % rtype)
        session.transaction_data.setdefault('pendingrtypes', set()).add(rtype)


class DropColumn(PreCommitOperation):
    """actually remove the attribut's column from entity table in the system
    database
    """
    table = column = None # make pylint happy
    def precommit_event(self):
        session, table, column = self.session, self.table, self.column
        # drop index if any
        session.pool.source('system').drop_index(session, table, column)
        try:
            session.system_sql('ALTER TABLE %s DROP COLUMN %s'
                               % (table, column), rollback_on_failure=False)
            self.info('dropped column %s from table %s', column, table)
        except Exception, ex:
            # not supported by sqlite for instance
            self.error('error while altering table %s: %s', table, ex)


# base operations for in-memory schema synchronization  ########################

class MemSchemaNotifyChanges(SingleLastOperation):
    """the update schema operation:

    special operation which should be called once and after all other schema
    operations. It will trigger internal structures rebuilding to consider
    schema changes
    """

    def __init__(self, session):
        self.repo = session.repo
        SingleLastOperation.__init__(self, session)

    def precommit_event(self):
        for eschema in self.repo.schema.entities():
            if not eschema.final:
                clear_cache(eschema, 'ordered_relations')

    def commit_event(self):
        rebuildinfered = self.session.data.get('rebuild-infered', True)
        self.repo.set_schema(self.repo.schema, rebuildinfered=rebuildinfered)

    def rollback_event(self):
        self.precommit_event()


class MemSchemaOperation(Operation):
    """base class for schema operations"""
    def __init__(self, session, kobj=None, **kwargs):
        self.schema = session.schema
        self.kobj = kobj
        # once Operation.__init__ has been called, event may be triggered, so
        # do this last !
        Operation.__init__(self, session, **kwargs)
        # every schema operation is triggering a schema update
        MemSchemaNotifyChanges(session)

    def prepare_constraints(self, subjtype, rtype, objtype):
        constraints = rtype.rproperty(subjtype, objtype, 'constraints')
        self.constraints = list(constraints)
        rtype.set_rproperty(subjtype, objtype, 'constraints', self.constraints)


class MemSchemaEarlyOperation(MemSchemaOperation):
    def insert_index(self):
        """schema operation which are inserted at the begining of the queue
        (typically to add/remove entity or relation types)
        """
        i = -1
        for i, op in enumerate(self.session.pending_operations):
            if not isinstance(op, MemSchemaEarlyOperation):
                return i
        return i + 1


class MemSchemaPermissionOperation(MemSchemaOperation):
    """base class to synchronize schema permission definitions"""
    def __init__(self, session, perm, etype_eid):
        self.perm = perm
        try:
            self.name = entity_name(session, etype_eid)
        except IndexError:
            self.error('changing permission of a no more existant type #%s',
                etype_eid)
        else:
            Operation.__init__(self, session)


# operations for high-level source database alteration  ########################

class SourceDbCWETypeRename(PreCommitOperation):
    """this operation updates physical storage accordingly"""
    oldname = newname = None # make pylint happy

    def precommit_event(self):
        # we need sql to operate physical changes on the system database
        sqlexec = self.session.system_sql
        sqlexec('ALTER TABLE %s%s RENAME TO %s%s' % (SQL_PREFIX, self.oldname,
                                                     SQL_PREFIX, self.newname))
        self.info('renamed table %s to %s', self.oldname, self.newname)
        sqlexec('UPDATE entities SET type=%s WHERE type=%s',
                (self.newname, self.oldname))
        sqlexec('UPDATE deleted_entities SET type=%s WHERE type=%s',
                (self.newname, self.oldname))


class SourceDbCWRTypeUpdate(PreCommitOperation):
    """actually update some properties of a relation definition"""
    rschema = values = entity = None # make pylint happy

    def precommit_event(self):
        session = self.session
        rschema = self.rschema
        if rschema.final or not 'inlined' in self.values:
            return # nothing to do
        inlined = self.values['inlined']
        entity = self.entity
        # check in-lining is necessary / possible
        if not entity.inlined_changed(inlined):
            return # nothing to do
        # inlined changed, make necessary physical changes!
        sqlexec = self.session.system_sql
        rtype = rschema.type
        eidcolumn = SQL_PREFIX + 'eid'
        if not inlined:
            # need to create the relation if it has not been already done by
            # another event of the same transaction
            if not rschema.type in session.transaction_data.get('createdtables', ()):
                tablesql = rschema2sql(rschema)
                # create the necessary table
                for sql in tablesql.split(';'):
                    if sql.strip():
                        sqlexec(sql)
                session.transaction_data.setdefault('createdtables', []).append(
                    rschema.type)
            # copy existant data
            column = SQL_PREFIX + rtype
            for etype in rschema.subjects():
                table = SQL_PREFIX + str(etype)
                sqlexec('INSERT INTO %s_relation SELECT %s, %s FROM %s WHERE NOT %s IS NULL'
                        % (rtype, eidcolumn, column, table, column))
            # drop existant columns
            for etype in rschema.subjects():
                DropColumn(session, table=SQL_PREFIX + str(etype),
                             column=SQL_PREFIX + rtype)
        else:
            for etype in rschema.subjects():
                try:
                    add_inline_relation_column(session, str(etype), rtype)
                except Exception, ex:
                    # the column probably already exists. this occurs when the
                    # entity's type has just been added or if the column has not
                    # been previously dropped
                    self.error('error while altering table %s: %s', etype, ex)
                # copy existant data.
                # XXX don't use, it's not supported by sqlite (at least at when i tried it)
                #sqlexec('UPDATE %(etype)s SET %(rtype)s=eid_to '
                #        'FROM %(rtype)s_relation '
                #        'WHERE %(etype)s.eid=%(rtype)s_relation.eid_from'
                #        % locals())
                table = SQL_PREFIX + str(etype)
                cursor = sqlexec('SELECT eid_from, eid_to FROM %(table)s, '
                                 '%(rtype)s_relation WHERE %(table)s.%(eidcolumn)s='
                                 '%(rtype)s_relation.eid_from' % locals())
                args = [{'val': eid_to, 'x': eid} for eid, eid_to in cursor.fetchall()]
                if args:
                    column = SQL_PREFIX + rtype
                    cursor.executemany('UPDATE %s SET %s=%%(val)s WHERE %s=%%(x)s'
                                       % (table, column, eidcolumn), args)
                # drop existant table
                DropRelationTable(session, rtype)


class SourceDbCWAttributeAdd(PreCommitOperation):
    """an attribute relation (CWAttribute) has been added:
    * add the necessary column
    * set default on this column if any and possible
    * register an operation to add the relation definition to the
      instance's schema on commit

    constraints are handled by specific hooks
    """
    entity = None # make pylint happy

    def init_rdef(self, **kwargs):
        entity = self.entity
        fromentity = entity.stype
        self.session.execute('SET X ordernum Y+1 '
                             'WHERE X from_entity SE, SE eid %(se)s, X ordernum Y, '
                             'X ordernum >= %(order)s, NOT X eid %(x)s',
                             {'x': entity.eid, 'se': fromentity.eid,
                              'order': entity.ordernum or 0})
        subj = str(fromentity.name)
        rtype = entity.rtype.name
        obj = str(entity.otype.name)
        constraints = get_constraints(self.session, entity)
        rdef = RelationDefinition(subj, rtype, obj,
                                  description=entity.description,
                                  cardinality=entity.cardinality,
                                  constraints=constraints,
                                  order=entity.ordernum,
                                  eid=entity.eid,
                                  **kwargs)
        MemSchemaRDefAdd(self.session, rdef)
        return rdef

    def precommit_event(self):
        session = self.session
        entity = self.entity
        # entity.defaultval is a string or None, but we need a correctly typed
        # value
        default = entity.defaultval
        if default is not None:
            default = TYPE_CONVERTER[entity.otype.name](default)
        props = {'default': default,
                 'indexed': entity.indexed,
                 'fulltextindexed': entity.fulltextindexed,
                 'internationalizable': entity.internationalizable}
        rdef = self.init_rdef(**props)
        sysource = session.pool.source('system')
        attrtype = type_from_constraints(sysource.dbhelper, rdef.object,
                                         rdef.constraints)
        # XXX should be moved somehow into lgc.adbh: sqlite doesn't support to
        # add a new column with UNIQUE, it should be added after the ALTER TABLE
        # using ADD INDEX
        if sysource.dbdriver == 'sqlite' and 'UNIQUE' in attrtype:
            extra_unique_index = True
            attrtype = attrtype.replace(' UNIQUE', '')
        else:
            extra_unique_index = False
        # added some str() wrapping query since some backend (eg psycopg) don't
        # allow unicode queries
        table = SQL_PREFIX + rdef.subject
        column = SQL_PREFIX + rdef.name
        try:
            session.system_sql(str('ALTER TABLE %s ADD COLUMN %s %s'
                                   % (table, column, attrtype)),
                               rollback_on_failure=False)
            self.info('added column %s to table %s', table, column)
        except Exception, ex:
            # the column probably already exists. this occurs when
            # the entity's type has just been added or if the column
            # has not been previously dropped
            self.error('error while altering table %s: %s', table, ex)
        if extra_unique_index or entity.indexed:
            try:
                sysource.create_index(session, table, column,
                                      unique=extra_unique_index)
            except Exception, ex:
                self.error('error while creating index for %s.%s: %s',
                           table, column, ex)
        # final relations are not infered, propagate
        try:
            eschema = self.schema.eschema(rdef.subject)
        except KeyError:
            return # entity type currently being added
        # propagate attribute to children classes
        rschema = self.schema.rschema(rdef.name)
        # if relation type has been inserted in the same transaction, its final
        # attribute is still set to False, so we've to ensure it's False
        rschema.final = True
        # XXX 'infered': True/False, not clear actually
        props.update({'constraints': rdef.constraints,
                      'description': rdef.description,
                      'cardinality': rdef.cardinality,
                      'constraints': rdef.constraints,
                      'order': rdef.order})
        for specialization in eschema.specialized_by(False):
            if rschema.has_rdef(specialization, rdef.object):
                continue
            for rql, args in ss.frdef2rql(rschema, str(specialization),
                                          rdef.object, props):
                session.execute(rql, args)
        # set default value, using sql for performance and to avoid
        # modification_date update
        if default:
            session.system_sql('UPDATE %s SET %s=%%(default)s' % (table, column),
                               {'default': default})


class SourceDbCWRelationAdd(SourceDbCWAttributeAdd):
    """an actual relation has been added:
    * if this is an inlined relation, add the necessary column
      else if it's the first instance of this relation type, add the
      necessary table and set default permissions
    * register an operation to add the relation definition to the
      instance's schema on commit

    constraints are handled by specific hooks
    """
    entity = None # make pylint happy

    def precommit_event(self):
        session = self.session
        entity = self.entity
        rdef = self.init_rdef(composite=entity.composite)
        schema = session.schema
        rtype = rdef.name
        rschema = session.schema.rschema(rtype)
        # this have to be done before permissions setting
        if rschema.inlined:
            # need to add a column if the relation is inlined and if this is the
            # first occurence of "Subject relation Something" whatever Something
            # and if it has not been added during other event of the same
            # transaction
            key = '%s.%s' % (rdef.subject, rtype)
            try:
                alreadythere = bool(rschema.objects(rdef.subject))
            except KeyError:
                alreadythere = False
            if not (alreadythere or
                    key in session.transaction_data.get('createdattrs', ())):
                add_inline_relation_column(session, rdef.subject, rtype)
        else:
            # need to create the relation if no relation definition in the
            # schema and if it has not been added during other event of the same
            # transaction
            if not (rschema.subjects() or
                    rtype in session.transaction_data.get('createdtables', ())):
                try:
                    rschema = session.schema.rschema(rtype)
                    tablesql = rschema2sql(rschema)
                except KeyError:
                    # fake we add it to the schema now to get a correctly
                    # initialized schema but remove it before doing anything
                    # more dangerous...
                    rschema = session.schema.add_relation_type(rdef)
                    tablesql = rschema2sql(rschema)
                    session.schema.del_relation_type(rtype)
                # create the necessary table
                for sql in tablesql.split(';'):
                    if sql.strip():
                        session.system_sql(sql)
                session.transaction_data.setdefault('createdtables', []).append(
                    rtype)


class SourceDbRDefUpdate(PreCommitOperation):
    """actually update some properties of a relation definition"""
    rschema = values = None # make pylint happy

    def precommit_event(self):
        etype = self.kobj[0]
        table = SQL_PREFIX + etype
        column = SQL_PREFIX + self.rschema.type
        if 'indexed' in self.values:
            sysource = self.session.pool.source('system')
            if self.values['indexed']:
                sysource.create_index(self.session, table, column)
            else:
                sysource.drop_index(self.session, table, column)
        if 'cardinality' in self.values and self.rschema.final:
            adbh = self.session.pool.source('system').dbhelper
            if not adbh.alter_column_support:
                # not supported (and NOT NULL not set by yams in that case, so
                # no worry)
                return
            atype = self.rschema.objects(etype)[0]
            constraints = self.rschema.rproperty(etype, atype, 'constraints')
            coltype = type_from_constraints(adbh, atype, constraints,
                                            creating=False)
            # XXX check self.values['cardinality'][0] actually changed?
            sql = adbh.sql_set_null_allowed(table, column, coltype,
                                            self.values['cardinality'][0] != '1')
            self.session.system_sql(sql)


class SourceDbCWConstraintAdd(PreCommitOperation):
    """actually update constraint of a relation definition"""
    entity = None # make pylint happy
    cancelled = False

    def precommit_event(self):
        rdef = self.entity.reverse_constrained_by[0]
        session = self.session
        # when the relation is added in the same transaction, the constraint
        # object is created by the operation adding the attribute or relation,
        # so there is nothing to do here
        if rdef.eid in session.transaction_data.get('neweids', ()):
            return
        subjtype, rtype, objtype = session.schema.schema_by_eid(rdef.eid)
        cstrtype = self.entity.type
        oldcstr = rtype.constraint_by_type(subjtype, objtype, cstrtype)
        newcstr = CONSTRAINTS[cstrtype].deserialize(self.entity.value)
        table = SQL_PREFIX + str(subjtype)
        column = SQL_PREFIX + str(rtype)
        # alter the physical schema on size constraint changes
        if newcstr.type() == 'SizeConstraint' and (
            oldcstr is None or oldcstr.max != newcstr.max):
            adbh = self.session.pool.source('system').dbhelper
            card = rtype.rproperty(subjtype, objtype, 'cardinality')
            coltype = type_from_constraints(adbh, objtype, [newcstr],
                                            creating=False)
            sql = adbh.sql_change_col_type(table, column, coltype, card != '1')
            try:
                session.system_sql(sql, rollback_on_failure=False)
                self.info('altered column %s of table %s: now VARCHAR(%s)',
                          column, table, newcstr.max)
            except Exception, ex:
                # not supported by sqlite for instance
                self.error('error while altering table %s: %s', table, ex)
        elif cstrtype == 'UniqueConstraint' and oldcstr is None:
            session.pool.source('system').create_index(
                self.session, table, column, unique=True)


class SourceDbCWConstraintDel(PreCommitOperation):
    """actually remove a constraint of a relation definition"""
    rtype = subjtype = objtype = None # make pylint happy

    def precommit_event(self):
        cstrtype = self.cstr.type()
        table = SQL_PREFIX + str(self.subjtype)
        column = SQL_PREFIX + str(self.rtype)
        # alter the physical schema on size/unique constraint changes
        if cstrtype == 'SizeConstraint':
            try:
                self.session.system_sql('ALTER TABLE %s ALTER COLUMN %s TYPE TEXT'
                                        % (table, column),
                                        rollback_on_failure=False)
                self.info('altered column %s of table %s: now TEXT',
                          column, table)
            except Exception, ex:
                # not supported by sqlite for instance
                self.error('error while altering table %s: %s', table, ex)
        elif cstrtype == 'UniqueConstraint':
            self.session.pool.source('system').drop_index(
                self.session, table, column, unique=True)


# operations for in-memory schema synchronization  #############################

class MemSchemaCWETypeAdd(MemSchemaEarlyOperation):
    """actually add the entity type to the instance's schema"""
    eid = None # make pylint happy
    def commit_event(self):
        self.schema.add_entity_type(self.kobj)


class MemSchemaCWETypeRename(MemSchemaOperation):
    """this operation updates physical storage accordingly"""
    oldname = newname = None # make pylint happy

    def commit_event(self):
        self.session.schema.rename_entity_type(self.oldname, self.newname)


class MemSchemaCWETypeDel(MemSchemaOperation):
    """actually remove the entity type from the instance's schema"""
    def commit_event(self):
        try:
            # del_entity_type also removes entity's relations
            self.schema.del_entity_type(self.kobj)
        except KeyError:
            # s/o entity type have already been deleted
            pass


class MemSchemaCWRTypeAdd(MemSchemaEarlyOperation):
    """actually add the relation type to the instance's schema"""
    eid = None # make pylint happy
    def commit_event(self):
        rschema = self.schema.add_relation_type(self.kobj)
        rschema.set_default_groups()


class MemSchemaCWRTypeUpdate(MemSchemaOperation):
    """actually update some properties of a relation definition"""
    rschema = values = None # make pylint happy

    def commit_event(self):
        # structure should be clean, not need to remove entity's relations
        # at this point
        self.rschema.__dict__.update(self.values)


class MemSchemaCWRTypeDel(MemSchemaOperation):
    """actually remove the relation type from the instance's schema"""
    def commit_event(self):
        try:
            self.schema.del_relation_type(self.kobj)
        except KeyError:
            # s/o entity type have already been deleted
            pass


class MemSchemaRDefAdd(MemSchemaEarlyOperation):
    """actually add the attribute relation definition to the instance's
    schema
    """
    def commit_event(self):
        self.schema.add_relation_def(self.kobj)


class MemSchemaRDefUpdate(MemSchemaOperation):
    """actually update some properties of a relation definition"""
    rschema = values = None # make pylint happy

    def commit_event(self):
        # structure should be clean, not need to remove entity's relations
        # at this point
        self.rschema._rproperties[self.kobj].update(self.values)


class MemSchemaRDefDel(MemSchemaOperation):
    """actually remove the relation definition from the instance's schema"""
    def commit_event(self):
        subjtype, rtype, objtype = self.kobj
        try:
            self.schema.del_relation_def(subjtype, rtype, objtype)
        except KeyError:
            # relation type may have been already deleted
            pass


class MemSchemaCWConstraintAdd(MemSchemaOperation):
    """actually update constraint of a relation definition

    has to be called before SourceDbCWConstraintAdd
    """
    cancelled = False

    def precommit_event(self):
        rdef = self.entity.reverse_constrained_by[0]
        # when the relation is added in the same transaction, the constraint
        # object is created by the operation adding the attribute or relation,
        # so there is nothing to do here
        if rdef.eid in self.session.transaction_data.get('neweids', ()):
            self.cancelled = True
            return
        subjtype, rtype, objtype = self.session.schema.schema_by_eid(rdef.eid)
        self.prepare_constraints(subjtype, rtype, objtype)
        cstrtype = self.entity.type
        self.cstr = rtype.constraint_by_type(subjtype, objtype, cstrtype)
        self.newcstr = CONSTRAINTS[cstrtype].deserialize(self.entity.value)
        self.newcstr.eid = self.entity.eid

    def commit_event(self):
        if self.cancelled:
            return
        # in-place modification
        if not self.cstr is None:
            self.constraints.remove(self.cstr)
        self.constraints.append(self.newcstr)


class MemSchemaCWConstraintDel(MemSchemaOperation):
    """actually remove a constraint of a relation definition

    has to be called before SourceDbCWConstraintDel
    """
    rtype = subjtype = objtype = None # make pylint happy
    def precommit_event(self):
        self.prepare_constraints(self.subjtype, self.rtype, self.objtype)

    def commit_event(self):
        self.constraints.remove(self.cstr)


class MemSchemaPermissionCWGroupAdd(MemSchemaPermissionOperation):
    """synchronize schema when a *_permission relation has been added on a group
    """
    def __init__(self, session, perm, etype_eid, group_eid):
        self.group = entity_name(session, group_eid)
        super(MemSchemaPermissionCWGroupAdd, self).__init__(
            session, perm, etype_eid)

    def commit_event(self):
        """the observed connections pool has been commited"""
        try:
            erschema = self.schema[self.name]
        except KeyError:
            # duh, schema not found, log error and skip operation
            self.error('no schema for %s', self.name)
            return
        groups = list(erschema.get_groups(self.perm))
        try:
            groups.index(self.group)
            self.warning('group %s already have permission %s on %s',
                         self.group, self.perm, erschema.type)
        except ValueError:
            groups.append(self.group)
            erschema.set_groups(self.perm, groups)


class MemSchemaPermissionCWGroupDel(MemSchemaPermissionCWGroupAdd):
    """synchronize schema when a *_permission relation has been deleted from a
    group
    """

    def commit_event(self):
        """the observed connections pool has been commited"""
        try:
            erschema = self.schema[self.name]
        except KeyError:
            # duh, schema not found, log error and skip operation
            self.error('no schema for %s', self.name)
            return
        groups = list(erschema.get_groups(self.perm))
        try:
            groups.remove(self.group)
            erschema.set_groups(self.perm, groups)
        except ValueError:
            self.error('can\'t remove permission %s on %s to group %s',
                self.perm, erschema.type, self.group)


class MemSchemaPermissionRQLExpressionAdd(MemSchemaPermissionOperation):
    """synchronize schema when a *_permission relation has been added on a rql
    expression
    """
    def __init__(self, session, perm, etype_eid, expression):
        self.expr = expression
        super(MemSchemaPermissionRQLExpressionAdd, self).__init__(
            session, perm, etype_eid)

    def commit_event(self):
        """the observed connections pool has been commited"""
        try:
            erschema = self.schema[self.name]
        except KeyError:
            # duh, schema not found, log error and skip operation
            self.error('no schema for %s', self.name)
            return
        exprs = list(erschema.get_rqlexprs(self.perm))
        exprs.append(erschema.rql_expression(self.expr))
        erschema.set_rqlexprs(self.perm, exprs)


class MemSchemaPermissionRQLExpressionDel(MemSchemaPermissionRQLExpressionAdd):
    """synchronize schema when a *_permission relation has been deleted from an
    rql expression
    """

    def commit_event(self):
        """the observed connections pool has been commited"""
        try:
            erschema = self.schema[self.name]
        except KeyError:
            # duh, schema not found, log error and skip operation
            self.error('no schema for %s', self.name)
            return
        rqlexprs = list(erschema.get_rqlexprs(self.perm))
        for i, rqlexpr in enumerate(rqlexprs):
            if rqlexpr.expression == self.expr:
                rqlexprs.pop(i)
                break
        else:
            self.error('can\'t remove permission %s on %s for expression %s',
                self.perm, erschema.type, self.expr)
            return
        erschema.set_rqlexprs(self.perm, rqlexprs)


class MemSchemaSpecializesAdd(MemSchemaOperation):

    def commit_event(self):
        eschema = self.session.schema.schema_by_eid(self.etypeeid)
        parenteschema = self.session.schema.schema_by_eid(self.parentetypeeid)
        eschema._specialized_type = parenteschema.type
        parenteschema._specialized_by.append(eschema.type)


class MemSchemaSpecializesDel(MemSchemaOperation):

    def commit_event(self):
        try:
            eschema = self.session.schema.schema_by_eid(self.etypeeid)
            parenteschema = self.session.schema.schema_by_eid(self.parentetypeeid)
        except KeyError:
            # etype removed, nothing to do
            return
        eschema._specialized_type = None
        parenteschema._specialized_by.remove(eschema.type)


# deletion hooks ###############################################################

def before_del_eetype(session, eid):
    """before deleting a CWEType entity:
    * check that we don't remove a core entity type
    * cascade to delete related CWAttribute and CWRelation entities
    * instantiate an operation to delete the entity type on commit
    """
    # final entities can't be deleted, don't care about that
    name = check_internal_entity(session, eid, CORE_ETYPES)
    # delete every entities of this type
    session.unsafe_execute('DELETE %s X' % name)
    DropTable(session, table=SQL_PREFIX + name)
    MemSchemaCWETypeDel(session, name)


def after_del_eetype(session, eid):
    # workflow cleanup
    session.execute('DELETE Workflow X WHERE NOT X workflow_of Y')


def before_del_ertype(session, eid):
    """before deleting a CWRType entity:
    * check that we don't remove a core relation type
    * cascade to delete related CWAttribute and CWRelation entities
    * instantiate an operation to delete the relation type on commit
    """
    name = check_internal_entity(session, eid, CORE_RTYPES)
    # delete relation definitions using this relation type
    session.execute('DELETE CWAttribute X WHERE X relation_type Y, Y eid %(x)s',
                    {'x': eid})
    session.execute('DELETE CWRelation X WHERE X relation_type Y, Y eid %(x)s',
                    {'x': eid})
    MemSchemaCWRTypeDel(session, name)


def after_del_relation_type(session, rdefeid, rtype, rteid):
    """before deleting a CWAttribute or CWRelation entity:
    * if this is a final or inlined relation definition, instantiate an
      operation to drop necessary column, else if this is the last instance
      of a non final relation, instantiate an operation to drop necessary
      table
    * instantiate an operation to delete the relation definition on commit
    * delete the associated relation type when necessary
    """
    subjschema, rschema, objschema = session.schema.schema_by_eid(rdefeid)
    pendings = session.transaction_data.get('pendingeids', ())
    pendingrdefs = session.transaction_data.setdefault('pendingrdefs', set())
    # first delete existing relation if necessary
    if rschema.final:
        rdeftype = 'CWAttribute'
        pendingrdefs.add((subjschema, rschema))
    else:
        rdeftype = 'CWRelation'
        pendingrdefs.add((subjschema, rschema, objschema))
        if not (subjschema.eid in pendings or objschema.eid in pendings):
            session.execute('DELETE X %s Y WHERE X is %s, Y is %s'
                            % (rschema, subjschema, objschema))
    execute = session.unsafe_execute
    rset = execute('Any COUNT(X) WHERE X is %s, X relation_type R,'
                   'R eid %%(x)s' % rdeftype, {'x': rteid})
    lastrel = rset[0][0] == 0
    # we have to update physical schema systematically for final and inlined
    # relations, but only if it's the last instance for this relation type
    # for other relations

    if (rschema.final or rschema.inlined):
        rset = execute('Any COUNT(X) WHERE X is %s, X relation_type R, '
                       'R eid %%(x)s, X from_entity E, E name %%(name)s'
                       % rdeftype, {'x': rteid, 'name': str(subjschema)})
        if rset[0][0] == 0 and not subjschema.eid in pendings:
            ptypes = session.transaction_data.setdefault('pendingrtypes', set())
            ptypes.add(rschema.type)
            DropColumn(session, table=SQL_PREFIX + subjschema.type,
                         column=SQL_PREFIX + rschema.type)
    elif lastrel:
        DropRelationTable(session, rschema.type)
    # if this is the last instance, drop associated relation type
    if lastrel and not rteid in pendings:
        execute('DELETE CWRType X WHERE X eid %(x)s', {'x': rteid}, 'x')
    MemSchemaRDefDel(session, (subjschema, rschema, objschema))


# addition hooks ###############################################################

def before_add_eetype(session, entity):
    """before adding a CWEType entity:
    * check that we are not using an existing entity type,
    """
    name = entity['name']
    schema = session.schema
    if name in schema and schema[name].eid is not None:
        raise RepositoryError('an entity type %s already exists' % name)

def after_add_eetype(session, entity):
    """after adding a CWEType entity:
    * create the necessary table
    * set creation_date and modification_date by creating the necessary
      CWAttribute entities
    * add owned_by relation by creating the necessary CWRelation entity
    * register an operation to add the entity type to the instance's
      schema on commit
    """
    if entity.get('final'):
        return
    schema = session.schema
    name = entity['name']
    etype = EntityType(name=name, description=entity.get('description'),
                       meta=entity.get('meta')) # don't care about final
    # fake we add it to the schema now to get a correctly initialized schema
    # but remove it before doing anything more dangerous...
    schema = session.schema
    eschema = schema.add_entity_type(etype)
    eschema.set_default_groups()
    # generate table sql and rql to add metadata
    tablesql = eschema2sql(session.pool.source('system').dbhelper, eschema,
                           prefix=SQL_PREFIX)
    relrqls = []
    for rtype in (META_RTYPES - VIRTUAL_RTYPES):
        rschema = schema[rtype]
        sampletype = rschema.subjects()[0]
        desttype = rschema.objects()[0]
        props = rschema.rproperties(sampletype, desttype)
        relrqls += list(ss.rdef2rql(rschema, name, desttype, props))
    # now remove it !
    schema.del_entity_type(name)
    # create the necessary table
    for sql in tablesql.split(';'):
        if sql.strip():
            session.system_sql(sql)
    # register operation to modify the schema on commit
    # this have to be done before adding other relations definitions
    # or permission settings
    etype.eid = entity.eid
    MemSchemaCWETypeAdd(session, etype)
    # add meta relations
    for rql, kwargs in relrqls:
        session.execute(rql, kwargs)


def before_add_ertype(session, entity):
    """before adding a CWRType entity:
    * check that we are not using an existing relation type,
    * register an operation to add the relation type to the instance's
      schema on commit

    We don't know yeat this point if a table is necessary
    """
    name = entity['name']
    if name in session.schema.relations():
        raise RepositoryError('a relation type %s already exists' % name)


def after_add_ertype(session, entity):
    """after a CWRType entity has been added:
    * register an operation to add the relation type to the instance's
      schema on commit
    We don't know yeat this point if a table is necessary
    """
    rtype = RelationType(name=entity['name'],
                         description=entity.get('description'),
                         meta=entity.get('meta', False),
                         inlined=entity.get('inlined', False),
                         symetric=entity.get('symetric', False))
    rtype.eid = entity.eid
    MemSchemaCWRTypeAdd(session, rtype)


def after_add_efrdef(session, entity):
    SourceDbCWAttributeAdd(session, entity=entity)

def after_add_enfrdef(session, entity):
    SourceDbCWRelationAdd(session, entity=entity)


# update hooks #################################################################

def check_valid_changes(session, entity, ro_attrs=('name', 'final')):
    errors = {}
    # don't use getattr(entity, attr), we would get the modified value if any
    for attr in ro_attrs:
        origval = entity_attr(session, entity.eid, attr)
        if entity.get(attr, origval) != origval:
            errors[attr] = session._("can't change the %s attribute") % \
                           display_name(session, attr)
    if errors:
        raise ValidationError(entity.eid, errors)

def before_update_eetype(session, entity):
    """check name change, handle final"""
    check_valid_changes(session, entity, ro_attrs=('final',))
    # don't use getattr(entity, attr), we would get the modified value if any
    oldname = entity_attr(session, entity.eid, 'name')
    newname = entity.get('name', oldname)
    if newname.lower() != oldname.lower():
        SourceDbCWETypeRename(session, oldname=oldname, newname=newname)
        MemSchemaCWETypeRename(session, oldname=oldname, newname=newname)

def before_update_ertype(session, entity):
    """check name change, handle final"""
    check_valid_changes(session, entity)


def after_update_erdef(session, entity):
    if entity.eid in session.transaction_data.get('pendingeids', ()):
        return
    desttype = entity.otype.name
    rschema = session.schema[entity.rtype.name]
    newvalues = {}
    for prop in rschema.rproperty_defs(desttype):
        if prop == 'constraints':
            continue
        if prop == 'order':
            prop = 'ordernum'
        if prop in entity.edited_attributes:
            newvalues[prop] = entity[prop]
    if newvalues:
        subjtype = entity.stype.name
        MemSchemaRDefUpdate(session, kobj=(subjtype, desttype),
                            rschema=rschema, values=newvalues)
        SourceDbRDefUpdate(session, kobj=(subjtype, desttype),
                           rschema=rschema, values=newvalues)

def after_update_ertype(session, entity):
    rschema = session.schema.rschema(entity.name)
    newvalues = {}
    for prop in ('meta', 'symetric', 'inlined'):
        if prop in entity:
            newvalues[prop] = entity[prop]
    if newvalues:
        MemSchemaCWRTypeUpdate(session, rschema=rschema, values=newvalues)
        SourceDbCWRTypeUpdate(session, rschema=rschema, values=newvalues,
                              entity=entity)

# constraints synchronization hooks ############################################

def after_add_econstraint(session, entity):
    MemSchemaCWConstraintAdd(session, entity=entity)
    SourceDbCWConstraintAdd(session, entity=entity)


def after_update_econstraint(session, entity):
    MemSchemaCWConstraintAdd(session, entity=entity)
    SourceDbCWConstraintAdd(session, entity=entity)


def before_delete_constrained_by(session, fromeid, rtype, toeid):
    if not fromeid in session.transaction_data.get('pendingeids', ()):
        schema = session.schema
        entity = session.entity_from_eid(toeid)
        subjtype, rtype, objtype = schema.schema_by_eid(fromeid)
        try:
            cstr = rtype.constraint_by_type(subjtype, objtype,
                                            entity.cstrtype[0].name)
        except IndexError:
            session.critical('constraint type no more accessible')
        else:
            SourceDbCWConstraintDel(session, subjtype=subjtype, rtype=rtype,
                                    objtype=objtype, cstr=cstr)
            MemSchemaCWConstraintDel(session, subjtype=subjtype, rtype=rtype,
                                     objtype=objtype, cstr=cstr)


def after_add_constrained_by(session, fromeid, rtype, toeid):
    if fromeid in session.transaction_data.get('neweids', ()):
        session.transaction_data.setdefault(fromeid, []).append(toeid)


# permissions synchronization hooks ############################################

def after_add_permission(session, subject, rtype, object):
    """added entity/relation *_permission, need to update schema"""
    perm = rtype.split('_', 1)[0]
    if session.describe(object)[0] == 'CWGroup':
        MemSchemaPermissionCWGroupAdd(session, perm, subject, object)
    else: # RQLExpression
        expr = session.execute('Any EXPR WHERE X eid %(x)s, X expression EXPR',
                               {'x': object}, 'x')[0][0]
        MemSchemaPermissionRQLExpressionAdd(session, perm, subject, expr)


def before_del_permission(session, subject, rtype, object):
    """delete entity/relation *_permission, need to update schema

    skip the operation if the related type is being deleted
    """
    if subject in session.transaction_data.get('pendingeids', ()):
        return
    perm = rtype.split('_', 1)[0]
    if session.describe(object)[0] == 'CWGroup':
        MemSchemaPermissionCWGroupDel(session, perm, subject, object)
    else: # RQLExpression
        expr = session.execute('Any EXPR WHERE X eid %(x)s, X expression EXPR',
                               {'x': object}, 'x')[0][0]
        MemSchemaPermissionRQLExpressionDel(session, perm, subject, expr)


def after_add_specializes(session, subject, rtype, object):
    MemSchemaSpecializesAdd(session, etypeeid=subject, parentetypeeid=object)

def after_del_specializes(session, subject, rtype, object):
    MemSchemaSpecializesDel(session, etypeeid=subject, parentetypeeid=object)


def _register_schema_hooks(hm):
    """register schema related hooks on the hooks manager"""
    # schema synchronisation #####################
    # before/after add
    hm.register_hook(before_add_eetype, 'before_add_entity', 'CWEType')
    hm.register_hook(before_add_ertype, 'before_add_entity', 'CWRType')
    hm.register_hook(after_add_eetype, 'after_add_entity', 'CWEType')
    hm.register_hook(after_add_ertype, 'after_add_entity', 'CWRType')
    hm.register_hook(after_add_efrdef, 'after_add_entity', 'CWAttribute')
    hm.register_hook(after_add_enfrdef, 'after_add_entity', 'CWRelation')
    # before/after update
    hm.register_hook(before_update_eetype, 'before_update_entity', 'CWEType')
    hm.register_hook(before_update_ertype, 'before_update_entity', 'CWRType')
    hm.register_hook(after_update_ertype, 'after_update_entity', 'CWRType')
    hm.register_hook(after_update_erdef, 'after_update_entity', 'CWAttribute')
    hm.register_hook(after_update_erdef, 'after_update_entity', 'CWRelation')
    # before/after delete
    hm.register_hook(before_del_eetype, 'before_delete_entity', 'CWEType')
    hm.register_hook(after_del_eetype, 'after_delete_entity', 'CWEType')
    hm.register_hook(before_del_ertype, 'before_delete_entity', 'CWRType')
    hm.register_hook(after_del_relation_type, 'after_delete_relation', 'relation_type')
    hm.register_hook(after_add_specializes, 'after_add_relation', 'specializes')
    hm.register_hook(after_del_specializes, 'after_delete_relation', 'specializes')
    # constraints synchronization hooks
    hm.register_hook(after_add_econstraint, 'after_add_entity', 'CWConstraint')
    hm.register_hook(after_update_econstraint, 'after_update_entity', 'CWConstraint')
    hm.register_hook(before_delete_constrained_by, 'before_delete_relation', 'constrained_by')
    hm.register_hook(after_add_constrained_by, 'after_add_relation', 'constrained_by')
    # permissions synchronisation ################
    for perm in ('read_permission', 'add_permission',
                 'delete_permission', 'update_permission'):
        hm.register_hook(after_add_permission, 'after_add_relation', perm)
        hm.register_hook(before_del_permission, 'before_delete_relation', perm)
