# copyright 2003-2017 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""schema hooks:

- synchronize the living schema object with the persistent schema
- perform physical update on the source when necessary

checking for schema consistency is done in hooks.py
"""

import json
from copy import copy

from yams.schema import BASE_TYPES, BadSchemaDefinition, RelationDefinitionSchema
from yams.constraints import UniqueConstraint
from yams import buildobjs as ybo, convert_default_value

from logilab.common.decorators import clear_cache

from cubicweb import _
from cubicweb import validation_error
from cubicweb.predicates import is_instance
from cubicweb.schema import (SCHEMA_TYPES, META_RTYPES, VIRTUAL_RTYPES,
                             CONSTRAINTS, UNIQUE_CONSTRAINTS, ETYPE_NAME_MAP)
from cubicweb.server import hook, schemaserial as ss, schema2sql as y2sql
from cubicweb.server.sqlutils import SQL_PREFIX
from cubicweb.hooks.synccomputed import RecomputeAttributeOperation

# core entity and relation types which can't be removed
CORE_TYPES = BASE_TYPES | SCHEMA_TYPES | META_RTYPES | set(
    ('CWUser', 'CWGroup', 'login', 'upassword', 'name', 'in_group'))


def get_constraints(cnx, entity):
    constraints = []
    for cstreid in cnx.transaction_data.get(entity.eid, ()):
        cstrent = cnx.entity_from_eid(cstreid)
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


def add_inline_relation_column(cnx, etype, rtype):
    """add necessary column and index for an inlined relation"""
    attrkey = '%s.%s' % (etype, rtype)
    createdattrs = cnx.transaction_data.setdefault('createdattrs', set())
    if attrkey in createdattrs:
        return
    createdattrs.add(attrkey)
    table = SQL_PREFIX + etype
    column = SQL_PREFIX + rtype
    try:
        cnx.system_sql(str('ALTER TABLE %s ADD %s integer REFERENCES entities (eid)'
                           % (table, column)),
                       rollback_on_failure=False)
        cnx.info('added column %s to table %s', column, table)
    except Exception:
        # silent exception here, if this error has not been raised because the
        # column already exists, index creation will fail anyway
        cnx.exception('error while adding column %s to table %s',
                      table, column)
    # create index before alter table which may expectingly fail during test
    # (sqlite) while index creation should never fail (test for index existence
    # is done by the dbhelper)
    cnx.repo.system_source.create_index(cnx, table, column)
    cnx.info('added index on %s(%s)', table, column)


def insert_rdef_on_subclasses(cnx, eschema, rschema, rdefdef, props):
    # XXX 'infered': True/False, not clear actually
    props.update({'constraints': rdefdef.constraints,
                  'description': rdefdef.description,
                  'cardinality': rdefdef.cardinality,
                  'permissions': rdefdef.get_permissions(),
                  'order': rdefdef.order,
                  'infered': False, 'eid': None
                  })
    cstrtypemap = ss.cstrtype_mapping(cnx)
    groupmap = group_mapping(cnx)
    object = rschema.schema.eschema(rdefdef.object)
    for specialization in eschema.specialized_by(False):
        if (specialization, rdefdef.object) in rschema.rdefs:
            continue
        sperdef = RelationDefinitionSchema(specialization, rschema,
                                           object, None, values=props)
        ss.execschemarql(cnx.execute, sperdef,
                         ss.rdef2rql(sperdef, cstrtypemap, groupmap))


def check_valid_changes(cnx, entity, ro_attrs=('name', 'final')):
    errors = {}
    # don't use getattr(entity, attr), we would get the modified value if any
    for attr in entity.cw_edited:
        if attr in ro_attrs:
            origval, newval = entity.cw_edited.oldnewvalue(attr)
            if newval != origval:
                errors[attr] = _("can't change this attribute")
    if errors:
        raise validation_error(entity, errors)


class _MockEntity(object):  # XXX use a named tuple with python 2.6
    def __init__(self, eid):
        self.eid = eid


class SyncSchemaHook(hook.Hook):
    """abstract class for schema synchronization hooks (in the `syncschema`
    category)
    """
    __abstract__ = True
    category = 'syncschema'


# operations for low-level database alteration  ################################

class DropTable(hook.Operation):
    """actually remove a database from the instance's schema"""
    table = None  # make pylint happy

    def precommit_event(self):
        dropped = self.cnx.transaction_data.setdefault('droppedtables', set())
        if self.table in dropped:
            return  # already processed
        dropped.add(self.table)
        self.cnx.system_sql('DROP TABLE %s' % self.table)
        self.info('dropped table %s', self.table)

    # XXX revertprecommit_event


class DropRelationTable(DropTable):
    def __init__(self, cnx, rtype):
        super(DropRelationTable, self).__init__(
            cnx, table='%s_relation' % rtype)
        cnx.transaction_data.setdefault('pendingrtypes', set()).add(rtype)


class DropColumn(hook.DataOperationMixIn, hook.Operation):
    """actually remove the attribut's column from entity table in the system
    database
    """
    def precommit_event(self):
        cnx = self.cnx
        for etype, attr in self.get_data():
            table = SQL_PREFIX + etype
            column = SQL_PREFIX + attr
            source = cnx.repo.system_source
            # drop index if any
            source.drop_index(cnx, table, column)
            if source.dbhelper.alter_column_support:
                cnx.system_sql('ALTER TABLE %s DROP COLUMN %s' % (table, column),
                               rollback_on_failure=False)
                self.info('dropped column %s from table %s', column, table)
            else:
                # not supported by sqlite for instance
                self.error('dropping column not supported by the backend, handle '
                           'it yourself (%s.%s)', table, column)

    # XXX revertprecommit_event


# base operations for in-memory schema synchronization  ########################

class MemSchemaNotifyChanges(hook.SingleLastOperation):
    """the update schema operation:

    special operation which should be called once and after all other schema
    operations. It will trigger internal structures rebuilding to consider
    schema changes.
    """

    def __init__(self, cnx):
        hook.SingleLastOperation.__init__(self, cnx)

    def precommit_event(self):
        for eschema in self.cnx.repo.schema.entities():
            if not eschema.final:
                clear_cache(eschema, 'ordered_relations')
                # clear additional cached properties
                try:
                    # is_composite use composite_rdef_roles, hence one try except should be enough
                    del eschema.composite_rdef_roles
                    del eschema.is_composite
                except AttributeError:
                    pass

    def postcommit_event(self):
        repo = self.cnx.repo
        # commit event should not raise error, while set_schema has chances to
        # do so because it triggers full vreg reloading
        try:
            repo.schema.rebuild_infered_relations()
            # trigger vreg reload
            repo.set_schema(repo.schema)
        except Exception:
            self.critical('error while setting schema', exc_info=True)

    def rollback_event(self):
        self.precommit_event()


