# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""allways executed before all others in server migration

it should only include low level schema changes
"""
from __future__ import print_function

from six import text_type

from cubicweb import ConfigurationError
from cubicweb.server.session import hooks_control
from cubicweb.server import schemaserial as ss

applcubicwebversion, cubicwebversion = versions_map['cubicweb']

def _add_relation_definition_no_perms(subjtype, rtype, objtype):
    rschema = fsschema.rschema(rtype)
    rdef = rschema.rdefs[(subjtype, objtype)]
    rdef.rtype = schema.rschema(rtype)
    rdef.subject = schema.eschema(subjtype)
    rdef.object = schema.eschema(objtype)
    ss.execschemarql(rql, rdef, ss.rdef2rql(rdef, CSTRMAP, groupmap=None))
    commit(ask_confirm=False)

def replace_eid_sequence_with_eid_numrange(session):
    dbh = session.repo.system_source.dbhelper
    cursor = session.cnxset.cu
    try:
        cursor.execute(dbh.sql_sequence_current_state('entities_id_seq'))
        lasteid = cursor.fetchone()[0]
    except: # programming error, already migrated
        session.rollback()
        return

    cursor.execute(dbh.sql_drop_sequence('entities_id_seq'))
    cursor.execute(dbh.sql_create_numrange('entities_id_seq'))
    cursor.execute(dbh.sql_restart_numrange('entities_id_seq', initial_value=lasteid))
    session.commit()

if applcubicwebversion <= (3, 13, 0) and cubicwebversion >= (3, 13, 1):
    sql('ALTER TABLE entities ADD asource VARCHAR(64)')
    sql('UPDATE entities SET asource=cw_name  '
        'FROM cw_CWSource, cw_source_relation '
        'WHERE entities.eid=cw_source_relation.eid_from AND cw_source_relation.eid_to=cw_CWSource.cw_eid')
    commit()

if applcubicwebversion <= (3, 14, 4) and cubicwebversion >= (3, 14, 4):
    from cubicweb.server import schema2sql as y2sql
    dbhelper = repo.system_source.dbhelper
    rdefdef = schema['CWSource'].rdef('name')
    attrtype = y2sql.type_from_constraints(dbhelper, rdefdef.object, rdefdef.constraints).split()[0]
    cursor = session.cnxset.cu
    sql('UPDATE entities SET asource = source WHERE asource is NULL')
    dbhelper.change_col_type(cursor, 'entities', 'asource', attrtype, False)
    dbhelper.change_col_type(cursor, 'entities', 'source', attrtype, False)

    # we now have a functional asource column, start using the normal eid_type_source method
    if repo.system_source.eid_type_source == repo.system_source.eid_type_source_pre_131:
        del repo.system_source.eid_type_source

if applcubicwebversion < (3, 19, 0) and cubicwebversion >= (3, 19, 0):
    try: 
        # need explicit drop of the indexes on some database systems (sqlserver)
        sql(repo.system_source.dbhelper.sql_drop_index('entities', 'mtime'))
        sql('ALTER TABLE "entities" DROP COLUMN "mtime"')
        sql('ALTER TABLE "entities" DROP COLUMN "source"')
    except: # programming error, already migrated
        print("Failed to drop mtime or source database columns")
        print("'entities' table of the database has probably been already updated")

    commit()

    replace_eid_sequence_with_eid_numrange(session)


if applcubicwebversion < (3, 18, 0) and cubicwebversion >= (3, 18, 0):
    driver = config.system_source_config['db-driver']
    if not (driver == 'postgres' or driver.startswith('sqlserver')):
        import sys
        print('This migration is not supported for backends other than sqlserver or postgres (yet).', file=sys.stderr)
        sys.exit(1)

    add_relation_definition('CWAttribute', 'add_permission', 'CWGroup')
    add_relation_definition('CWAttribute', 'add_permission', 'RQLExpression')

    # a bad defaultval in 3.13.8 schema was fixed in 3.13.9, but the migration was missed
    rql('SET ATTR defaultval NULL WHERE ATTR from_entity E, E name "CWSource", ATTR relation_type T, T name "in_synchronization"')

    # the migration gets confused when we change rdefs out from under it.  So
    # explicitly remove this size constraint so it doesn't stick around and break
    # things later.
    rdefeid = schema['defaultval'].rdefs.values()[0].eid
    rql('DELETE CWConstraint C WHERE C cstrtype T, T name "SizeConstraint", R constrained_by C, R eid %(eid)s', {'eid': rdefeid})

    sync_schema_props_perms('defaultval')

    def convert_defaultval(cwattr, default):
        from decimal import Decimal
        import yams
        from cubicweb import Binary
        if default is None:
            return
        if isinstance(default, Binary):
            # partially migrated instance, try to be idempotent
            return default
        atype = cwattr.to_entity[0].name
        if atype == 'Boolean':
            # boolean attributes with default=False were stored as ''
            assert default in ('True', 'False', ''), repr(default)
            default = default == 'True'
        elif atype in ('Int', 'BigInt'):
            default = int(default)
        elif atype == 'Float':
            default = float(default)
        elif atype == 'Decimal':
            default = Decimal(default)
        elif atype in ('Date', 'Datetime', 'TZDatetime', 'Time'):
            try:
                # handle NOW and TODAY, keep them stored as strings
                yams.KEYWORD_MAP[atype][default.upper()]
                default = default.upper()
            except KeyError:
                # otherwise get an actual date or datetime
                default = yams.DATE_FACTORY_MAP[atype](default)
        else:
            assert atype == 'String', atype
            default = text_type(default)
        return Binary.zpickle(default)

    dbh = repo.system_source.dbhelper


    sql('ALTER TABLE cw_cwattribute ADD new_defaultval %s' % dbh.TYPE_MAPPING['Bytes'])

    for cwattr in rql('CWAttribute X').entities():
        olddefault = cwattr.defaultval
        if olddefault is not None:
            req = "UPDATE cw_cwattribute SET new_defaultval = %(val)s WHERE cw_eid = %(eid)s"
            args = {'val': dbh.binary_value(convert_defaultval(cwattr, olddefault).getvalue()), 'eid': cwattr.eid}
            sql(req, args, ask_confirm=False)

    sql('ALTER TABLE cw_cwattribute DROP COLUMN cw_defaultval')
    if driver == 'postgres':
        sql('ALTER TABLE cw_cwattribute RENAME COLUMN new_defaultval TO cw_defaultval')
    else: # sqlserver
        sql("sp_rename 'cw_cwattribute.new_defaultval', 'cw_defaultval', 'COLUMN'")


    # Set object type to "Bytes" for CWAttribute's "defaultval" attribute
    rql('SET X to_entity B WHERE X is CWAttribute, X from_entity Y, Y name "CWAttribute", '
        'X relation_type Z, Z name "defaultval", B name "Bytes", NOT X to_entity B')

    oldrdef = schema['CWAttribute'].rdef('defaultval')
    import yams.buildobjs as ybo
    newrdef = ybo.RelationDefinition('CWAttribute', 'defaultval', 'Bytes')
    newrdef.eid = oldrdef.eid
    schema.add_relation_def(newrdef)
    schema.del_relation_def('CWAttribute', 'defaultval', 'String')

    commit()

    sync_schema_props_perms('defaultval')

    for rschema in schema.relations():
        if rschema.symmetric:
            subjects = set(repr(e.type) for e in rschema.subjects())
            objects = set(repr(e.type) for e in rschema.objects())
            assert subjects == objects
            martians = set(str(eid) for eid, in sql('SELECT eid_to FROM %s_relation, entities WHERE eid_to = eid AND type NOT IN (%s)' %
                                               (rschema.type, ','.join(subjects))))
            martians |= set(str(eid) for eid, in sql('SELECT eid_from FROM %s_relation, entities WHERE eid_from = eid AND type NOT IN (%s)' %
                                                (rschema.type, ','.join(subjects))))
            if martians:
                martians = ','.join(martians)
                print('deleting broken relations %s for eids %s' % (rschema.type, martians))
                sql('DELETE FROM %s_relation WHERE eid_from IN (%s) OR eid_to IN (%s)' % (rschema.type, martians, martians))
            with session.deny_all_hooks_but():
                rql('SET X %(r)s Y WHERE Y %(r)s X, NOT X %(r)s Y' % {'r': rschema.type})
            commit()


    # multi columns unique constraints regeneration
    from cubicweb.server import schemaserial

    # syncschema hooks would try to remove indices but
    # 1) we already do that below
    # 2) the hook expects the CWUniqueTogetherConstraint.name attribute that hasn't
    #    yet been added
    with session.allow_all_hooks_but('syncschema'):
        rql('DELETE CWUniqueTogetherConstraint C')
    commit()
    add_attribute('CWUniqueTogetherConstraint', 'name')

    # low-level wipe code for postgres & sqlserver, plain sql ...
    if driver == 'postgres':
        for indexname, in sql('select indexname from pg_indexes'):
            if indexname.startswith('unique_'):
                print('dropping index', indexname)
                sql('DROP INDEX %s' % indexname)
        commit()
    elif driver.startswith('sqlserver'):
        for viewname, in sql('select name from sys.views'):
            if viewname.startswith('utv_'):
                print('dropping view (index should be cascade-deleted)', viewname)
                sql('DROP VIEW %s' % viewname)
        commit()

    # recreate the constraints, hook will lead to low-level recreation
    for eschema in sorted(schema.entities()):
        if eschema._unique_together:
            print('recreate unique indexes for', eschema)
            rql_args = schemaserial.uniquetogether2rqls(eschema)
            for rql, args in rql_args:
                args['x'] = eschema.eid
                session.execute(rql, args)
    commit()

    # all attributes perms have to be refreshed ...
    for rschema in sorted(schema.relations()):
        if rschema.final:
            if rschema.type in fsschema:
                print('sync perms for', rschema.type)
                sync_schema_props_perms(rschema.type, syncprops=False, ask_confirm=False, commit=False)
            else:
                print('WARNING: attribute %s missing from fs schema' % rschema.type)
    commit()

if applcubicwebversion < (3, 17, 0) and cubicwebversion >= (3, 17, 0):
    try:
        add_cube('sioc', update_database=False)
    except ConfigurationError:
        if not confirm('In cubicweb 3.17 sioc views have been moved to the sioc '
                       'cube, which is not installed.  Continue anyway?'):
            raise
    try:
        add_cube('embed', update_database=False)
    except ConfigurationError:
        if not confirm('In cubicweb 3.17 embedding views have been moved to the embed '
                       'cube, which is not installed.  Continue anyway?'):
            raise
    try:
        add_cube('geocoding', update_database=False)
    except ConfigurationError:
        if not confirm('In cubicweb 3.17 geocoding views have been moved to the geocoding '
                       'cube, which is not installed.  Continue anyway?'):
            raise


if applcubicwebversion <= (3, 14, 0) and cubicwebversion >= (3, 14, 0):
    if 'require_permission' in schema and not 'localperms'in repo.config.cubes():
        from cubicweb import ExecutionError
        try:
            add_cube('localperms', update_database=False)
        except ConfigurationError:
            raise ExecutionError('In cubicweb 3.14, CWPermission and related stuff '
                                 'has been moved to cube localperms. Install it first.')


if applcubicwebversion == (3, 6, 0) and cubicwebversion >= (3, 6, 0):
    CSTRMAP = dict(rql('Any T, X WHERE X is CWConstraintType, X name T',
                       ask_confirm=False))
    _add_relation_definition_no_perms('CWAttribute', 'update_permission', 'CWGroup')
    _add_relation_definition_no_perms('CWAttribute', 'update_permission', 'RQLExpression')
    rql('SET X update_permission Y WHERE X is CWAttribute, X add_permission Y')
    drop_relation_definition('CWAttribute', 'delete_permission', 'CWGroup')
    drop_relation_definition('CWAttribute', 'delete_permission', 'RQLExpression')

elif applcubicwebversion < (3, 6, 0) and cubicwebversion >= (3, 6, 0):
    CSTRMAP = dict(rql('Any T, X WHERE X is CWConstraintType, X name T',
                       ask_confirm=False))
    session.set_cnxset()
    permsdict = ss.deserialize_ertype_permissions(session)

    with hooks_control(session, session.HOOKS_ALLOW_ALL, 'integrity'):
        for rschema in repo.schema.relations():
            rpermsdict = permsdict.get(rschema.eid, {})
            for rdef in rschema.rdefs.values():
                for action in rdef.ACTIONS:
                    actperms = []
                    for something in rpermsdict.get(action == 'update' and 'add' or action, ()):
                        if isinstance(something, tuple):
                            actperms.append(rdef.rql_expression(*something))
                        else: # group name
                            actperms.append(something)
                    rdef.set_action_permissions(action, actperms)
        for action in ('read', 'add', 'delete'):
            _add_relation_definition_no_perms('CWRelation', '%s_permission' % action, 'CWGroup')
            _add_relation_definition_no_perms('CWRelation', '%s_permission' % action, 'RQLExpression')
        for action in ('read', 'update'):
            _add_relation_definition_no_perms('CWAttribute', '%s_permission' % action, 'CWGroup')
            _add_relation_definition_no_perms('CWAttribute', '%s_permission' % action, 'RQLExpression')
        for action in ('read', 'add', 'delete'):
            rql('SET X %s_permission Y WHERE X is CWRelation, '
                'RT %s_permission Y, X relation_type RT, Y is CWGroup' % (action, action))
            rql('INSERT RQLExpression Y: Y exprtype YET, Y mainvars YMV, Y expression YEX, '
                'X %s_permission Y WHERE X is CWRelation, '
                'X relation_type RT, RT %s_permission Y2, Y2 exprtype YET, '
                'Y2 mainvars YMV, Y2 expression YEX' % (action, action))
        rql('SET X read_permission Y WHERE X is CWAttribute, '
            'RT read_permission Y, X relation_type RT, Y is CWGroup')
        rql('INSERT RQLExpression Y: Y exprtype YET, Y mainvars YMV, Y expression YEX, '
            'X read_permission Y WHERE X is CWAttribute, '
            'X relation_type RT, RT read_permission Y2, Y2 exprtype YET, '
            'Y2 mainvars YMV, Y2 expression YEX')
        rql('SET X update_permission Y WHERE X is CWAttribute, '
            'RT add_permission Y, X relation_type RT, Y is CWGroup')
        rql('INSERT RQLExpression Y: Y exprtype YET, Y mainvars YMV, Y expression YEX, '
            'X update_permission Y WHERE X is CWAttribute, '
            'X relation_type RT, RT add_permission Y2, Y2 exprtype YET, '
            'Y2 mainvars YMV, Y2 expression YEX')
        for action in ('read', 'add', 'delete'):
            drop_relation_definition('CWRType', '%s_permission' % action, 'CWGroup', commit=False)
            drop_relation_definition('CWRType', '%s_permission' % action, 'RQLExpression')
    sync_schema_props_perms('read_permission', syncperms=False) # fix read_permission cardinality

if applcubicwebversion < (3, 9, 6) and cubicwebversion >= (3, 9, 6) and not 'CWUniqueTogetherConstraint' in schema:
    add_entity_type('CWUniqueTogetherConstraint')

if not ('CWUniqueTogetherConstraint', 'CWRType') in schema['relations'].rdefs:
    add_relation_definition('CWUniqueTogetherConstraint', 'relations', 'CWRType')
    rql('SET C relations RT WHERE C relations RDEF, RDEF relation_type RT')
    commit()
    drop_relation_definition('CWUniqueTogetherConstraint', 'relations', 'CWAttribute')
    drop_relation_definition('CWUniqueTogetherConstraint', 'relations', 'CWRelation')


if applcubicwebversion < (3, 4, 0) and cubicwebversion >= (3, 4, 0):

    with hooks_control(session, session.HOOKS_ALLOW_ALL, 'integrity'):
        session.set_shared_data('do-not-insert-cwuri', True)
        add_relation_type('cwuri')
        base_url = session.base_url()
        for eid, in rql('Any X', ask_confirm=False):
            type, source, extid = session.describe(eid)
            if source == 'system':
                rql('SET X cwuri %(u)s WHERE X eid %(x)s',
                    {'x': eid, 'u': u'%s%s' % (base_url, eid)})
        isession.commit()
        session.set_shared_data('do-not-insert-cwuri', False)

if applcubicwebversion < (3, 5, 0) and cubicwebversion >= (3, 5, 0):
    # check that migration is not doomed
    rset = rql('Any X,Y WHERE X transition_of E, Y transition_of E, '
               'X name N, Y name N, NOT X identity Y',
               ask_confirm=False)
    if rset:
        from logilab.common.shellutils import ASK
        if not ASK.confirm('Migration will fail because of transitions with the same name. '
                           'Continue anyway ?'):
            import sys
            sys.exit(1)
    # proceed with migration
    add_entity_type('Workflow')
    add_entity_type('BaseTransition')
    add_entity_type('WorkflowTransition')
    add_entity_type('SubWorkflowExitPoint')
    # drop explicit 'State allowed_transition Transition' since it should be
    # infered due to yams inheritance.  However we've to disable the schema
    # sync hook first to avoid to destroy existing data...
    try:
        from cubicweb.hooks import syncschema
        repo.vreg.unregister(syncschema.AfterDelRelationTypeHook)
        try:
            drop_relation_definition('State', 'allowed_transition', 'Transition')
        finally:
            repo.vreg.register(syncschema.AfterDelRelationTypeHook)
    except ImportError: # syncschema is in CW >= 3.6 only
        from cubicweb.server.schemahooks import after_del_relation_type
        repo.hm.unregister_hook(after_del_relation_type,
                                'after_delete_relation', 'relation_type')
        try:
            drop_relation_definition('State', 'allowed_transition', 'Transition')
        finally:
            repo.hm.register_hook(after_del_relation_type,
                                  'after_delete_relation', 'relation_type')
    schema.rebuild_infered_relations() # need to be explicitly called once everything is in place

    for et in rql('DISTINCT Any ET,ETN WHERE S state_of ET, ET name ETN',
                  ask_confirm=False).entities():
        wf = add_workflow(u'default %s workflow' % et.name, et.name,
                          ask_confirm=False)
        rql('SET S state_of WF WHERE S state_of ET, ET eid %(et)s, WF eid %(wf)s',
            {'et': et.eid, 'wf': wf.eid}, 'et', ask_confirm=False)
        rql('SET T transition_of WF WHERE T transition_of ET, ET eid %(et)s, WF eid %(wf)s',
            {'et': et.eid, 'wf': wf.eid}, 'et', ask_confirm=False)
        rql('SET WF initial_state S WHERE ET initial_state S, ET eid %(et)s, WF eid %(wf)s',
            {'et': et.eid, 'wf': wf.eid}, 'et', ask_confirm=False)


    rql('DELETE TrInfo TI WHERE NOT TI from_state S')
    rql('SET TI by_transition T WHERE TI from_state FS, TI to_state TS, '
        'FS allowed_transition T, T destination_state TS')
    commit()

    drop_relation_definition('State', 'state_of', 'CWEType')
    drop_relation_definition('Transition', 'transition_of', 'CWEType')
    drop_relation_definition('CWEType', 'initial_state', 'State')

    sync_schema_props_perms()

if applcubicwebversion < (3, 2, 2) and cubicwebversion >= (3, 2, 1):
    from base64 import b64encode
    for eid, extid in sql('SELECT eid, extid FROM entities '
                          'WHERE extid is NOT NULL',
                          ask_confirm=False):
        sql('UPDATE entities SET extid=%(extid)s WHERE eid=%(eid)s',
            {'extid': b64encode(extid), 'eid': eid}, ask_confirm=False)
    commit()

if applcubicwebversion < (3, 2, 0) and cubicwebversion >= (3, 2, 0):
    add_cube('card', update_database=False)

if applcubicwebversion < (3, 20, 0) and cubicwebversion >= (3, 20, 0):
    ss._IGNORED_PROPS.append('formula')
    add_attribute('CWAttribute', 'formula', commit=False)
    ss._IGNORED_PROPS.remove('formula')
    commit()
    add_entity_type('CWComputedRType')
    commit()

if schema['TZDatetime'].eid is None:
    add_entity_type('TZDatetime', auto=False)
if schema['TZTime'].eid is None:
    add_entity_type('TZTime', auto=False)


if applcubicwebversion < (3, 21, 1) and cubicwebversion >= (3, 21, 1):
    add_relation_definition('CWComputedRType', 'read_permission', 'CWGroup')
    add_relation_definition('CWComputedRType', 'read_permission', 'RQLExpression')


def sync_constraint_types():
    """Make sure the repository knows about all constraint types defined in the code"""
    from cubicweb.schema import CONSTRAINTS
    repo_constraints = set(row[0] for row in rql('Any N WHERE X is CWConstraintType, X name N'))

    for cstrtype in set(CONSTRAINTS) - repo_constraints:
        if cstrtype == 'BoundConstraint':
            # was renamed to BoundaryConstraint, we don't need the old name
            continue
        rql('INSERT CWConstraintType X: X name %(name)s', {'name': cstrtype})

    commit()

sync_constraint_types()
