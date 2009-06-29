"""cubicweb post creation script, set user's workflow

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

activatedeid = add_state(_('activated'), 'CWUser', initial=True)
deactivatedeid = add_state(_('deactivated'), 'CWUser')
add_transition(_('deactivate'), 'CWUser',
               (activatedeid,), deactivatedeid,
               requiredgroups=('managers',))
add_transition(_('activate'), 'CWUser',
               (deactivatedeid,), activatedeid,
               requiredgroups=('managers',))

# need this since we already have at least one user in the database (the default admin)
rql('SET X in_state S WHERE X is CWUser, S eid %s' % activatedeid)

# create anonymous user if all-in-one config and anonymous user has been specified
if hasattr(config, 'anonymous_user'):
    anonlogin, anonpwd = config.anonymous_user()
    if anonlogin:
        rql('INSERT CWUser X: X login %(login)s, X upassword %(pwd)s,'
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
            rql('INSERT CWProperty X: X pkey %(k)s, X value %(v)s', {'k': key, 'v': value})

# add PERM_USE_TEMPLATE_FORMAT permission
from cubicweb.schema import PERM_USE_TEMPLATE_FORMAT
eid = add_entity('CWPermission', name=PERM_USE_TEMPLATE_FORMAT,
                 label=_('use template languages'))
rql('SET X require_group G WHERE G name "managers", X eid %(x)s',
    {'x': eid}, 'x')
