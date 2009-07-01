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

from cubicweb import ValidationError, RepositoryError
from cubicweb.server import schemaserial as ss
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.server.pool import Operation, SingleLastOperation, PreCommitOperation
from cubicweb.server.hookhelper import (entity_attr, entity_name,
                                     check_internal_entity)

# core entity and relation types which can't be removed
CORE_ETYPES = list(BASE_TYPES) + ['CWEType', 'CWRType', 'CWUser', 'CWGroup',
                                  'CWConstraint', 'CWAttribute', 'CWRelation']
CORE_RTYPES = ['eid', 'creation_date', 'modification_date',
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
                               % (table, column)))
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


class SchemaOperation(Operation):
    """base class for schema operations"""
    def __init__(self, session, kobj=None, **kwargs):
        self.schema = session.repo.schema
        self.kobj = kobj
        # once Operation.__init__ has been called, event may be triggered, so
        # do this last !
        Operation.__init__(self, session, **kwargs)
        # every schema operation is triggering a schema update
        UpdateSchemaOp(session)

class EarlySchemaOperation(SchemaOperation):
    def insert_index(self):
        """schema operation which are inserted at the begining of the queue
        (typically to add/remove entity or relation types)
        """
        i = -1
        for i, op in enumerate(self.session.pending_operations):
            if not isinstance(op, EarlySchemaOperation):
                return i
        return i + 1

class UpdateSchemaOp(SingleLastOperation):
    """the update schema operation:

    special operation which should be called once and after all other schema
    operations. It will trigger internal structures rebuilding to consider
    schema changes
    """

    def __init__(self, session):
        self.repo = session.repo
        SingleLastOperation.__init__(self, session)

    def commit_event(self):
        self.repo.set_schema(self.repo.schema)


class DropTableOp(PreCommitOperation):
    """actually remove a database from the application's schema"""
    table = None # make pylint happy
    def precommit_event(self):
        dropped = self.session.transaction_data.setdefault('droppedtables',
                                                           set())
        if self.table in dropped:
            return # already processed
        dropped.add(self.table)
        self.session.system_sql('DROP TABLE %s' % self.table)
        self.info('dropped table %s', self.table)

class DropColumnOp(PreCommitOperation):
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
                               % (table, column))
            self.info('dropped column %s from table %s', column, table)
        except Exception, ex:
            # not supported by sqlite for instance
            self.error('error while altering table %s: %s', table, ex)


# deletion ####################################################################

class DeleteCWETypeOp(SchemaOperation):
    """actually remove the entity type from the application's schema"""
    def commit_event(self):
        try:
            # del_entity_type also removes entity's relations
            self.schema.del_entity_type(self.kobj)
        except KeyError:
            # s/o entity type have already been deleted
            pass

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
    DropTableOp(session, table=SQL_PREFIX + name)
    DeleteCWETypeOp(session, name)

def after_del_eetype(session, eid):
    # workflow cleanup
    session.execute('DELETE State X WHERE NOT X state_of Y')
    session.execute('DELETE Transition X WHERE NOT X transition_of Y')


class DeleteCWRTypeOp(SchemaOperation):
    """actually remove the relation type from the application's schema"""
    def commit_event(self):
        try:
            self.schema.del_relation_type(self.kobj)
        except KeyError:
            # s/o entity type have already been deleted
            pass

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
    DeleteCWRTypeOp(session, name)


class DelRelationDefOp(SchemaOperation):
    """actually remove the relation definition from the application's schema"""
    def commit_event(self):
        subjtype, rtype, objtype = self.kobj
        try:
            self.schema.del_relation_def(subjtype, rtype, objtype)
        except KeyError:
            # relation type may have been already deleted
            pass

def after_del_relation_type(session, rdefeid, rtype, rteid):
    """before deleting a CWAttribute or CWRelation entity:
    * if this is a final or inlined relation definition, instantiate an
      operation to drop necessary column, else if this is the last instance
      of a non final relation, instantiate an operation to drop necessary
      table
    * instantiate an operation to delete the relation definition on commit
    * delete the associated relation type when necessary
    """
    subjschema, rschema, objschema = session.repo.schema.schema_by_eid(rdefeid)
    pendings = session.transaction_data.get('pendingeids', ())
    # first delete existing relation if necessary
    if rschema.is_final():
        rdeftype = 'CWAttribute'
    else:
        rdeftype = 'CWRelation'
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

    if (rschema.is_final() or rschema.inlined):
        rset = execute('Any COUNT(X) WHERE X is %s, X relation_type R, '
                       'R eid %%(x)s, X from_entity E, E name %%(name)s'
                       % rdeftype, {'x': rteid, 'name': str(subjschema)})
        if rset[0][0] == 0 and not subjschema.eid in pendings:
            DropColumnOp(session, table=SQL_PREFIX + subjschema.type,
                         column=SQL_PREFIX + rschema.type)
    elif lastrel:
        DropTableOp(session, table='%s_relation' % rschema.type)
    # if this is the last instance, drop associated relation type
    if lastrel and not rteid in pendings:
        execute('DELETE CWRType X WHERE X eid %(x)s', {'x': rteid}, 'x')
    DelRelationDefOp(session, (subjschema, rschema, objschema))