class MemSchemaOperation(hook.Operation):
    """base class for schema operations"""
    def __init__(self, cnx, **kwargs):
        hook.Operation.__init__(self, cnx, **kwargs)
        # every schema operation is triggering a schema update
        MemSchemaNotifyChanges(cnx)


# operations for high-level source database alteration  ########################

class CWETypeAddOp(MemSchemaOperation):
    """after adding a CWEType entity:
    * add it to the instance's schema
    * create the necessary table
    * set creation_date and modification_date by creating the necessary
      CWAttribute entities
    * add <meta rtype> relation by creating the necessary CWRelation entity
    """
    entity = None  # make pylint happy

    def precommit_event(self):
        cnx = self.cnx
        entity = self.entity
        schema = cnx.vreg.schema
        etype = ybo.EntityType(eid=entity.eid, name=entity.name,
                               description=entity.description)
        eschema = schema.add_entity_type(etype)
        # create the necessary table
        for sql in y2sql.eschema2sql(cnx.repo.system_source.dbhelper,
                                     eschema, prefix=SQL_PREFIX):
            cnx.system_sql(sql)
        # add meta relations
        gmap = group_mapping(cnx)
        cmap = ss.cstrtype_mapping(cnx)
        for rtype in (META_RTYPES - VIRTUAL_RTYPES):
            try:
                rschema = schema[rtype]
            except KeyError:
                self.critical('rtype %s was not handled at cwetype creation time', rtype)
                continue
            if not rschema.rdefs:
                self.warning('rtype %s has no relation definition yet', rtype)
                continue
            sampletype = rschema.subjects()[0]
            desttype = rschema.objects()[0]
            try:
                rdef = copy(rschema.rdef(sampletype, desttype))
            except KeyError:
                # this combo does not exist because this is not a universal META_RTYPE
                continue
            rdef.subject = _MockEntity(eid=entity.eid)
            mock = _MockEntity(eid=None)
            ss.execschemarql(cnx.execute, mock, ss.rdef2rql(rdef, cmap, gmap))

    def revertprecommit_event(self):
        # revert changes on in memory schema
        self.cnx.vreg.schema.del_entity_type(self.entity.name)
        # revert changes on database
        self.cnx.system_sql('DROP TABLE %s%s' % (SQL_PREFIX, self.entity.name))


class CWETypeRenameOp(MemSchemaOperation):
    """this operation updates physical storage accordingly"""

    oldname = newname = None  # make pylint happy

    def rename(self, oldname, newname):
        cnx = self.cnx
        source = cnx.repo.system_source
        dbhelper = source.dbhelper
        # we need sql to operate physical changes on the system database
        sqlexec = cnx.system_sql
        cnx.vreg.schema.rename_entity_type(oldname, newname)
        old_table = SQL_PREFIX + oldname
        new_table = SQL_PREFIX + newname
        eschema = cnx.vreg.schema.eschema(newname)
        # drop old indexes before the renaming
        for rschema in eschema.subject_relations():
            if rschema.inlined or (rschema.final and eschema.rdef(rschema.type).indexed):
                source.drop_index(cnx, old_table, SQL_PREFIX + rschema.type)
            if rschema.final and any(isinstance(cstr, UniqueConstraint)
                                     for cstr in eschema.rdef(rschema.type).constraints):
                source.drop_index(cnx, old_table, SQL_PREFIX + rschema.type, unique=True)
        sql = dbhelper.sql_rename_table(old_table, new_table)
        sqlexec(sql)
        self.info('renamed table %s to %s', oldname, newname)
        sqlexec('UPDATE entities SET type=%(newname)s WHERE type=%(oldname)s',
                {'newname': newname, 'oldname': oldname})
        for eid, etype in cnx.repo._type_cache.items():
            if etype == oldname:
                cnx.repo._type_cache[eid] = newname
        # recreate the indexes
        for rschema in eschema.subject_relations():
            if rschema.inlined or (rschema.final and eschema.rdef(rschema.type).indexed):
                source.create_index(cnx, new_table, SQL_PREFIX + rschema.type)
            if rschema.final and any(isinstance(cstr, UniqueConstraint)
                                     for cstr in eschema.rdef(rschema.type).constraints):
                source.create_index(cnx, new_table, SQL_PREFIX + rschema.type, unique=True)
        for attrs in eschema._unique_together or ():
            columns = ['%s%s' % (SQL_PREFIX, attr) for attr in attrs]
            old_index_name = y2sql.unique_index_name(oldname, columns)
            for sql in dbhelper.sqls_drop_multicol_unique_index(
                    new_table, columns, old_index_name):
                sqlexec(sql)
            new_index_name = y2sql.unique_index_name(newname, columns)
            for sql in dbhelper.sqls_create_multicol_unique_index(
                    new_table, columns, new_index_name):
                sqlexec(sql)
        # XXX transaction records

    def precommit_event(self):
        self.rename(self.oldname, self.newname)

    def revertprecommit_event(self):
        self.rename(self.newname, self.oldname)


