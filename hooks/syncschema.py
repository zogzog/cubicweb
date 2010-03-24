"""schema hooks:

- synchronize the living schema object with the persistent schema
- perform physical update on the source when necessary

checking for schema consistency is done in hooks.py

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from yams.schema import BASE_TYPES, RelationSchema, RelationDefinitionSchema
from yams.buildobjs import EntityType, RelationType, RelationDefinition
from yams.schema2sql import eschema2sql, rschema2sql, type_from_constraints

from logilab.common.decorators import clear_cache

from cubicweb import ValidationError
from cubicweb.selectors import implements
from cubicweb.schema import META_RTYPES, VIRTUAL_RTYPES, CONSTRAINTS, display_name
from cubicweb.server import hook, schemaserial as ss
from cubicweb.server.sqlutils import SQL_PREFIX


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

def group_mapping(cw):
    try:
        return cw.transaction_data['groupmap']
    except KeyError:
        cw.transaction_data['groupmap'] = gmap = ss.group_mapping(cw)
        return gmap

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


def check_valid_changes(session, entity, ro_attrs=('name', 'final')):
    errors = {}
    # don't use getattr(entity, attr), we would get the modified value if any
    for attr in entity.edited_attributes:
        if attr in ro_attrs:
            newval = entity.pop(attr)
            origval = getattr(entity, attr)
            if newval != origval:
                errors[attr] = session._("can't change the %s attribute") % \
                               display_name(session, attr)
            entity[attr] = newval
    if errors:
        raise ValidationError(entity.eid, errors)


# operations for low-level database alteration  ################################

class DropTable(hook.Operation):
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


class DropColumn(hook.Operation):
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

class MemSchemaNotifyChanges(hook.SingleLastOperation):
    """the update schema operation:

    special operation which should be called once and after all other schema
    operations. It will trigger internal structures rebuilding to consider
    schema changes.
    """

    def __init__(self, session):
        hook.SingleLastOperation.__init__(self, session)

    def precommit_event(self):
        for eschema in self.session.repo.schema.entities():
            if not eschema.final:
                clear_cache(eschema, 'ordered_relations')

    def commit_event(self):
        rebuildinfered = self.session.data.get('rebuild-infered', True)
        repo = self.session.repo
        # commit event should not raise error, while set_schema has chances to
        # do so because it triggers full vreg reloading
        try:
            repo.set_schema(repo.schema, rebuildinfered=rebuildinfered)
            # CWUser class might have changed, update current session users
            cwuser_cls = self.session.vreg['etypes'].etype_class('CWUser')
            for session in repo._sessions.values():
                session.user.__class__ = cwuser_cls
        except:
            self.critical('error while setting schmea', exc_info=True)

    def rollback_event(self):
        self.precommit_event()


class MemSchemaOperation(hook.Operation):
    """base class for schema operations"""
    def __init__(self, session, kobj=None, **kwargs):
        self.kobj = kobj
        # once Operation.__init__ has been called, event may be triggered, so
        # do this last !
        hook.Operation.__init__(self, session, **kwargs)
        # every schema operation is triggering a schema update
        MemSchemaNotifyChanges(session)

    def prepare_constraints(self, rdef):
        # if constraints is already a list, reuse it (we're updating multiple
        # constraints of the same rdef in the same transactions)
        if not isinstance(rdef.constraints, list):
            rdef.constraints = list(rdef.constraints)
        self.constraints = rdef.constraints


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


# operations for high-level source database alteration  ########################

class SourceDbCWETypeRename(hook.Operation):
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


class SourceDbCWRTypeUpdate(hook.Operation):
    """actually update some properties of a relation definition"""
    rschema = entity = values = None # make pylint happy

    def precommit_event(self):
        rschema = self.rschema
        if rschema.final:
            return
        session = self.session
        if 'fulltext_container' in self.values:
            ftiupdates = session.transaction_data.setdefault(
                'fti_update_etypes', set())
            for subjtype, objtype in rschema.rdefs:
                ftiupdates.add(subjtype)
                ftiupdates.add(objtype)
            UpdateFTIndexOp(session)
        if not 'inlined' in self.values:
            return # nothing to do
        inlined = self.values['inlined']
        # check in-lining is necessary / possible
        if inlined:
            self.entity.check_inlined_allowed()
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


class SourceDbCWAttributeAdd(hook.Operation):
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
            eschema = session.vreg.schema.eschema(rdef.subject)
        except KeyError:
            return # entity type currently being added
        # propagate attribute to children classes
        rschema = session.vreg.schema.rschema(rdef.name)
        # if relation type has been inserted in the same transaction, its final
        # attribute is still set to False, so we've to ensure it's False
        rschema.final = True
        # XXX 'infered': True/False, not clear actually
        props.update({'constraints': rdef.constraints,
                      'description': rdef.description,
                      'cardinality': rdef.cardinality,
                      'constraints': rdef.constraints,
                      'permissions': rdef.get_permissions(),
                      'order': rdef.order})
        groupmap = group_mapping(session)
        for specialization in eschema.specialized_by(False):
            if (specialization, rdef.object) in rschema.rdefs:
                continue
            sperdef = RelationDefinitionSchema(specialization, rschema, rdef.object, props)
            for rql, args in ss.rdef2rql(rschema, str(specialization),
                                         rdef.object, sperdef, groupmap=groupmap):
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
        schema = session.vreg.schema
        rtype = rdef.name
        rschema = schema.rschema(rtype)
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
                    rschema = schema.rschema(rtype)
                    tablesql = rschema2sql(rschema)
                except KeyError:
                    # fake we add it to the schema now to get a correctly
                    # initialized schema but remove it before doing anything
                    # more dangerous...
                    rschema = schema.add_relation_type(rdef)
                    tablesql = rschema2sql(rschema)
                    schema.del_relation_type(rtype)
                # create the necessary table
                for sql in tablesql.split(';'):
                    if sql.strip():
                        session.system_sql(sql)
                session.transaction_data.setdefault('createdtables', []).append(
                    rtype)


class SourceDbRDefUpdate(hook.Operation):
    """actually update some properties of a relation definition"""
    rschema = values = None # make pylint happy

    def precommit_event(self):
        session = self.session
        etype = self.kobj[0]
        table = SQL_PREFIX + etype
        column = SQL_PREFIX + self.rschema.type
        if 'indexed' in self.values:
            sysource = session.pool.source('system')
            if self.values['indexed']:
                sysource.create_index(session, table, column)
            else:
                sysource.drop_index(session, table, column)
        if 'cardinality' in self.values and self.rschema.final:
            adbh = session.pool.source('system').dbhelper
            if not adbh.alter_column_support:
                # not supported (and NOT NULL not set by yams in that case, so
                # no worry)
                return
            atype = self.rschema.objects(etype)[0]
            constraints = self.rschema.rdef(etype, atype).constraints
            coltype = type_from_constraints(adbh, atype, constraints,
                                            creating=False)
            # XXX check self.values['cardinality'][0] actually changed?
            sql = adbh.sql_set_null_allowed(table, column, coltype,
                                            self.values['cardinality'][0] != '1')
            session.system_sql(sql)
        if 'fulltextindexed' in self.values:
            UpdateFTIndexOp(session)
            session.transaction_data.setdefault(
                'fti_update_etypes', set()).add(etype)


class SourceDbCWConstraintAdd(hook.Operation):
    """actually update constraint of a relation definition"""
    entity = None # make pylint happy
    cancelled = False

    def precommit_event(self):
        rdef = self.entity.reverse_constrained_by[0]
        session = self.session
        # when the relation is added in the same transaction, the constraint
        # object is created by the operation adding the attribute or relation,
        # so there is nothing to do here
        if session.added_in_transaction(rdef.eid):
            return
        rdefschema = session.vreg.schema.schema_by_eid(rdef.eid)
        subjtype, rtype, objtype = rdefschema.as_triple()
        cstrtype = self.entity.type
        oldcstr = rtype.rdef(subjtype, objtype).constraint_by_type(cstrtype)
        newcstr = CONSTRAINTS[cstrtype].deserialize(self.entity.value)
        table = SQL_PREFIX + str(subjtype)
        column = SQL_PREFIX + str(rtype)
        # alter the physical schema on size constraint changes
        if newcstr.type() == 'SizeConstraint' and (
            oldcstr is None or oldcstr.max != newcstr.max):
            adbh = self.session.pool.source('system').dbhelper
            card = rtype.rdef(subjtype, objtype).cardinality
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


class SourceDbCWConstraintDel(hook.Operation):
    """actually remove a constraint of a relation definition"""
    rtype = subjtype = None # make pylint happy

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
        self.session.vreg.schema.add_entity_type(self.kobj)


class MemSchemaCWETypeRename(MemSchemaOperation):
    """this operation updates physical storage accordingly"""
    oldname = newname = None # make pylint happy

    def commit_event(self):
        self.session.vreg.schema.rename_entity_type(self.oldname, self.newname)


class MemSchemaCWETypeDel(MemSchemaOperation):
    """actually remove the entity type from the instance's schema"""
    def commit_event(self):
        try:
            # del_entity_type also removes entity's relations
            self.session.vreg.schema.del_entity_type(self.kobj)
        except KeyError:
            # s/o entity type have already been deleted
            pass