# addition ####################################################################

class AddCWETypeOp(EarlySchemaOperation):
    """actually add the entity type to the application's schema"""
    eid = None # make pylint happy
    def commit_event(self):
        eschema = self.schema.add_entity_type(self.kobj)
        eschema.eid = self.eid

def before_add_eetype(session, entity):
    """before adding a CWEType entity:
    * check that we are not using an existing entity type,
    """
    name = entity['name']
    schema = session.repo.schema
    if name in schema and schema[name].eid is not None:
        raise RepositoryError('an entity type %s already exists' % name)

def after_add_eetype(session, entity):
    """after adding a CWEType entity:
    * create the necessary table
    * set creation_date and modification_date by creating the necessary
      CWAttribute entities
    * add owned_by relation by creating the necessary CWRelation entity
    * register an operation to add the entity type to the application's
      schema on commit
    """
    if entity.get('final'):
        return
    schema = session.repo.schema
    name = entity['name']
    etype = EntityType(name=name, description=entity.get('description'),
                       meta=entity.get('meta')) # don't care about final
    # fake we add it to the schema now to get a correctly initialized schema
    # but remove it before doing anything more dangerous...
    schema = session.repo.schema
    eschema = schema.add_entity_type(etype)
    eschema.set_default_groups()
    # generate table sql and rql to add metadata
    tablesql = eschema2sql(session.pool.source('system').dbhelper, eschema,
                           prefix=SQL_PREFIX)
    relrqls = []
    for rtype in ('is', 'is_instance_of', 'creation_date', 'modification_date',
                  'created_by', 'owned_by'):
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
    AddCWETypeOp(session, etype, eid=entity.eid)
    # add meta creation_date, modification_date and owned_by relations
    for rql, kwargs in relrqls:
        session.execute(rql, kwargs)


class AddCWRTypeOp(EarlySchemaOperation):
    """actually add the relation type to the application's schema"""
    eid = None # make pylint happy
    def commit_event(self):
        rschema = self.schema.add_relation_type(self.kobj)
        rschema.set_default_groups()
        rschema.eid = self.eid

def before_add_ertype(session, entity):
    """before adding a CWRType entity:
    * check that we are not using an existing relation type,
    * register an operation to add the relation type to the application's
      schema on commit

    We don't know yeat this point if a table is necessary
    """
    name = entity['name']
    if name in session.repo.schema.relations():
        raise RepositoryError('a relation type %s already exists' % name)

def after_add_ertype(session, entity):
    """after a CWRType entity has been added:
    * register an operation to add the relation type to the application's
      schema on commit
    We don't know yeat this point if a table is necessary
    """
    AddCWRTypeOp(session, RelationType(name=entity['name'],
                                      description=entity.get('description'),
                                      meta=entity.get('meta', False),
                                      inlined=entity.get('inlined', False),
                                      symetric=entity.get('symetric', False)),
                eid=entity.eid)


class AddErdefOp(EarlySchemaOperation):
    """actually add the attribute relation definition to the application's
    schema
    """
    def commit_event(self):
        self.schema.add_relation_def(self.kobj)

TYPE_CONVERTER = {
    'Boolean': bool,
    'Int': int,
    'Float': float,
    'Password': str,
    'String': unicode,
    'Date' : unicode,
    'Datetime' : unicode,
    'Time' : unicode,
    }