class CWRTypeUpdateOp(MemSchemaOperation):
    """actually update some properties of a relation definition"""

    rschema = entity = values = None  # make pylint happy
    oldvalues = None

    def precommit_event(self):
        rschema = self.rschema
        if rschema.final:
            return  # watched changes to final relation type are unexpected
        cnx = self.cnx
        if 'fulltext_container' in self.values:
            op = UpdateFTIndexOp.get_instance(cnx)
            for subjtype, objtype in rschema.rdefs:
                if self.values['fulltext_container'] == 'subject':
                    op.add_data(subjtype)
                    op.add_data(objtype)
                else:
                    op.add_data(objtype)
                    op.add_data(subjtype)
        # update the in-memory schema first
        self.oldvalues = dict((attr, getattr(rschema, attr)) for attr in self.values)
        self.rschema.__dict__.update(self.values)
        # then make necessary changes to the system source database
        if 'inlined' not in self.values:
            return  # nothing to do
        inlined = self.values['inlined']
        # check in-lining is possible when inlined
        if inlined:
            self.entity.check_inlined_allowed()
        # inlined changed, make necessary physical changes!
        sqlexec = self.cnx.system_sql
        rtype = rschema.type
        eidcolumn = SQL_PREFIX + 'eid'
        if not inlined:
            # need to create the relation if it has not been already done by
            # another event of the same transaction
            if rschema.type not in cnx.transaction_data.get('createdtables', ()):
                # create the necessary table
                for sql in y2sql.rschema2sql(rschema):
                    sqlexec(sql)
                cnx.transaction_data.setdefault('createdtables', []).append(
                    rschema.type)
            # copy existant data
            column = SQL_PREFIX + rtype
            for etype in rschema.subjects():
                table = SQL_PREFIX + str(etype)
                sqlexec('INSERT INTO %s_relation SELECT %s, %s FROM %s WHERE NOT %s IS NULL'
                        % (rtype, eidcolumn, column, table, column))
            # drop existant columns
            for etype in rschema.subjects():
                DropColumn.get_instance(cnx).add_data((str(etype), rtype))
        else:
            for etype in rschema.subjects():
                try:
                    add_inline_relation_column(cnx, str(etype), rtype)
                except Exception as ex:
                    # the column probably already exists. this occurs when the
                    # entity's type has just been added or if the column has not
                    # been previously dropped (eg sqlite)
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
                DropRelationTable(cnx, rtype)

    def revertprecommit_event(self):
        # revert changes on in memory schema
        self.rschema.__dict__.update(self.oldvalues)
        # XXX revert changes on database


class CWComputedRTypeUpdateOp(MemSchemaOperation):
    """actually update some properties of a computed relation definition"""
    rschema = entity = rule = None  # make pylint happy
    old_rule = None

    def precommit_event(self):
        # update the in-memory schema first
        self.old_rule = self.rschema.rule
        self.rschema.rule = self.rule

    def revertprecommit_event(self):
        # revert changes on in memory schema
        self.rschema.rule = self.old_rule


class CWAttributeAddOp(MemSchemaOperation):
    """an attribute relation (CWAttribute) has been added:
    * add the necessary column
    * set default on this column if any and possible
    * register an operation to add the relation definition to the
      instance's schema on commit

    constraints are handled by specific hooks
    """
    entity = None  # make pylint happy

    def init_rdef(self, **kwargs):
        entity = self.entity
        fromentity = entity.stype
        rdefdef = self.rdefdef = ybo.RelationDefinition(
            str(fromentity.name), entity.rtype.name, str(entity.otype.name),
            description=entity.description, cardinality=entity.cardinality,
            constraints=get_constraints(self.cnx, entity),
            order=entity.ordernum, eid=entity.eid, **kwargs)
        try:
            self.cnx.vreg.schema.add_relation_def(rdefdef)
        except BadSchemaDefinition:
            # rdef has been infered then explicitly added (current consensus is
            # not clear at all versus infered relation handling (and much
            # probably buggy)
            rdef = self.cnx.vreg.schema.rschema(rdefdef.name).rdefs[rdefdef.subject, rdefdef.object]
            assert rdef.infered
        else:
            rdef = self.cnx.vreg.schema.rschema(rdefdef.name).rdefs[rdefdef.subject, rdefdef.object]

        self.cnx.execute('SET X ordernum Y+1 '
                         'WHERE X from_entity SE, SE eid %(se)s, X ordernum Y, '
                         'X ordernum >= %(order)s, NOT X eid %(x)s',
                         {'x': entity.eid, 'se': fromentity.eid,
                          'order': entity.ordernum or 0})
        return rdefdef, rdef

    def precommit_event(self):
        cnx = self.cnx
        entity = self.entity
        # entity.defaultval is a Binary or None, but we need a correctly typed
        # value
        default = entity.defaultval
        if default is not None:
            default = default.unzpickle()
        props = {'default': default,
                 'indexed': entity.indexed,
                 'fulltextindexed': entity.fulltextindexed,
                 'internationalizable': entity.internationalizable}
        if entity.extra_props:
            props.update(json.loads(entity.extra_props.getvalue().decode('ascii')))
        # entity.formula may not exist yet if we're migrating to 3.20
        if hasattr(entity, 'formula'):
            props['formula'] = entity.formula
        # update the in-memory schema first
        rdefdef, rdef = self.init_rdef(**props)
        # then make necessary changes to the system source database
        syssource = cnx.repo.system_source
        attrtype = y2sql.type_from_rdef(syssource.dbhelper, rdef)
        # added some str() wrapping query since some backend (eg psycopg) don't
        # allow unicode queries
        table = SQL_PREFIX + rdefdef.subject
        column = SQL_PREFIX + rdefdef.name
        try:
            cnx.system_sql(str('ALTER TABLE %s ADD %s %s'
                               % (table, column, attrtype)),
                           rollback_on_failure=False)
            self.info('added column %s to table %s', column, table)
        except Exception as ex:
            # the column probably already exists. this occurs when
            # the entity's type has just been added or if the column
            # has not been previously dropped
            self.error('error while altering table %s: %s', table, ex)
        if entity.indexed:
            try:
                syssource.create_index(cnx, table, column, unique=False)
            except Exception as ex:
                self.error('error while creating index for %s.%s: %s',
                           table, column, ex)
        # final relations are not infered, propagate
        schema = cnx.vreg.schema
        try:
            eschema = schema.eschema(rdefdef.subject)
        except KeyError:
            return  # entity type currently being added
        # propagate attribute to children classes
        rschema = schema.rschema(rdefdef.name)
        # if relation type has been inserted in the same transaction, its final
        # attribute is still set to False, so we've to ensure it's False
        rschema.final = True
        insert_rdef_on_subclasses(cnx, eschema, rschema, rdefdef, props)
        # update existing entities with the default value of newly added attribute
        if default is not None:
            default = convert_default_value(self.rdefdef, default)
            cnx.system_sql('UPDATE %s SET %s=%%(default)s' % (table, column),
                           {'default': default})
        # if attribute is computed, compute it
        if getattr(entity, 'formula', None):
            # add rtype attribute for RelationDefinitionSchema api compat, this
            # is what RecomputeAttributeOperation expect
            rdefdef.rtype = rdefdef.name
            RecomputeAttributeOperation.get_instance(cnx).add_data(rdefdef)

    def revertprecommit_event(self):
        # revert changes on in memory schema
        if getattr(self, 'rdefdef', None) is None:
            return
        self.cnx.vreg.schema.del_relation_def(
            self.rdefdef.subject, self.rdefdef.name, self.rdefdef.object)
        # XXX revert changes on database


