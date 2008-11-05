change_relation_props('EFRDef', 'cardinality', 'String', internationalizable=True)
change_relation_props('ENFRDef', 'cardinality', 'String', internationalizable=True)

drop_relation_definition('EPermission', 'require_state', 'State')

if confirm('cleanup require_permission relation'):
    try:
        newrschema = newschema.rschema('require_permission')
    except KeyError:
        newrschema = None
    for rsubj, robj in schema.rschema('require_permission').rdefs():
        if newrschema is None or not newrschema.has_rdef(rsubj, robj):
            print 'removing', rsubj, 'require_permission', robj
            drop_relation_definition(rsubj, 'require_permission', robj, ask_confirm=False)