class MemSchemaCWRTypeAdd(MemSchemaEarlyOperation):
    """actually add the relation type to the instance's schema"""
    eid = None # make pylint happy
    def commit_event(self):
        self.session.vreg.schema.add_relation_type(self.kobj)


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
            self.session.vreg.schema.del_relation_type(self.kobj)
        except KeyError:
            # s/o entity type have already been deleted
            pass


class MemSchemaRDefAdd(MemSchemaEarlyOperation):
    """actually add the attribute relation definition to the instance's
    schema
    """
    def commit_event(self):
        self.session.vreg.schema.add_relation_def(self.kobj)


class MemSchemaRDefUpdate(MemSchemaOperation):
    """actually update some properties of a relation definition"""
    rschema = values = None # make pylint happy

    def commit_event(self):
        # structure should be clean, not need to remove entity's relations
        # at this point
        self.rschema.rdefs[self.kobj].update(self.values)


class MemSchemaRDefDel(MemSchemaOperation):
    """actually remove the relation definition from the instance's schema"""
    def commit_event(self):
        subjtype, rtype, objtype = self.kobj
        try:
            self.session.vreg.schema.del_relation_def(subjtype, rtype, objtype)
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
        if self.session.added_in_transaction(rdef.eid):
            self.cancelled = True
            return
        rdef = self.session.vreg.schema.schema_by_eid(rdef.eid)
        self.prepare_constraints(rdef)
        cstrtype = self.entity.type
        self.cstr = rdef.constraint_by_type(cstrtype)
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
        self.prepare_constraints(self.rdef)

    def commit_event(self):
        self.constraints.remove(self.cstr)