class CWRelationAddOp(CWAttributeAddOp):
    """an actual relation has been added:

    * add the relation definition to the instance's schema

    * if this is an inlined relation, add the necessary column else if it's the
      first instance of this relation type, add the necessary table and set
      default permissions

    constraints are handled by specific hooks
    """
    entity = None  # make pylint happy

    def precommit_event(self):
        cnx = self.cnx
        entity = self.entity
        # update the in-memory schema first
        rdefdef, rdef = self.init_rdef(composite=entity.composite)
        # then make necessary changes to the system source database
        schema = cnx.vreg.schema
        rtype = rdefdef.name
        rschema = schema.rschema(rtype)
        # this have to be done before permissions setting
        if rschema.inlined:
            # need to add a column if the relation is inlined and if this is the
            # first occurence of "Subject relation Something" whatever Something
            if len(rschema.objects(rdefdef.subject)) == 1:
                add_inline_relation_column(cnx, rdefdef.subject, rtype)
            eschema = schema[rdefdef.subject]
            insert_rdef_on_subclasses(cnx, eschema, rschema, rdefdef,
                                      {'composite': entity.composite})
        else:
            if rschema.symmetric:
                # for symmetric relations, rdefs will store relation definitions
                # in both ways (i.e. (subj -> obj) and (obj -> subj))
                relation_already_defined = len(rschema.rdefs) > 2
            else:
                relation_already_defined = len(rschema.rdefs) > 1
            # need to create the relation if no relation definition in the
            # schema and if it has not been added during other event of the same
            # transaction
            if not (relation_already_defined or
                    rtype in cnx.transaction_data.get('createdtables', ())):
                rschema = schema.rschema(rtype)
                # create the necessary table
                for sql in y2sql.rschema2sql(rschema):
                    cnx.system_sql(sql)
                cnx.transaction_data.setdefault('createdtables', []).append(
                    rtype)

    # XXX revertprecommit_event


class RDefDelOp(MemSchemaOperation):
    """an actual relation has been removed"""
    rdef = None  # make pylint happy

    def precommit_event(self):
        cnx = self.cnx
        rdef = self.rdef
        rschema = rdef.rtype
        # make necessary changes to the system source database first
        rdeftype = rschema.final and 'CWAttribute' or 'CWRelation'
        execute = cnx.execute
        rset = execute('Any COUNT(X) WHERE X is %s, X relation_type R,'
                       'R eid %%(x)s' % rdeftype, {'x': rschema.eid})
        lastrel = rset[0][0] == 0
        # we have to update physical schema systematically for final and inlined
        # relations, but only if it's the last instance for this relation type
        # for other relations
        if (rschema.final or rschema.inlined):
            if not cnx.deleted_in_transaction(rdef.subject.eid):
                rset = execute('Any COUNT(X) WHERE X is %s, X relation_type R, '
                               'R eid %%(r)s, X from_entity E, E eid %%(e)s'
                               % rdeftype,
                               {'r': rschema.eid, 'e': rdef.subject.eid})
                if rset[0][0] == 0:
                    ptypes = cnx.transaction_data.setdefault('pendingrtypes', set())
                    ptypes.add(rschema.type)
                    DropColumn.get_instance(cnx).add_data((str(rdef.subject), str(rschema)))
                elif rschema.inlined:
                    cnx.system_sql('UPDATE %s%s SET %s%s=NULL WHERE '
                                   'EXISTS(SELECT 1 FROM entities '
                                   '       WHERE eid=%s%s AND type=%%(to_etype)s)'
                                   % (SQL_PREFIX, rdef.subject, SQL_PREFIX, rdef.rtype,
                                      SQL_PREFIX, rdef.rtype),
                                   {'to_etype': rdef.object.type})
        elif lastrel:
            DropRelationTable(cnx, str(rschema))
        else:
            cnx.system_sql('DELETE FROM %s_relation WHERE '
                           'EXISTS(SELECT 1 FROM entities '
                           '       WHERE eid=eid_from AND type=%%(from_etype)s)'
                           ' AND EXISTS(SELECT 1 FROM entities '
                           '       WHERE eid=eid_to AND type=%%(to_etype)s)'
                           % rschema,
                           {'from_etype': rdef.subject.type, 'to_etype': rdef.object.type})
        # then update the in-memory schema
        if rdef.subject not in ETYPE_NAME_MAP and rdef.object not in ETYPE_NAME_MAP:
            rschema.del_relation_def(rdef.subject, rdef.object)
        # if this is the last relation definition of this type, drop associated
        # relation type
        if lastrel and not cnx.deleted_in_transaction(rschema.eid):
            execute('DELETE CWRType X WHERE X eid %(x)s', {'x': rschema.eid})

    def revertprecommit_event(self):
        # revert changes on in memory schema
        #
        # Note: add_relation_def takes a RelationDefinition, not a
        # RelationDefinitionSchema, needs to fake it
        rdef = self.rdef
        rdef.name = str(rdef.rtype)
        if rdef.subject not in ETYPE_NAME_MAP and rdef.object not in ETYPE_NAME_MAP:
            self.cnx.vreg.schema.add_relation_def(rdef)


class RDefUpdateOp(MemSchemaOperation):
    """actually update some properties of a relation definition"""
    rschema = rdefkey = values = None  # make pylint happy
    rdef = oldvalues = None
    indexed_changed = null_allowed_changed = False

    def precommit_event(self):
        cnx = self.cnx
        rdef = self.rdef = self.rschema.rdefs[self.rdefkey]
        # update the in-memory schema first
        self.oldvalues = dict((attr, getattr(rdef, attr)) for attr in self.values)
        rdef.update(self.values)
        # then make necessary changes to the system source database
        syssource = cnx.repo.system_source
        if 'indexed' in self.values:
            syssource.update_rdef_indexed(cnx, rdef)
            self.indexed_changed = True
        if ('cardinality' in self.values and rdef.rtype.final
                and self.values['cardinality'][0] != self.oldvalues['cardinality'][0]):
            syssource.update_rdef_null_allowed(self.cnx, rdef)
            self.null_allowed_changed = True
        if 'fulltextindexed' in self.values:
            UpdateFTIndexOp.get_instance(cnx).add_data(rdef.subject)
        if 'formula' in self.values:
            RecomputeAttributeOperation.get_instance(cnx).add_data(rdef)

    def revertprecommit_event(self):
        if self.rdef is None:
            return
        # revert changes on in memory schema
        self.rdef.update(self.oldvalues)
        # revert changes on database
        syssource = self.cnx.repo.system_source
        if self.indexed_changed:
            syssource.update_rdef_indexed(self.cnx, self.rdef)
        if self.null_allowed_changed:
            syssource.update_rdef_null_allowed(self.cnx, self.rdef)


