"""cubicweb post creation script, set user's workflow

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

# insert versions
create_entity('CWProperty', pkey=u'system.version.cubicweb',
              value=unicode(config.cubicweb_version()))
for cube in config.cubes():
    create_entity('CWProperty', pkey=u'system.version.%s' % cube.lower(),
                  value=unicode(config.cube_version(cube)))

# some entities have been added before schema entities, fix the 'is' and
# 'is_instance_of' relations
for rtype in ('is', 'is_instance_of'):
    sql('INSERT INTO %s_relation '
        'SELECT X.eid, ET.cw_eid FROM entities as X, cw_CWEType as ET '
        'WHERE X.type=ET.cw_name AND NOT EXISTS('
        '      SELECT 1 from is_relation '
        '      WHERE eid_from=X.eid AND eid_to=ET.cw_eid)' % rtype)

# user workflow
userwf = add_workflow(_('default user workflow'), 'CWUser')
activated = userwf.add_state(_('activated'), initial=True)
deactivated = userwf.add_state(_('deactivated'))
userwf.add_transition(_('deactivate'), (activated,), deactivated,
                      requiredgroups=('managers',))
userwf.add_transition(_('activate'), (deactivated,), activated,
                      requiredgroups=('managers',))

# create anonymous user if all-in-one config and anonymous user has been specified
if hasattr(config, 'anonymous_user'):
    anonlogin, anonpwd = config.anonymous_user()
    if anonlogin == session.user.login:
        print 'you are using a manager account as anonymous user.'
        print 'Hopefully this is not a production instance...'
    elif anonlogin:
        rql('INSERT CWUser X: X login %(login)s, X upassword %(pwd)s,'
            'X in_group G WHERE G name "guests"',
            {'login': unicode(anonlogin), 'pwd': anonpwd})

# need this since we already have at least one user in the database (the default admin)
for user in rql('Any X WHERE X is CWUser').entities():
    session.unsafe_execute('SET X in_state S WHERE X eid %(x)s, S eid %(s)s',
                           {'x': user.eid, 's': activated.eid}, 'x')

# on interactive mode, ask for level 0 persistent options
if interactive_mode:
    cfg = config.persistent_options_configuration()
    cfg.input_config(inputlevel=0)
    for section, options in cfg.options_by_section():
        for optname, optdict, value in options:
            key = '%s.%s' % (section, optname)
            default = cfg.option_default(optname, optdict)
            # only record values differing from default
            if value != default:
                rql('INSERT CWProperty X: X pkey %(k)s, X value %(v)s', {'k': key, 'v': value})

# add PERM_USE_TEMPLATE_FORMAT permission
from cubicweb.schema import PERM_USE_TEMPLATE_FORMAT
usetmplperm = create_entity('CWPermission', name=PERM_USE_TEMPLATE_FORMAT,
                            label=_('use template languages'))
rql('SET X require_group G WHERE G name "managers", X eid %(x)s',
    {'x': usetmplperm.eid}, 'x')