class MemSchemaPermissionAdd(MemSchemaOperation):
    """synchronize schema when a *_permission relation has been added on a group
    """

    def commit_event(self):
        """the observed connections pool has been commited"""
        try:
            erschema = self.session.vreg.schema.schema_by_eid(self.eid)
        except KeyError:
            # duh, schema not found, log error and skip operation
            self.warning('no schema for %s', self.eid)
            return
        perms = list(erschema.action_permissions(self.action))
        if hasattr(self, 'group_eid'):
            perm = self.session.entity_from_eid(self.group_eid).name
        else:
            perm = erschema.rql_expression(self.expr)
        try:
            perms.index(perm)
            self.warning('%s already in permissions for %s on %s',
                         perm, self.action, erschema)
        except ValueError:
            perms.append(perm)
            erschema.set_action_permissions(self.action, perms)


class MemSchemaPermissionDel(MemSchemaPermissionAdd):
    """synchronize schema when a *_permission relation has been deleted from a
    group
    """

    def commit_event(self):
        """the observed connections pool has been commited"""
        try:
            erschema = self.session.vreg.schema.schema_by_eid(self.eid)
        except KeyError:
            # duh, schema not found, log error and skip operation
            self.warning('no schema for %s', self.eid)
            return
        if isinstance(erschema, RelationSchema): # XXX 3.6 migration
            return
        if isinstance(erschema, RelationDefinitionSchema) and \
               self.action in ('delete', 'add'): # XXX 3.6.1 migration
            return
        perms = list(erschema.action_permissions(self.action))
        if hasattr(self, 'group_eid'):
            perm = self.session.entity_from_eid(self.group_eid).name
        else:
            perm = erschema.rql_expression(self.expr)
        try:
            perms.remove(perm)
            erschema.set_action_permissions(self.action, perms)
        except ValueError:
            self.error('can\'t remove permission %s for %s on %s',
                       perm, self.action, erschema)


