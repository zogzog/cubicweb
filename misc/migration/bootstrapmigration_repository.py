"""allways executed before all others in server migration

it should only include low level schema changes

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

applcubicwebversion, cubicwebversion = versions_map['cubicweb']

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
    add_entity_type('Workflow')
    add_entity_type('BaseTransition')
    add_entity_type('WorkflowTransition')
    add_entity_type('SubWorkflowExitPoint')
    # drop explicit 'State allowed_transition Transition' since it should be
    # infered due to yams inheritance.  However we've to disable the schema
    # sync hook first to avoid to destroy existing data...
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
    checkpoint()

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
    checkpoint()

if applcubicwebversion < (3, 2, 0) and cubicwebversion >= (3, 2, 0):
    add_cube('card', update_database=False)
