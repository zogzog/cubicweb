"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
change_relation_props('CWAttribute', 'cardinality', 'String', internationalizable=True)
change_relation_props('CWRelation', 'cardinality', 'String', internationalizable=True)

drop_relation_definition('CWPermission', 'require_state', 'State')

if confirm('cleanup require_permission relation'):
    try:
        newrschema = fsschema.rschema('require_permission')
    except KeyError:
        newrschema = None
    for rsubj, robj in schema.rschema('require_permission').rdefs():
        if newrschema is None or not newrschema.has_rdef(rsubj, robj):
            print 'removing', rsubj, 'require_permission', robj
            drop_relation_definition(rsubj, 'require_permission', robj, ask_confirm=False)