def _set_modifiable_constraints(rdef):
    # for proper in-place modification of in-memory schema: if rdef.constraints
    # is already a list, reuse it (we're updating multiple constraints of the
    # same rdef in the same transaction)
    if not isinstance(rdef.constraints, list):
        rdef.constraints = list(rdef.constraints)


class CWConstraintDelOp(MemSchemaOperation):
    """actually remove a constraint of a relation definition"""
    rdef = oldcstr = newcstr = None  # make pylint happy
    size_cstr_changed = unique_changed = False

    def precommit_event(self):
        cnx = self.cnx
        rdef = self.rdef
        # in-place modification of in-memory schema first
        _set_modifiable_constraints(rdef)
        if self.oldcstr in rdef.constraints:
            rdef.constraints.remove(self.oldcstr)
        else:
            self.critical('constraint %s for rdef %s was missing or already removed',
                          self.oldcstr, rdef)
        if cnx.deleted_in_transaction(rdef.eid):
            # don't try to alter a table that's going away (or is already gone)
            return
        # then update database: alter the physical schema on size/unique
        # constraint changes
        syssource = cnx.repo.system_source
        cstrtype = self.oldcstr.type()
        if cstrtype == 'SizeConstraint':
            # if the size constraint is being replaced with a new max size, we'll
            # call update_rdef_column in CWConstraintAddOp, skip it here
            for cstr in cnx.transaction_data.get('newsizecstr', ()):
                rdefentity = cstr.reverse_constrained_by[0]
                cstrrdef = cnx.vreg.schema.schema_by_eid(rdefentity.eid)
                if cstrrdef == rdef:
                    return

            # we found that the size constraint for this rdef is really gone,
            # not just replaced by another
            syssource.update_rdef_column(cnx, rdef)
            self.size_cstr_changed = True
        elif cstrtype == 'UniqueConstraint':
            syssource.update_rdef_unique(cnx, rdef)
            self.unique_changed = True
        elif cstrtype in ('BoundaryConstraint',
                          'IntervalBoundConstraint',
                          'StaticVocabularyConstraint'):
            cnx.system_sql('ALTER TABLE %s%s DROP CONSTRAINT %s'
                           % (SQL_PREFIX, rdef.subject, self.oldcstr.name_for(rdef)))

    def revertprecommit_event(self):
        # revert changes on in memory schema
        if self.newcstr is not None:
            self.rdef.constraints.remove(self.newcstr)
        if self.oldcstr is not None:
            self.rdef.constraints.append(self.oldcstr)
        # revert changes on database
        syssource = self.cnx.repo.system_source
        if self.size_cstr_changed:
            syssource.update_rdef_column(self.cnx, self.rdef)
        if self.unique_changed:
            syssource.update_rdef_unique(self.cnx, self.rdef)


class CWConstraintAddOp(hook.LateOperation, CWConstraintDelOp):
    """actually update constraint of a relation definition"""
    entity = None  # make pylint happy

    def precommit_event(self):
        cnx = self.cnx
        rdefentity = self.entity.reverse_constrained_by[0]
        rdef = self.rdef = cnx.vreg.schema.schema_by_eid(rdefentity.eid)
        cstrtype = self.entity.type
        if cstrtype in UNIQUE_CONSTRAINTS:
            oldcstr = self.oldcstr = rdef.constraint_by_type(cstrtype)
        else:
            oldcstr = None
        newcstr = self.newcstr = CONSTRAINTS[cstrtype].deserialize(self.entity.value)
        # in-place modification of in-memory schema first
        _set_modifiable_constraints(rdef)
        newcstr.eid = self.entity.eid
        if oldcstr is not None:
            rdef.constraints.remove(oldcstr)
        rdef.constraints.append(newcstr)
        # then update database: alter the physical schema on size/unique
        # constraint changes
        syssource = cnx.repo.system_source
        if cstrtype == 'SizeConstraint' and (oldcstr is None or
                                             oldcstr.max != newcstr.max):
            syssource.update_rdef_column(cnx, rdef)
            self.size_cstr_changed = True
        elif cstrtype == 'UniqueConstraint' and oldcstr is None:
            syssource.update_rdef_unique(cnx, rdef)
            self.unique_changed = True
        if cstrtype in ('BoundaryConstraint',
                        'IntervalBoundConstraint',
                        'StaticVocabularyConstraint'):
            cstrname, check = y2sql.check_constraint(rdef, newcstr, syssource.dbhelper,
                                                     prefix=SQL_PREFIX)
            # oldcstr is the new constraint when the attribute is being added in the same
            # transaction or when constraint value is updated. So we've to take care...
            if oldcstr is not None:
                oldcstrname = self.oldcstr.name_for(rdef)
                if oldcstrname != cstrname:
                    cnx.system_sql('ALTER TABLE %s%s DROP CONSTRAINT %s'
                                   % (SQL_PREFIX, rdef.subject, oldcstrname))
            cnx.system_sql('ALTER TABLE %s%s ADD CONSTRAINT %s CHECK(%s)' %
                           (SQL_PREFIX, rdef.subject, cstrname, check))


class CWUniqueTogetherConstraintAddOp(MemSchemaOperation):
    entity = None  # make pylint happy

    def precommit_event(self):
        cnx = self.cnx
        prefix = SQL_PREFIX
        entity = self.entity
        table = '%s%s' % (prefix, entity.constraint_of[0].name)
        cols = ['%s%s' % (prefix, r.name) for r in entity.relations]
        dbhelper = cnx.repo.system_source.dbhelper
        sqls = dbhelper.sqls_create_multicol_unique_index(table, cols, entity.name)
        for sql in sqls:
            cnx.system_sql(sql)

    def postcommit_event(self):
        entity = self.entity
        eschema = self.cnx.vreg.schema.schema_by_eid(entity.constraint_of[0].eid)
        attrs = [r.name for r in entity.relations]
        eschema._unique_together.append(attrs)