class AddCWAttributePreCommitOp(PreCommitOperation):
    """an attribute relation (CWAttribute) has been added:
    * add the necessary column
    * set default on this column if any and possible
    * register an operation to add the relation definition to the
      application's schema on commit

    constraints are handled by specific hooks
    """
    entity = None # make pylint happy
    def precommit_event(self):
        session = self.session
        entity = self.entity
        fromentity = entity.from_entity[0]
        relationtype = entity.relation_type[0]
        session.execute('SET X ordernum Y+1 WHERE X from_entity SE, SE eid %(se)s, X ordernum Y, X ordernum >= %(order)s, NOT X eid %(x)s',
                        {'x': entity.eid, 'se': fromentity.eid, 'order': entity.ordernum or 0})
        subj, rtype = str(fromentity.name), str(relationtype.name)
        obj = str(entity.to_entity[0].name)
        # at this point default is a string or None, but we need a correctly
        # typed value
        default = entity.defaultval
        if default is not None:
            default = TYPE_CONVERTER[obj](default)
        constraints = get_constraints(session, entity)
        rdef = RelationDefinition(subj, rtype, obj,
                                  cardinality=entity.cardinality,
                                  order=entity.ordernum,
                                  description=entity.description,
                                  default=default,
                                  indexed=entity.indexed,
                                  fulltextindexed=entity.fulltextindexed,
                                  internationalizable=entity.internationalizable,
                                  constraints=constraints,
                                  eid=entity.eid)
        sysource = session.pool.source('system')
        attrtype = type_from_constraints(sysource.dbhelper, rdef.object,
                                         constraints)
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
        table = SQL_PREFIX + subj
        column = SQL_PREFIX + rtype
        try:
            session.system_sql(str('ALTER TABLE %s ADD COLUMN %s %s'
                                   % (table, column, attrtype)))
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
        AddErdefOp(session, rdef)

def after_add_efrdef(session, entity):
    AddCWAttributePreCommitOp(session, entity=entity)


class AddCWRelationPreCommitOp(PreCommitOperation):
    """an actual relation has been added:
    * if this is an inlined relation, add the necessary column
      else if it's the first instance of this relation type, add the
      necessary table and set default permissions
    * register an operation to add the relation definition to the
      application's schema on commit

    constraints are handled by specific hooks
    """
    entity = None # make pylint happy
    def precommit_event(self):
        session = self.session
        entity = self.entity
        fromentity = entity.from_entity[0]
        relationtype = entity.relation_type[0]
        session.execute('SET X ordernum Y+1 WHERE X from_entity SE, SE eid %(se)s, X ordernum Y, X ordernum >= %(order)s, NOT X eid %(x)s',
                        {'x': entity.eid, 'se': fromentity.eid, 'order': entity.ordernum or 0})
        subj, rtype = str(fromentity.name), str(relationtype.name)
        obj = str(entity.to_entity[0].name)
        card = entity.get('cardinality')
        rdef = RelationDefinition(subj, rtype, obj,
                                  cardinality=card,
                                  order=entity.ordernum,
                                  composite=entity.composite,
                                  description=entity.description,
                                  constraints=get_constraints(session, entity),
                                  eid=entity.eid)
        schema = session.repo.schema
        rschema = schema.rschema(rtype)
        # this have to be done before permissions setting
        AddErdefOp(session, rdef)
        if rschema.inlined:
            # need to add a column if the relation is inlined and if this is the
            # first occurence of "Subject relation Something" whatever Something
            # and if it has not been added during other event of the same
            # transaction
            key = '%s.%s' % (subj, rtype)
            try:
                alreadythere = bool(rschema.objects(subj))
            except KeyError:
                alreadythere = False
            if not (alreadythere or
                    key in session.transaction_data.get('createdattrs', ())):
                add_inline_relation_column(session, subj, rtype)
        else:
            # need to create the relation if no relation definition in the
            # schema and if it has not been added during other event of the same
            # transaction
            if not (rschema.subjects() or
                    rtype in session.transaction_data.get('createdtables', ())):
                try:
                    rschema = schema[rtype]
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
                        self.session.system_sql(sql)
                session.transaction_data.setdefault('createdtables', []).append(
                    rtype)

def after_add_enfrdef(session, entity):
    AddCWRelationPreCommitOp(session, entity=entity)


# update ######################################################################

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
        eschema = session.repo.schema[oldname]
        UpdateEntityTypeName(session, eschema=eschema,
                             oldname=oldname, newname=newname)

def before_update_ertype(session, entity):
    """check name change, handle final"""
    check_valid_changes(session, entity)


class UpdateEntityTypeName(SchemaOperation):
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

    def commit_event(self):
        self.session.repo.schema.rename_entity_type(self.oldname, self.newname)


class UpdateRelationDefOp(SchemaOperation):
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
        if 'cardinality' in self.values and self.rschema.is_final():
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

    def commit_event(self):
        # structure should be clean, not need to remove entity's relations
        # at this point
        self.rschema._rproperties[self.kobj].update(self.values)


