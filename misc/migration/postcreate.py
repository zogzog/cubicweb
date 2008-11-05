"""cubicweb post creation script, set user's workflow"""

activatedeid = add_state(_('activated'), 'EUser', initial=True)
deactivatedeid = add_state(_('deactivated'), 'EUser')
add_transition(_('deactivate'), 'EUser',
               (activatedeid,), deactivatedeid,
               requiredgroups=('managers',))
add_transition(_('activate'), 'EUser',
               (deactivatedeid,), activatedeid,
               requiredgroups=('managers',))

# need this since we already have at least one user in the database (the default admin)
rql('SET X in_state S WHERE X is EUser, S eid %s' % activatedeid)

# create anonymous user if all-in-one config and anonymous user has been specified
if hasattr(config, 'anonymous_user'):
    anonlogin, anonpwd = config.anonymous_user()
    if anonlogin:
        rql('INSERT EUser X: X login %(login)s, X upassword %(pwd)s,'
            'X in_state S, X in_group G WHERE G name "guests", S name "activated"',
            {'login': unicode(anonlogin), 'pwd': anonpwd})

cfg = config.persistent_options_configuration()
if interactive_mode:
    cfg.input_config(inputlevel=0)

for section, options in cfg.options_by_section():
    for optname, optdict, value in options:
        key = '%s.%s' % (section, optname)
        default = cfg.option_default(optname, optdict)
        # only record values differing from default
        if value != default:
            rql('INSERT EProperty X: X pkey %(k)s, X value %(v)s', {'k': key, 'v': value})

# add PERM_USE_TEMPLATE_FORMAT permission
from cubicweb.schema import PERM_USE_TEMPLATE_FORMAT
eid = add_entity('EPermission', name=PERM_USE_TEMPLATE_FORMAT,
                 label=_('use template languages'))
rql('SET X require_group G WHERE G name "managers", X eid %(x)s',
    {'x': eid}, 'x')    