class MemSchemaSpecializesAdd(MemSchemaOperation):

    def commit_event(self):
        eschema = self.session.vreg.schema.schema_by_eid(self.etypeeid)
        parenteschema = self.session.vreg.schema.schema_by_eid(self.parentetypeeid)
        eschema._specialized_type = parenteschema.type
        parenteschema._specialized_by.append(eschema.type)


class MemSchemaSpecializesDel(MemSchemaOperation):

    def commit_event(self):
        try:
            eschema = self.session.vreg.schema.schema_by_eid(self.etypeeid)
            parenteschema = self.session.vreg.schema.schema_by_eid(self.parentetypeeid)
        except KeyError:
            # etype removed, nothing to do
            return
        eschema._specialized_type = None
        parenteschema._specialized_by.remove(eschema.type)


class SyncSchemaHook(hook.Hook):
    __abstract__ = True
    category = 'syncschema'


# CWEType hooks ################################################################

class DelCWETypeHook(SyncSchemaHook):
    """before deleting a CWEType entity:
    * check that we don't remove a core entity type
    * cascade to delete related CWAttribute and CWRelation entities
    * instantiate an operation to delete the entity type on commit
    """
    __regid__ = 'syncdelcwetype'
    __select__ = SyncSchemaHook.__select__ & implements('CWEType')
    events = ('before_delete_entity',)

    def __call__(self):
        # final entities can't be deleted, don't care about that
        name = self.entity.name
        if name in CORE_ETYPES:
            raise ValidationError(self.entity.eid, {None: self._cw._('can\'t be deleted')})
        # delete every entities of this type
        self._cw.unsafe_execute('DELETE %s X' % name)
        DropTable(self._cw, table=SQL_PREFIX + name)
        MemSchemaCWETypeDel(self._cw, name)


class AfterDelCWETypeHook(DelCWETypeHook):
    __regid__ = 'wfcleanup'
    events = ('after_delete_entity',)

    def __call__(self):
        # workflow cleanup
        self._cw.execute('DELETE Workflow X WHERE NOT X workflow_of Y')


class AfterAddCWETypeHook(DelCWETypeHook):
    """after adding a CWEType entity:
    * create the necessary table
    * set creation_date and modification_date by creating the necessary
      CWAttribute entities
    * add owned_by relation by creating the necessary CWRelation entity
    * register an operation to add the entity type to the instance's
      schema on commit
    """
    __regid__ = 'syncaddcwetype'
    events = ('after_add_entity',)

    def __call__(self):
        entity = self.entity
        if entity.get('final'):
            return
        schema = self._cw.vreg.schema
        name = entity['name']
        etype = EntityType(name=name, description=entity.get('description'),
                           meta=entity.get('meta')) # don't care about final
        # fake we add it to the schema now to get a correctly initialized schema
        # but remove it before doing anything more dangerous...
        schema = self._cw.vreg.schema
        eschema = schema.add_entity_type(etype)
        # generate table sql and rql to add metadata
        tablesql = eschema2sql(self._cw.pool.source('system').dbhelper, eschema,
                               prefix=SQL_PREFIX)
        relrqls = []
        for rtype in (META_RTYPES - VIRTUAL_RTYPES):
            rschema = schema[rtype]
            sampletype = rschema.subjects()[0]
            desttype = rschema.objects()[0]
            props = rschema.rdef(sampletype, desttype)
            relrqls += list(ss.rdef2rql(rschema, name, desttype, props,
                                        groupmap=group_mapping(self._cw)))
        # now remove it !
        schema.del_entity_type(name)
        # create the necessary table
        for sql in tablesql.split(';'):
            if sql.strip():
                self._cw.system_sql(sql)
        # register operation to modify the schema on commit
        # this have to be done before adding other relations definitions
        # or permission settings
        etype.eid = entity.eid
        MemSchemaCWETypeAdd(self._cw, etype)
        # add meta relations
        for rql, kwargs in relrqls:
            self._cw.execute(rql, kwargs)