def after_update_erdef(session, entity):
    desttype = entity.to_entity[0].name
    rschema = session.repo.schema[entity.relation_type[0].name]
    newvalues = {}
    for prop in rschema.rproperty_defs(desttype):
        if prop == 'constraints':
            continue
        if prop == 'order':
            prop = 'ordernum'
        if prop in entity:
            newvalues[prop] = entity[prop]
    if newvalues:
        subjtype = entity.from_entity[0].name
        UpdateRelationDefOp(session, (subjtype, desttype),
                            rschema=rschema, values=newvalues)


class UpdateRtypeOp(SchemaOperation):
    """actually update some properties of a relation definition"""
    rschema = values = entity = None # make pylint happy

    def precommit_event(self):
        session = self.session
        rschema = self.rschema
        if rschema.is_final() or not 'inlined' in self.values:
            return # nothing to do
        inlined = self.values['inlined']
        entity = self.entity
        if not entity.inlined_changed(inlined): # check in-lining is necessary/possible
            return # nothing to do
        # inlined changed, make necessary physical changes!
        sqlexec = self.session.system_sql
        rtype = rschema.type
        eidcolumn = SQL_PREFIX + 'eid'
        if not inlined:
            # need to create the relation if it has not been already done by another
            # event of the same transaction
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
                DropColumnOp(session, table=SQL_PREFIX + str(etype),
                             column=SQL_PREFIX + rtype)
        else:
            for etype in rschema.subjects():
                try:
                    add_inline_relation_column(session, str(etype), rtype)
                except Exception, ex:
                    # the column probably already exists. this occurs when
                    # the entity's type has just been added or if the column
                    # has not been previously dropped
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
                DropTableOp(session, table='%s_relation' % rtype)

    def commit_event(self):
        # structure should be clean, not need to remove entity's relations
        # at this point
        self.rschema.__dict__.update(self.values)

def after_update_ertype(session, entity):
    rschema = session.repo.schema.rschema(entity.name)
    newvalues = {}
    for prop in ('meta', 'symetric', 'inlined'):
        if prop in entity:
            newvalues[prop] = entity[prop]
    if newvalues:
        UpdateRtypeOp(session, entity=entity, rschema=rschema, values=newvalues)

# constraints synchronization #################################################

from cubicweb.schema import CONSTRAINTS

class ConstraintOp(SchemaOperation):
    """actually update constraint of a relation definition"""
    entity = None # make pylint happy

    def prepare_constraints(self, rtype, subjtype, objtype):
        constraints = rtype.rproperty(subjtype, objtype, 'constraints')
        self.constraints = list(constraints)
        rtype.set_rproperty(subjtype, objtype, 'constraints', self.constraints)
        return self.constraints

    def precommit_event(self):
        rdef = self.entity.reverse_constrained_by[0]
        session = self.session
        # when the relation is added in the same transaction, the constraint object
        # is created by AddEN?FRDefPreCommitOp, there is nothing to do here
        if rdef.eid in session.transaction_data.get('neweids', ()):
            self.cancelled = True
            return
        self.cancelled = False
        schema = session.repo.schema
        subjtype, rtype, objtype = schema.schema_by_eid(rdef.eid)
        self.prepare_constraints(rtype, subjtype, objtype)
        cstrtype = self.entity.type
        self.cstr = rtype.constraint_by_type(subjtype, objtype, cstrtype)
        self._cstr = CONSTRAINTS[cstrtype].deserialize(self.entity.value)
        self._cstr.eid = self.entity.eid
        table = SQL_PREFIX + str(subjtype)
        column = SQL_PREFIX + str(rtype)
        # alter the physical schema on size constraint changes
        if self._cstr.type() == 'SizeConstraint' and (
            self.cstr is None or self.cstr.max != self._cstr.max):
            adbh = self.session.pool.source('system').dbhelper
            card = rtype.rproperty(subjtype, objtype, 'cardinality')
            coltype = type_from_constraints(adbh, objtype, [self._cstr],
                                            creating=False)
            sql = adbh.sql_change_col_type(table, column, coltype, card != '1')
            try:
                session.system_sql(sql)
                self.info('altered column %s of table %s: now VARCHAR(%s)',
                          column, table, self._cstr.max)
            except Exception, ex:
                # not supported by sqlite for instance
                self.error('error while altering table %s: %s', table, ex)
        elif cstrtype == 'UniqueConstraint':
            session.pool.source('system').create_index(
                self.session, table, column, unique=True)

    def commit_event(self):
        if self.cancelled:
            return
        # in-place modification
        if not self.cstr is None:
            self.constraints.remove(self.cstr)
        self.constraints.append(self._cstr)


