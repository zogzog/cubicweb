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
"""

"""
if __name__ == '__main__':

    from os.path import dirname, abspath
    from cubicweb import goa
    from cubicweb.goa.goaconfig import GAEConfiguration
    from cubicweb.goa.dbinit import create_user, create_groups

    # compute instance's root directory
    APPLROOT = dirname(abspath(__file__))
    # apply monkey patches first
    goa.do_monkey_patch()
    # get instance's configuration (will be loaded from app.conf file)
    GAEConfiguration.ext_resources['JAVASCRIPTS'].append('DATADIR/goa.js')
    config = GAEConfiguration('toto', APPLROOT)
    # create default groups
    create_groups()
    if not config['use-google-auth']:
        # create default admin
        create_user('admin', 'admin', ('managers', 'users'))
        # create anonymous user if specified
        anonlogin = config['anonymous-user']
        if anonlogin:
            create_user(anonlogin, config['anonymous-password'], ('guests',))
    print 'content initialized'