class BeforeUpdateCWETypeHook(DelCWETypeHook):
    """check name change, handle final"""
    __regid__ = 'syncupdatecwetype'
    events = ('before_update_entity',)

    def __call__(self):
        entity = self.entity
        check_valid_changes(self._cw, entity, ro_attrs=('final',))
        # don't use getattr(entity, attr), we would get the modified value if any
        if 'name' in entity.edited_attributes:
            newname = entity.pop('name')
            oldname = entity.name
            if newname.lower() != oldname.lower():
                SourceDbCWETypeRename(self._cw, oldname=oldname, newname=newname)
                MemSchemaCWETypeRename(self._cw, oldname=oldname, newname=newname)
            entity['name'] = newname


# CWRType hooks ################################################################

class DelCWRTypeHook(SyncSchemaHook):
    """before deleting a CWRType entity:
    * check that we don't remove a core relation type
    * cascade to delete related CWAttribute and CWRelation entities
    * instantiate an operation to delete the relation type on commit
    """
    __regid__ = 'syncdelcwrtype'
    __select__ = SyncSchemaHook.__select__ & implements('CWRType')
    events = ('before_delete_entity',)

    def __call__(self):
        name = self.entity.name
        if name in CORE_RTYPES:
            raise ValidationError(self.entity.eid, {None: self._cw._('can\'t be deleted')})
        # delete relation definitions using this relation type
        self._cw.execute('DELETE CWAttribute X WHERE X relation_type Y, Y eid %(x)s',
                        {'x': self.entity.eid})
        self._cw.execute('DELETE CWRelation X WHERE X relation_type Y, Y eid %(x)s',
                        {'x': self.entity.eid})
        MemSchemaCWRTypeDel(self._cw, name)


class AfterAddCWRTypeHook(DelCWRTypeHook):
    """after a CWRType entity has been added:
    * register an operation to add the relation type to the instance's
      schema on commit

    We don't know yet this point if a table is necessary
    """
    __regid__ = 'syncaddcwrtype'
    events = ('after_add_entity',)

    def __call__(self):
        entity = self.entity
        rtype = RelationType(name=entity.name,
                             description=entity.get('description'),
                             meta=entity.get('meta', False),
                             inlined=entity.get('inlined', False),
                             symmetric=entity.get('symmetric', False),
                             eid=entity.eid)
        MemSchemaCWRTypeAdd(self._cw, rtype)


class BeforeUpdateCWRTypeHook(DelCWRTypeHook):
    """check name change, handle final"""
    __regid__ = 'syncupdatecwrtype'
    events = ('before_update_entity',)

    def __call__(self):
        entity = self.entity
        check_valid_changes(self._cw, entity)
        newvalues = {}
        for prop in ('symmetric', 'inlined', 'fulltext_container'):
            if prop in entity.edited_attributes:
                old, new = hook.entity_oldnewvalue(entity, prop)
                if old != new:
                    newvalues[prop] = entity[prop]
        if newvalues:
            rschema = self._cw.vreg.schema.rschema(entity.name)
            SourceDbCWRTypeUpdate(self._cw, rschema=rschema, entity=entity,
                                  values=newvalues)
            MemSchemaCWRTypeUpdate(self._cw, rschema=rschema, values=newvalues)


