"""cubicweb on appengine plugins for cubicweb-ctl

:organization: Logilab
:copyright: 2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from os.path import exists, join, split, dirname, basename, normpath, abspath

from cubicweb import BadCommandUsage
from cubicweb import CW_SOFTWARE_ROOT
from cubicweb.toolsutils import (Command, register_commands, copy_skeleton,
                              create_dir, create_symlink, create_copy)
from cubicweb.cwconfig import CubicWebConfiguration

from logilab import common as lgc
from logilab.common.textutils import get_csv
from logilab import constraint as lgcstr
from logilab import mtconverter as lgmtc
import rql, yams, yapps, simplejson, dateutil, vobject, docutils, roman

SLINK_DIRECTORIES = (
    (lgc.__path__[0], 'logilab/common'),
    (lgmtc.__path__[0], 'logilab/mtconverter'),
    (lgcstr.__path__[0], 'logilab/constraint'),
    (rql.__path__[0], 'rql'),
    (simplejson.__path__[0], 'simplejson'),
    (yams.__path__[0], 'yams'),
    (yapps.__path__[0], 'yapps'),
    (dateutil.__path__[0], 'dateutil'),
    (vobject.__path__[0], 'vobject'),
    (docutils.__path__[0], 'docutils'),
    (roman.__file__.replace('.pyc', '.py'), 'roman.py'),

    (join(CW_SOFTWARE_ROOT, 'embedded', 'mx'), 'mx'),
    ('/usr/share/fckeditor/', 'fckeditor'),

    (join(CW_SOFTWARE_ROOT, 'web', 'data'), join('cubes', 'shared', 'data')), 
    (join(CW_SOFTWARE_ROOT, 'web', 'wdoc'), join('cubes', 'shared', 'wdoc')),
    (join(CW_SOFTWARE_ROOT, 'i18n'), join('cubes', 'shared', 'i18n')),
    (join(CW_SOFTWARE_ROOT, 'goa', 'tools'), 'tools'),
    (join(CW_SOFTWARE_ROOT, 'goa', 'bin'), 'bin'),
    )

COPY_CW_FILES = (
    '__init__.py',
    '__pkginfo__.py',
    '_exceptions.py',
    'dbapi.py',
    'cwvreg.py',
    'cwconfig.py',
    'interfaces.py',
    'rset.py',
    'schema.py',
    'schemaviewer.py',
    'vregistry.py',
    
    'common/appobject.py',
    'common/entity.py',
    'common/html4zope.py',
    'common/mail.py',
    'common/migration.py',
    'common/mixins.py',
    'common/mttransforms.py',
    'common/registerers.py',
    'common/rest.py',
    'common/selectors.py',
    'common/view.py',
    'common/uilib.py',
    'common/utils.py',

    'server/hookhelper.py',
    'server/hooksmanager.py',
    'server/hooks.py',
    'server/migractions.py',
    'server/pool.py',
    'server/querier.py',
    'server/repository.py',
    'server/rqlrewrite.py',
    'server/securityhooks.py',
    'server/session.py',
    'server/serverconfig.py',
    'server/ssplanner.py',
    'server/utils.py',
    'server/sources/__init__.py',

    'entities/__init__.py',
    'entities/authobjs.py',
    'entities/lib.py',
    'entities/schemaobjs.py',
    'entities/wfobjs.py',

    'sobjects/__init__.py',
    'sobjects/notification.py',
    
# XXX would be necessary for goa.testlib but require more stuff to be added
#     such as server.serverconfig and so on (check devtools.__init__)
#    'devtools/__init__.py',
#    'devtools/fake.py',
    
    'web/__init__.py',
    'web/_exceptions.py',
    'web/action.py',
    'web/application.py',
    'web/box.py',
    'web/component.py',
    'web/controller.py',
    'web/form.py',
    'web/htmlwidgets.py',
    'web/httpcache.py',
    'web/request.py',
    'web/webconfig.py',
    'web/widgets.py',

    'web/views/__init__.py',
    'web/views/actions.py',
    'web/views/basecomponents.py',
    'web/views/basecontrollers.py',
    'web/views/baseforms.py',
    'web/views/basetemplates.py',
    'web/views/baseviews.py',
    'web/views/boxes.py',
    'web/views/calendar.py',
    'web/views/error.py',
    'web/views/editcontroller.py',
    'web/views/ibreadcrumbs.py',
    'web/views/idownloadable.py',
    'web/views/magicsearch.py',
    'web/views/management.py',
    'web/views/navigation.py',
    'web/views/startup.py',
    'web/views/vcard.py',
    'web/views/wdoc.py',
    'web/views/urlpublishing.py',
    'web/views/urlrewrite.py',
    'web/views/xbel.py',

    'wsgi/__init__.py',
    'wsgi/handler.py',
    'wsgi/request.py',
    
    'goa/__init__.py',
    'goa/db.py',
    'goa/dbinit.py',
    'goa/dbmyams.py',
    'goa/goaconfig.py',
    'goa/goavreg.py',
    'goa/gaesource.py',
    'goa/rqlinterpreter.py',
    'goa/appobjects/__init__.py',
    'goa/appobjects/components.py', 
    'goa/appobjects/dbmgmt.py', 
    'goa/appobjects/gauthservice.py', 
    'goa/appobjects/sessions.py',

    'schemas/bootstrap.py',
    'schemas/base.py',
    )

OVERRIDEN_FILES = (
    ('toolsutils.py', 'toolsutils.py'),
    ('mttransforms.py', 'common/mttransforms.py'),
    ('server__init__.py', 'server/__init__.py'),
    ('rqlannotation.py', 'server/rqlannotation.py'),
    )


def create_init_file(pkgdir, pkgname):
    open(join(pkgdir, '__init__.py'), 'w').write('"""%s pkg"""' % pkgname)


class NewGoogleAppCommand(Command):
    """Create a new google appengine application.

    <application directory>
      the path to the appengine application directory
    """
    name = 'newgapp'
    arguments = '<application directory>'
    
    def run(self, args):
        if len(args) != 1:
            raise BadCommandUsage("exactly one argument is expected")
        appldir, = args
        appldir = normpath(abspath(appldir))
        appid = basename(appldir)
        context = {'appname': appid}
        # goa application'skeleton
        copy_skeleton(join(CW_SOFTWARE_ROOT, 'goa', 'skel'),
                      appldir, context, askconfirm=True)
        # cubicweb core dependancies
        for directory, subdirectory in SLINK_DIRECTORIES:
            subdirectory = join(appldir, subdirectory)
            if not exists(split(subdirectory)[0]):
                create_dir(split(subdirectory)[0])
            create_symlink(directory, join(appldir, subdirectory))
        create_init_file(join(appldir, 'logilab'), 'logilab')
        # copy supported part of cubicweb 
        create_dir(join(appldir, 'cubicweb'))
        for fpath in COPY_CW_FILES:
            target = join(appldir, 'cubicweb', fpath)
            if not exists(split(target)[0]):
                create_dir(split(target)[0])
            create_symlink(join(CW_SOFTWARE_ROOT, fpath), target)
        # overriden files
        create_init_file(join(appldir, 'cubicweb/common'), 'cubicweb.common')
        for fpath, subfpath in OVERRIDEN_FILES:
            create_symlink(join(CW_SOFTWARE_ROOT, 'goa', 'overrides', fpath),
                           join(appldir, 'cubicweb', subfpath))
        # link every supported components
        packagesdir = join(appldir, 'cubes')
        create_init_file(join(appldir, 'cubes'), 'cubes')
        cubesdir = CubicWebConfiguration.cubes_dir()
        for include in ('addressbook','basket', 'blog','classfolders',
                        'classtags', 'comment', 'file', 'link',
                        'mailinglist', 'person', 'task', 'zone',
                        ):
            create_symlink(join(cubesdir, include), join(packagesdir, include))
        # generate sample config
        from cubicweb.goa.goaconfig import GAEConfiguration
        from cubicweb.common.migration import MigrationHelper
        config = GAEConfiguration(appid, appldir)
        if exists(config.main_config_file()):
            mih = MigrationHelper(config)
            mih.rewrite_configuration()
        else:
            config.save()


register_commands((NewGoogleAppCommand,
                   ))