class CWUniqueTogetherConstraintDelOp(MemSchemaOperation):
    entity = cstrname = None  # make pylint happy
    cols = ()  # make pylint happy

    def insert_index(self):
        # We need to run before CWConstraintDelOp: if a size constraint is
        # removed and the column is part of a unique_together constraint, we
        # remove the unique_together index before changing the column's type.
        # SQL Server does not support unique indices on unlimited text columns.
        return 0

    def precommit_event(self):
        cnx = self.cnx
        prefix = SQL_PREFIX
        table = '%s%s' % (prefix, self.entity.type)
        dbhelper = cnx.repo.system_source.dbhelper
        cols = ['%s%s' % (prefix, c) for c in self.cols]
        sqls = dbhelper.sqls_drop_multicol_unique_index(table, cols, self.cstrname)
        for sql in sqls:
            cnx.system_sql(sql)

    def postcommit_event(self):
        eschema = self.cnx.vreg.schema.schema_by_eid(self.entity.eid)
        cols = set(self.cols)
        unique_together = [ut for ut in eschema._unique_together
                           if set(ut) != cols]
        eschema._unique_together = unique_together


# operations for in-memory schema synchronization  #############################

class MemSchemaCWETypeDel(MemSchemaOperation):
    """actually remove the entity type from the instance's schema"""
    etype = None  # make pylint happy

    def postcommit_event(self):
        # del_entity_type also removes entity's relations
        self.cnx.vreg.schema.del_entity_type(self.etype)


class MemSchemaCWRTypeAdd(MemSchemaOperation):
    """Revert addition of the relation type from the instance's schema if something goes wrong.
    """
    rtypedef = None  # make pylint happy

    def revertprecommit_event(self):
        self.cnx.vreg.schema.del_relation_type(self.rtypedef.name)


class MemSchemaCWRTypeDel(MemSchemaOperation):
    """actually remove the relation type from the instance's schema"""
    rtype = None  # make pylint happy

    def postcommit_event(self):
        try:
            self.cnx.vreg.schema.del_relation_type(self.rtype)
        except KeyError:
            # s/o entity type have already been deleted
            pass


class MemSchemaPermissionAdd(MemSchemaOperation):
    """synchronize schema when a *_permission relation has been added on a group
    """
    eid = action = group_eid = expr = None  # make pylint happy

    def precommit_event(self):
        """the observed connections.cnxset has been commited"""
        try:
            erschema = self.cnx.vreg.schema.schema_by_eid(self.eid)
        except KeyError:
            # duh, schema not found, log error and skip operation
            self.warning('no schema for %s', self.eid)
            return
        perms = list(erschema.action_permissions(self.action))
        if self.group_eid is not None:
            perm = self.cnx.entity_from_eid(self.group_eid).name
        else:
            perm = erschema.rql_expression(self.expr)
        try:
            perms.index(perm)
            self.warning('%s already in permissions for %s on %s',
                         perm, self.action, erschema)
        except ValueError:
            perms.append(perm)
            erschema.set_action_permissions(self.action, perms)

    # XXX revertprecommit_event


class MemSchemaPermissionDel(MemSchemaPermissionAdd):
    """synchronize schema when a *_permission relation has been deleted from a
    group
    """

    def precommit_event(self):
        """the observed connections set has been commited"""
        try:
            erschema = self.cnx.vreg.schema.schema_by_eid(self.eid)
        except KeyError:
            # duh, schema not found, log error and skip operation
            self.warning('no schema for %s', self.eid)
            return
        perms = list(erschema.action_permissions(self.action))
        if self.group_eid is not None:
            perm = self.cnx.entity_from_eid(self.group_eid).name
        else:
            perm = erschema.rql_expression(self.expr)
        try:
            perms.remove(perm)
            erschema.set_action_permissions(self.action, perms)
        except ValueError:
            self.error('can\'t remove permission %s for %s on %s',
                       perm, self.action, erschema)

    # XXX revertprecommit_event


class MemSchemaSpecializesAdd(MemSchemaOperation):
    etypeeid = parentetypeeid = None  # make pylint happy

    def precommit_event(self):
        eschema = self.cnx.vreg.schema.schema_by_eid(self.etypeeid)
        parenteschema = self.cnx.vreg.schema.schema_by_eid(self.parentetypeeid)
        eschema._specialized_type = parenteschema.type
        parenteschema._specialized_by.append(eschema.type)

    # XXX revertprecommit_event


class MemSchemaSpecializesDel(MemSchemaOperation):
    etypeeid = parentetypeeid = None  # make pylint happy

    def precommit_event(self):
        try:
            eschema = self.cnx.vreg.schema.schema_by_eid(self.etypeeid)
            parenteschema = self.cnx.vreg.schema.schema_by_eid(self.parentetypeeid)
        except KeyError:
            # etype removed, nothing to do
            return
        eschema._specialized_type = None
        parenteschema._specialized_by.remove(eschema.type)

    # XXX revertprecommit_event


# CWEType hooks ################################################################

class DelCWETypeHook(SyncSchemaHook):
    """before deleting a CWEType entity:
    * check that we don't remove a core entity type
    * cascade to delete related CWAttribute and CWRelation entities
    * instantiate an operation to delete the entity type on commit
    """
    __regid__ = 'syncdelcwetype'
    __select__ = SyncSchemaHook.__select__ & is_instance('CWEType')
    events = ('before_delete_entity',)

    def __call__(self):
        # final entities can't be deleted, don't care about that
        name = self.entity.name
        if name in CORE_TYPES:
            raise validation_error(self.entity, {None: _("can't be deleted")})
        # delete every entities of this type
        if name not in ETYPE_NAME_MAP:
            MemSchemaCWETypeDel(self._cw, etype=name)
        if not self.entity.final:
            DropTable(self._cw, table=SQL_PREFIX + name)


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
        if entity.cw_edited.get('final'):
            # final entity types don't need a table in the database and are
            # systematically added by yams at schema initialization time so
            # there is no need to do further processing. Simply assign its eid.
            self._cw.vreg.schema[entity.name].eid = entity.eid
            return
        CWETypeAddOp(self._cw, entity=entity)