class AfterDelRelationTypeHook(SyncSchemaHook):
    """before deleting a CWAttribute or CWRelation entity:
    * if this is a final or inlined relation definition, instantiate an
      operation to drop necessary column, else if this is the last instance
      of a non final relation, instantiate an operation to drop necessary
      table
    * instantiate an operation to delete the relation definition on commit
    * delete the associated relation type when necessary
    """
    __regid__ = 'syncdelrelationtype'
    __select__ = SyncSchemaHook.__select__ & hook.match_rtype('relation_type')
    events = ('after_delete_relation',)

    def __call__(self):
        session = self._cw
        rdef = session.vreg.schema.schema_by_eid(self.eidfrom)
        subjschema, rschema, objschema = rdef.as_triple()
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
                       'R eid %%(x)s' % rdeftype, {'x': self.eidto})
        lastrel = rset[0][0] == 0
        # we have to update physical schema systematically for final and inlined
        # relations, but only if it's the last instance for this relation type
        # for other relations

        if (rschema.final or rschema.inlined):
            rset = execute('Any COUNT(X) WHERE X is %s, X relation_type R, '
                           'R eid %%(x)s, X from_entity E, E name %%(name)s'
                           % rdeftype, {'x': self.eidto, 'name': str(subjschema)})
            if rset[0][0] == 0 and not subjschema.eid in pendings:
                ptypes = session.transaction_data.setdefault('pendingrtypes', set())
                ptypes.add(rschema.type)
                DropColumn(session, table=SQL_PREFIX + subjschema.type,
                           column=SQL_PREFIX + rschema.type)
        elif lastrel:
            DropRelationTable(session, rschema.type)
        # if this is the last instance, drop associated relation type
        if lastrel and not self.eidto in pendings:
            execute('DELETE CWRType X WHERE X eid %(x)s', {'x': self.eidto}, 'x')
        MemSchemaRDefDel(session, (subjschema, rschema, objschema))


# CWAttribute / CWRelation hooks ###############################################

class AfterAddCWAttributeHook(SyncSchemaHook):
    __regid__ = 'syncaddcwattribute'
    __select__ = SyncSchemaHook.__select__ & implements('CWAttribute')
    events = ('after_add_entity',)

    def __call__(self):
        SourceDbCWAttributeAdd(self._cw, entity=self.entity)


class AfterAddCWRelationHook(AfterAddCWAttributeHook):
    __regid__ = 'syncaddcwrelation'
    __select__ = SyncSchemaHook.__select__ & implements('CWRelation')

    def __call__(self):
        SourceDbCWRelationAdd(self._cw, entity=self.entity)


class AfterUpdateCWRDefHook(SyncSchemaHook):
    __regid__ = 'syncaddcwattribute'
    __select__ = SyncSchemaHook.__select__ & implements('CWAttribute',
                                                        'CWRelation')
    events = ('before_update_entity',)

    def __call__(self):
        entity = self.entity
        if self._cw.deleted_in_transaction(entity.eid):
            return
        desttype = entity.otype.name
        rschema = self._cw.vreg.schema[entity.rtype.name]
        newvalues = {}
        for prop in RelationDefinitionSchema.rproperty_defs(desttype):
            if prop == 'constraints':
                continue
            if prop == 'order':
                prop = 'ordernum'
            if prop in entity.edited_attributes:
                old, new = hook.entity_oldnewvalue(entity, prop)
                if old != new:
                    newvalues[prop] = entity[prop]
        if newvalues:
            subjtype = entity.stype.name
            MemSchemaRDefUpdate(self._cw, kobj=(subjtype, desttype),
                                rschema=rschema, values=newvalues)
            SourceDbRDefUpdate(self._cw, kobj=(subjtype, desttype),
                               rschema=rschema, values=newvalues)


# constraints synchronization hooks ############################################

class AfterAddCWConstraintHook(SyncSchemaHook):
    __regid__ = 'syncaddcwconstraint'
    __select__ = SyncSchemaHook.__select__ & implements('CWConstraint')
    events = ('after_add_entity', 'after_update_entity')

    def __call__(self):
        MemSchemaCWConstraintAdd(self._cw, entity=self.entity)
        SourceDbCWConstraintAdd(self._cw, entity=self.entity)


class AfterAddConstrainedByHook(SyncSchemaHook):
    __regid__ = 'syncdelconstrainedby'
    __select__ = SyncSchemaHook.__select__ & hook.match_rtype('constrained_by')
    events = ('after_add_relation',)

    def __call__(self):
        if self._cw.added_in_transaction(self.eidfrom):
            self._cw.transaction_data.setdefault(self.eidfrom, []).append(self.eidto)


