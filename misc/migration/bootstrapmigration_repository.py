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
        return

    cursor.execute(dbh.sql_drop_sequence('entities_id_seq'))
    cursor.execute(dbh.sql_create_numrange('entities_id_seq'))
    cursor.execute(dbh.sql_restart_numrange('entities_id_seq', initial_value=lasteid))
    session.commit()

if applcubicwebversion < (3, 19, 0) and cubicwebversion >= (3, 19, 0):
    try: 
        # need explicit drop of the indexes on some database systems (sqlserver)
        sql(repo.system_source.dbhelper.sql_drop_index('entities', 'mtime'))
        sql('ALTER TABLE "entities" DROP COLUMN "mtime"')
        sql('ALTER TABLE "entities" DROP COLUMN "source"')
    except: # programming error, already migrated
        print "Failed to drop mtime or source database columns"
        print "'entities' table of the database has probably been already updated"

    commit()

    replace_eid_sequence_with_eid_numrange(session)

if applcubicwebversion < (3, 20, 0) and cubicwebversion >= (3, 20, 0):
    ss._IGNORED_PROPS.append('formula')
    add_attribute('CWAttribute', 'formula', commit=False)
    ss._IGNORED_PROPS.remove('formula')
    commit()
    add_entity_type('CWComputedRType')
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

if applcubicwebversion <= (3, 13, 0) and cubicwebversion >= (3, 13, 1):
    sql('ALTER TABLE entities ADD asource VARCHAR(64)')
    sql('UPDATE entities SET asource=cw_name  '
        'FROM cw_CWSource, cw_source_relation '
        'WHERE entities.eid=cw_source_relation.eid_from AND cw_source_relation.eid_to=cw_CWSource.cw_eid')
    commit()

if schema['TZDatetime'].eid is None:
    add_entity_type('TZDatetime', auto=False)
if schema['TZTime'].eid is None:
    add_entity_type('TZTime', auto=False)


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
    drop_relation_definition('CWAttribute', 'add_permission', 'CWGroup')
    drop_relation_definition('CWAttribute', 'add_permission', 'RQLExpression')
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
            for rdef in rschema.rdefs.itervalues():
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