class BeforeUpdateCWETypeHook(DelCWETypeHook):
    """check name change, handle final"""
    __regid__ = 'syncupdatecwetype'
    events = ('before_update_entity',)

    def __call__(self):
        entity = self.entity
        check_valid_changes(self._cw, entity, ro_attrs=('final',))
        # don't use getattr(entity, attr), we would get the modified value if any
        if 'name' in entity.cw_edited:
            oldname, newname = entity.cw_edited.oldnewvalue('name')
            if newname.lower() != oldname.lower():
                CWETypeRenameOp(self._cw, oldname=oldname, newname=newname)


# CWRType hooks ################################################################

class DelCWRTypeHook(SyncSchemaHook):
    """before deleting a CWRType entity:
    * check that we don't remove a core relation type
    * cascade to delete related CWAttribute and CWRelation entities
    * instantiate an operation to delete the relation type on commit
    """
    __regid__ = 'syncdelcwrtype'
    __select__ = SyncSchemaHook.__select__ & is_instance('CWRType')
    events = ('before_delete_entity',)

    def __call__(self):
        name = self.entity.name
        if name in CORE_TYPES:
            raise validation_error(self.entity, {None: _("can't be deleted")})
        # delete relation definitions using this relation type
        self._cw.execute('DELETE CWAttribute X WHERE X relation_type Y, Y eid %(x)s',
                         {'x': self.entity.eid})
        self._cw.execute('DELETE CWRelation X WHERE X relation_type Y, Y eid %(x)s',
                         {'x': self.entity.eid})
        MemSchemaCWRTypeDel(self._cw, rtype=name)


class AfterAddCWRTypeHook(SyncSchemaHook):
    """After a CWRType entity has been added, register an operation to add the
    relation type to the instance's schema on commit.

    We don't know yet at this point if a table is necessary, it will depend on
    further addition of relation definitions.
    """
    __regid__ = 'syncaddcwrtype'
    __select__ = SyncSchemaHook.__select__ & is_instance('CWRType')
    events = ('after_add_entity',)

    def __call__(self):
        rtypedef = self.rtype_def()
        # modify the instance's schema now since we'll usually need the type definition to do
        # further thing (e.g. add relation def of this type) but register and operation to revert
        # this if necessary
        self._cw.vreg.schema.add_relation_type(rtypedef)
        MemSchemaCWRTypeAdd(self._cw, rtypedef=rtypedef)

    def rtype_def(self):
        entity = self.entity
        return ybo.RelationType(name=entity.name,
                                description=entity.description,
                                inlined=entity.cw_edited.get('inlined', False),
                                symmetric=entity.cw_edited.get('symmetric', False),
                                eid=entity.eid)


class AfterAddCWComputedRTypeHook(AfterAddCWRTypeHook):
    """After a CWComputedRType entity has been added, register an operation to
    add the relation type to the instance's schema on commit.
    """
    __select__ = SyncSchemaHook.__select__ & is_instance('CWComputedRType')

    def rtype_def(self):
        entity = self.entity
        return ybo.ComputedRelation(name=entity.name,
                                    eid=entity.eid,
                                    rule=entity.rule)


class BeforeUpdateCWRTypeHook(SyncSchemaHook):
    """check name change, handle final"""
    __regid__ = 'syncupdatecwrtype'
    __select__ = SyncSchemaHook.__select__ & is_instance('CWRType')
    events = ('before_update_entity',)

    def __call__(self):
        entity = self.entity
        check_valid_changes(self._cw, entity)
        newvalues = {}
        for prop in ('symmetric', 'inlined', 'fulltext_container'):
            if prop in entity.cw_edited:
                old, new = entity.cw_edited.oldnewvalue(prop)
                if old != new:
                    newvalues[prop] = new
        if newvalues:
            rschema = self._cw.vreg.schema.rschema(entity.name)
            CWRTypeUpdateOp(self._cw, rschema=rschema, entity=entity,
                            values=newvalues)


class BeforeUpdateCWComputedRTypeHook(SyncSchemaHook):
    """check name change, handle final"""
    __regid__ = 'syncupdatecwcomputedrtype'
    __select__ = SyncSchemaHook.__select__ & is_instance('CWComputedRType')
    events = ('before_update_entity',)

    def __call__(self):
        entity = self.entity
        check_valid_changes(self._cw, entity)
        if 'rule' in entity.cw_edited:
            old, new = entity.cw_edited.oldnewvalue('rule')
            if old != new:
                rschema = self._cw.vreg.schema.rschema(entity.name)
                CWComputedRTypeUpdateOp(self._cw, rschema=rschema,
                                        entity=entity, rule=new)


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
        cnx = self._cw
        try:
            rdef = cnx.vreg.schema.schema_by_eid(self.eidfrom)
        except KeyError:
            self.critical('cant get schema rdef associated to %s', self.eidfrom)
            return
        subjschema, rschema, objschema = rdef.as_triple()
        pendingrdefs = cnx.transaction_data.setdefault('pendingrdefs', set())
        # first delete existing relation if necessary
        if rschema.final:
            pendingrdefs.add((subjschema, rschema))
        else:
            pendingrdefs.add((subjschema, rschema, objschema))
        RDefDelOp(cnx, rdef=rdef)


# CWComputedRType hooks #######################################################

class DelCWComputedRTypeHook(SyncSchemaHook):
    """before deleting a CWComputedRType entity:
    * check that we don't remove a core relation type
    * instantiate an operation to delete the relation type on commit
    """
    __regid__ = 'syncdelcwcomputedrtype'
    __select__ = SyncSchemaHook.__select__ & is_instance('CWComputedRType')
    events = ('before_delete_entity',)

    def __call__(self):
        name = self.entity.name
        if name in CORE_TYPES:
            raise validation_error(self.entity, {None: _("can't be deleted")})
        MemSchemaCWRTypeDel(self._cw, rtype=name)


# CWAttribute / CWRelation hooks ###############################################

class AfterAddCWAttributeHook(SyncSchemaHook):
    __regid__ = 'syncaddcwattribute'
    __select__ = SyncSchemaHook.__select__ & is_instance('CWAttribute')
    events = ('after_add_entity',)

    def __call__(self):
        CWAttributeAddOp(self._cw, entity=self.entity)