class BeforeDeleteConstrainedByHook(AfterAddConstrainedByHook):
    __regid__ = 'syncdelconstrainedby'
    events = ('before_delete_relation',)

    def __call__(self):
        if self._cw.deleted_in_transaction(self.eidfrom):
            return
        schema = self._cw.vreg.schema
        entity = self._cw.entity_from_eid(self.eidto)
        rdef = schema.schema_by_eid(self.eidfrom)
        try:
            cstr = rdef.constraint_by_type(entity.type)
        except IndexError:
            self._cw.critical('constraint type no more accessible')
        else:
            SourceDbCWConstraintDel(self._cw, cstr=cstr,
                                    subjtype=rdef.subject, rtype=rdef.rtype)
            MemSchemaCWConstraintDel(self._cw, rdef=rdef, cstr=cstr)


# permissions synchronization hooks ############################################

class AfterAddPermissionHook(SyncSchemaHook):
    """added entity/relation *_permission, need to update schema"""
    __regid__ = 'syncaddperm'
    __select__ = SyncSchemaHook.__select__ & hook.match_rtype(
        'read_permission', 'add_permission', 'delete_permission',
        'update_permission')
    events = ('after_add_relation',)

    def __call__(self):
        action = self.rtype.split('_', 1)[0]
        if self._cw.describe(self.eidto)[0] == 'CWGroup':
            MemSchemaPermissionAdd(self._cw, action=action, eid=self.eidfrom,
                                   group_eid=self.eidto)
        else: # RQLExpression
            expr = self._cw.entity_from_eid(self.eidto).expression
            MemSchemaPermissionAdd(self._cw, action=action, eid=self.eidfrom,
                                   expr=expr)


class BeforeDelPermissionHook(AfterAddPermissionHook):
    """delete entity/relation *_permission, need to update schema

    skip the operation if the related type is being deleted
    """
    __regid__ = 'syncdelperm'
    events = ('before_delete_relation',)

    def __call__(self):
        if self._cw.deleted_in_transaction(self.eidfrom):
            return
        action = self.rtype.split('_', 1)[0]
        if self._cw.describe(self.eidto)[0] == 'CWGroup':
            MemSchemaPermissionDel(self._cw, action=action, eid=self.eidfrom,
                                   group_eid=self.eidto)
        else: # RQLExpression
            expr = self._cw.entity_from_eid(self.eidto).expression
            MemSchemaPermissionDel(self._cw, action=action, eid=self.eidfrom,
                                   expr=expr)



class UpdateFTIndexOp(hook.SingleLastOperation):
    """operation to update full text indexation of entity whose schema change

    We wait after the commit to as the schema in memory is only updated after the commit.
    """

    def postcommit_event(self):
        session = self.session
        source = session.repo.system_source
        to_reindex = session.transaction_data.get('fti_update_etypes', ())
        self.info('%i etypes need full text indexed reindexation',
                  len(to_reindex))
        schema = self.session.repo.vreg.schema
        for etype in to_reindex:
            rset = session.execute('Any X WHERE X is %s' % etype)
            self.info('Reindexing full text index for %i entity of type %s',
                      len(rset), etype)
            still_fti = list(schema[etype].indexable_attributes())
            for entity in rset.entities():
                source.fti_unindex_entity(session, entity.eid)
                for container in entity.fti_containers():
                    if still_fti or container is not entity:
                        source.fti_unindex_entity(session, entity.eid)
                        source.fti_index_entity(session, container)
        if len(to_reindex):
            # Transaction have already been committed
            session.pool.commit()




# specializes synchronization hooks ############################################


class AfterAddSpecializesHook(SyncSchemaHook):
    __regid__ = 'syncaddspecializes'
    __select__ = SyncSchemaHook.__select__ & hook.match_rtype('specializes')
    events = ('after_add_relation',)

    def __call__(self):
        MemSchemaSpecializesAdd(self._cw, etypeeid=self.eidfrom,
                                parentetypeeid=self.eidto)


class AfterDelSpecializesHook(SyncSchemaHook):
    __regid__ = 'syncdelspecializes'
    __select__ = SyncSchemaHook.__select__ & hook.match_rtype('specializes')
    events = ('after_delete_relation',)

    def __call__(self):
        MemSchemaSpecializesDel(self._cw, etypeeid=self.eidfrom,
                                parentetypeeid=self.eidto)
