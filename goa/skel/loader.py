"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
if __name__ == '__main__':

    from os.path import dirname, abspath
    from cubicweb import goa
    from cubicweb.goa.goaconfig import GAEConfiguration
    from cubicweb.goa.dbinit import create_user, create_groups

    # compute application's root directory
    APPLROOT = dirname(abspath(__file__))
    # apply monkey patches first
    goa.do_monkey_patch()
    # get application's configuration (will be loaded from app.conf file)
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
