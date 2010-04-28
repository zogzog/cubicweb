# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""cubicweb post creation script, set user's workflow

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
        from cubicweb.server import create_user
        create_user(session, unicode(anonlogin), anonpwd, 'guests')

# need this since we already have at least one user in the database (the default admin)
for user in rql('Any X WHERE X is CWUser').entities():
    rql('SET X in_state S WHERE X eid %(x)s, S eid %(s)s',
        {'x': user.eid, 's': activated.eid})

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
                rql('INSERT CWProperty X: X pkey %(k)s, X value %(v)s',
                    {'k': key, 'v': value})

# add PERM_USE_TEMPLATE_FORMAT permission
from cubicweb.schema import PERM_USE_TEMPLATE_FORMAT
usetmplperm = create_entity('CWPermission', name=PERM_USE_TEMPLATE_FORMAT,
                            label=_('use template languages'))
rql('SET X require_group G WHERE G name "managers", X eid %(x)s',
    {'x': usetmplperm.eid})