class AfterAddCWRelationHook(AfterAddCWAttributeHook):
    __regid__ = 'syncaddcwrelation'
    __select__ = SyncSchemaHook.__select__ & is_instance('CWRelation')

    def __call__(self):
        CWRelationAddOp(self._cw, entity=self.entity)


class AfterUpdateCWRDefHook(SyncSchemaHook):
    __regid__ = 'syncaddcwattribute'
    __select__ = SyncSchemaHook.__select__ & is_instance('CWAttribute',
                                                         'CWRelation')
    events = ('before_update_entity',)

    def __call__(self):
        entity = self.entity
        if self._cw.deleted_in_transaction(entity.eid):
            return
        subjtype = entity.stype.name
        objtype = entity.otype.name
        if subjtype in ETYPE_NAME_MAP or objtype in ETYPE_NAME_MAP:
            return
        rschema = self._cw.vreg.schema[entity.rtype.name]
        # note: do not access schema rdef here, it may be added later by an
        # operation
        newvalues = {}
        for prop in RelationDefinitionSchema.rproperty_defs(objtype):
            if prop == 'constraints':
                continue
            if prop == 'order':
                attr = 'ordernum'
            else:
                attr = prop
            if attr in entity.cw_edited:
                old, new = entity.cw_edited.oldnewvalue(attr)
                if old != new:
                    newvalues[prop] = new
        if newvalues:
            RDefUpdateOp(self._cw, rschema=rschema, rdefkey=(subjtype, objtype),
                         values=newvalues)


# constraints synchronization hooks ############################################

class AfterAddCWConstraintHook(SyncSchemaHook):
    __regid__ = 'syncaddcwconstraint'
    __select__ = SyncSchemaHook.__select__ & is_instance('CWConstraint')
    events = ('after_add_entity', 'after_update_entity')

    def __call__(self):
        if self.entity.cstrtype[0].name == 'SizeConstraint':
            txdata = self._cw.transaction_data
            if 'newsizecstr' not in txdata:
                txdata['newsizecstr'] = set()
            txdata['newsizecstr'].add(self.entity)
        CWConstraintAddOp(self._cw, entity=self.entity)


class AfterAddConstrainedByHook(SyncSchemaHook):
    __regid__ = 'syncaddconstrainedby'
    __select__ = SyncSchemaHook.__select__ & hook.match_rtype('constrained_by')
    events = ('after_add_relation',)

    def __call__(self):
        if self._cw.added_in_transaction(self.eidfrom):
            # used by get_constraints() which is called in CWAttributeAddOp
            self._cw.transaction_data.setdefault(self.eidfrom, []).append(self.eidto)


class BeforeDeleteCWConstraintHook(SyncSchemaHook):
    __regid__ = 'syncdelcwconstraint'
    __select__ = SyncSchemaHook.__select__ & is_instance('CWConstraint')
    events = ('before_delete_entity',)

    def __call__(self):
        entity = self.entity
        schema = self._cw.vreg.schema
        try:
            # KeyError, e.g. composite chain deletion
            rdef = schema.schema_by_eid(entity.reverse_constrained_by[0].eid)
            # IndexError
            cstr = rdef.constraint_by_eid(entity.eid)
        except (KeyError, IndexError):
            self._cw.critical('constraint type no more accessible')
        else:
            CWConstraintDelOp(self._cw, rdef=rdef, oldcstr=cstr)


# unique_together constraints
# XXX: use setoperations and before_add_relation here (on constraint_of and relations)
class AfterAddCWUniqueTogetherConstraintHook(SyncSchemaHook):
    __regid__ = 'syncadd_cwuniquetogether_constraint'
    __select__ = SyncSchemaHook.__select__ & is_instance('CWUniqueTogetherConstraint')
    events = ('after_add_entity',)

    def __call__(self):
        CWUniqueTogetherConstraintAddOp(self._cw, entity=self.entity)


class BeforeDeleteConstraintOfHook(SyncSchemaHook):
    __regid__ = 'syncdelconstraintof'
    __select__ = SyncSchemaHook.__select__ & hook.match_rtype('constraint_of')
    events = ('before_delete_relation',)

    def __call__(self):
        if self._cw.deleted_in_transaction(self.eidto):
            return
        schema = self._cw.vreg.schema
        cstr = self._cw.entity_from_eid(self.eidfrom)
        entity = schema.schema_by_eid(self.eidto)
        cols = tuple(r.name for r in cstr.relations)
        CWUniqueTogetherConstraintDelOp(self._cw, entity=entity,
                                        cstrname=cstr.name, cols=cols)


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
        if self._cw.entity_type(self.eidto) == 'CWGroup':
            MemSchemaPermissionAdd(self._cw, action=action, eid=self.eidfrom,
                                   group_eid=self.eidto)
        else:  # RQLExpression
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
        if self._cw.entity_type(self.eidto) == 'CWGroup':
            MemSchemaPermissionDel(self._cw, action=action, eid=self.eidfrom,
                                   group_eid=self.eidto)
        else:  # RQLExpression
            expr = self._cw.entity_from_eid(self.eidto).expression
            MemSchemaPermissionDel(self._cw, action=action, eid=self.eidfrom,
                                   expr=expr)


class UpdateFTIndexOp(hook.DataOperationMixIn, hook.SingleLastOperation):
    """operation to update full text indexation of entity whose schema change

    We wait after the commit to as the schema in memory is only updated after
    the commit.
    """
    containercls = list

    def postcommit_event(self):
        cnx = self.cnx
        source = cnx.repo.system_source
        schema = cnx.repo.vreg.schema
        to_reindex = self.get_data()
        self.info('%i etypes need full text indexed reindexation',
                  len(to_reindex))
        for etype in to_reindex:
            rset = cnx.execute('Any X WHERE X is %s' % etype)
            self.info('Reindexing full text index for %i entity of type %s',
                      len(rset), etype)
            still_fti = list(schema[etype].indexable_attributes())
            for entity in rset.entities():
                source.fti_unindex_entities(cnx, [entity])
                for container in entity.cw_adapt_to('IFTIndexable').fti_containers():
                    if still_fti or container is not entity:
                        source.fti_unindex_entities(cnx, [container])
                        source.fti_index_entities(cnx, [container])
        if to_reindex:
            # Transaction has already been committed
            cnx.cnxset.commit()


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