def after_add_econstraint(session, entity):
    ConstraintOp(session, entity=entity)

def after_update_econstraint(session, entity):
    ConstraintOp(session, entity=entity)


class DelConstraintOp(ConstraintOp):
    """actually remove a constraint of a relation definition"""
    rtype = subjtype = objtype = None # make pylint happy

    def precommit_event(self):
        self.prepare_constraints(self.rtype, self.subjtype, self.objtype)
        cstrtype = self.cstr.type()
        table = SQL_PREFIX + str(self.subjtype)
        column = SQL_PREFIX + str(self.rtype)
        # alter the physical schema on size/unique constraint changes
        if cstrtype == 'SizeConstraint':
            try:
                self.session.system_sql('ALTER TABLE %s ALTER COLUMN %s TYPE TEXT'
                                        % (table, column))
                self.info('altered column %s of table %s: now TEXT',
                          column, table)
            except Exception, ex:
                # not supported by sqlite for instance
                self.error('error while altering table %s: %s', table, ex)
        elif cstrtype == 'UniqueConstraint':
            self.session.pool.source('system').drop_index(
                self.session, table, column, unique=True)

    def commit_event(self):
        self.constraints.remove(self.cstr)


def before_delete_constrained_by(session, fromeid, rtype, toeid):
    if not fromeid in session.transaction_data.get('pendingeids', ()):
        schema = session.repo.schema
        entity = session.eid_rset(toeid).get_entity(0, 0)
        subjtype, rtype, objtype = schema.schema_by_eid(fromeid)
        try:
            cstr = rtype.constraint_by_type(subjtype, objtype, entity.cstrtype[0].name)
            DelConstraintOp(session, subjtype=subjtype, rtype=rtype, objtype=objtype,
                            cstr=cstr)
        except IndexError:
            session.critical('constraint type no more accessible')


def after_add_constrained_by(session, fromeid, rtype, toeid):
    if fromeid in session.transaction_data.get('neweids', ()):
        session.transaction_data.setdefault(fromeid, []).append(toeid)


# schema permissions synchronization ##########################################

class PermissionOp(Operation):
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

class AddGroupPermissionOp(PermissionOp):
    """synchronize schema when a *_permission relation has been added on a group
    """
    def __init__(self, session, perm, etype_eid, group_eid):
        self.group = entity_name(session, group_eid)
        PermissionOp.__init__(self, session, perm, etype_eid)

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

class AddRQLExpressionPermissionOp(PermissionOp):
    """synchronize schema when a *_permission relation has been added on a rql
    expression
    """
    def __init__(self, session, perm, etype_eid, expression):
        self.expr = expression
        PermissionOp.__init__(self, session, perm, etype_eid)

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

def after_add_permission(session, subject, rtype, object):
    """added entity/relation *_permission, need to update schema"""
    perm = rtype.split('_', 1)[0]
    if session.describe(object)[0] == 'CWGroup':
        AddGroupPermissionOp(session, perm, subject, object)
    else: # RQLExpression
        expr = session.execute('Any EXPR WHERE X eid %(x)s, X expression EXPR',
                               {'x': object}, 'x')[0][0]
        AddRQLExpressionPermissionOp(session, perm, subject, expr)



class DelGroupPermissionOp(AddGroupPermissionOp):
    """synchronize schema when a *_permission relation has been deleted from a group"""

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


class DelRQLExpressionPermissionOp(AddRQLExpressionPermissionOp):
    """synchronize schema when a *_permission relation has been deleted from an rql expression"""

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


def before_del_permission(session, subject, rtype, object):
    """delete entity/relation *_permission, need to update schema

    skip the operation if the related type is being deleted
    """
    if subject in session.transaction_data.get('pendingeids', ()):
        return
    perm = rtype.split('_', 1)[0]
    if session.describe(object)[0] == 'CWGroup':
        DelGroupPermissionOp(session, perm, subject, object)
    else: # RQLExpression
        expr = session.execute('Any EXPR WHERE X eid %(x)s, X expression EXPR',
                               {'x': object}, 'x')[0][0]
        DelRQLExpressionPermissionOp(session, perm, subject, expr)


def rebuild_infered_relations(session, subject, rtype, object):
    # registering a schema operation will trigger a call to
    # repo.set_schema() on commit which will in turn rebuild
    # infered relation definitions
    UpdateSchemaOp(session)


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
    hm.register_hook(rebuild_infered_relations, 'after_add_relation', 'specializes')
    hm.register_hook(rebuild_infered_relations, 'after_delete_relation', 'specializes')
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
