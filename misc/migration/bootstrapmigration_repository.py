"""allways executed before all others in server migration

it should only include low level schema changes

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

applcubicwebversion, cubicwebversion = versions_map['cubicweb']

from cubicweb.server import schemaserial as ss
def _add_relation_definition_no_perms(subjtype, rtype, objtype):
    rschema = fsschema.rschema(rtype)
    for query, args in ss.rdef2rql(rschema, subjtype, objtype, groupmap=None):
        rql(query, args, ask_confirm=False)
    commit(ask_confirm=False)

if applcubicwebversion == (3, 6, 0) and cubicwebversion >= (3, 6, 0):
    _add_relation_definition_no_perms('CWAttribute', 'update_permission', 'CWGroup')
    _add_relation_definition_no_perms('CWAttribute', 'update_permission', 'RQLExpression')
    session.set_pool()
    session.unsafe_execute('SET X update_permission Y WHERE X is CWAttribute, X add_permission Y')
    drop_relation_definition('CWAttribute', 'add_permission', 'CWGroup')
    drop_relation_definition('CWAttribute', 'add_permission', 'RQLExpression')
    drop_relation_definition('CWAttribute', 'delete_permission', 'CWGroup')
    drop_relation_definition('CWAttribute', 'delete_permission', 'RQLExpression')

elif applcubicwebversion < (3, 6, 0) and cubicwebversion >= (3, 6, 0):
    session.set_pool()
    session.execute = session.unsafe_execute
    permsdict = ss.deserialize_ertype_permissions(session)

    changes = session.disable_hooks_category.add('integrity')
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
    if changes:
        session.enable_hooks_category.add(*changes)

if applcubicwebversion < (3, 4, 0) and cubicwebversion >= (3, 4, 0):

    session.set_shared_data('do-not-insert-cwuri', True)
    deactivate_verification_hooks()
    add_relation_type('cwuri')
    base_url = session.base_url()
    # use an internal session since some entity might forbid modifications to admin
    isession = repo.internal_session()
    for eid, in rql('Any X', ask_confirm=False):
        type, source, extid = session.describe(eid)
        if source == 'system':
            isession.execute('SET X cwuri %(u)s WHERE X eid %(x)s',
                             {'x': eid, 'u': base_url + u'eid/%s' % eid})
    isession.commit()
    reactivate_verification_hooks()
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
    for table in ('entities', 'deleted_entities'):
        for eid, extid in sql('SELECT eid, extid FROM %s WHERE extid is NOT NULL'
                              % table, ask_confirm=False):
            sql('UPDATE %s SET extid=%%(extid)s WHERE eid=%%(eid)s' % table,
                {'extid': b64encode(extid), 'eid': eid}, ask_confirm=False)
    commit()

if applcubicwebversion < (3, 2, 0) and cubicwebversion >= (3, 2, 0):
    add_cube('card', update_database=False)
