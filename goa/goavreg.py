"""goa specific registry

:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from os import listdir
from os.path import join, isdir

from cubicweb import CW_SOFTWARE_ROOT
from cubicweb.cwvreg import CubicWebVRegistry


def _pkg_name(cube, module):
    if cube is None:
        return module
    return 'cubes.%s.%s' % (cube, module)

class GAEVRegistry(CubicWebVRegistry):

    def set_schema(self, schema):
        """disable reload hooks of cubicweb registry set_schema method"""
        self.schema = schema

    def load(self, applroot):
        from cubicweb.goa import db
        self.load_module(db) # AnyEntity class
        # explicit loading, we don't want to load __init__.py
        self.load_directory(join(CW_SOFTWARE_ROOT, 'entities'),
                            'cubicweb.entities', skip=('__init__.py',))
        self.load_directory(join(CW_SOFTWARE_ROOT, 'web', 'views'),
                            'cubicweb.web.views')
        self.load_directory(join(CW_SOFTWARE_ROOT, 'goa', 'appobjects'),
                            'cubicweb.goa.appobjects')
        for cube in reversed(self.config.cubes()):
            self.load_cube(cube)
        self.load_instance(applroot)

    def load_directory(self, directory, cube, skip=()):
        for filename in listdir(directory):
            if filename[-3:] == '.py' and not filename in skip:
                self._import('%s.%s' % (cube, filename[:-3]))

    def load_cube(self, cube):
        self._auto_load(self.config.cube_dir(cube),
                        cube in self.config['included-cubes'],
                        cube)

    def load_instance(self, applroot):
        self._auto_load(applroot, self.config['schema-type'] == 'dbmodel')

    def _import(self, modname):
        obj = __import__(modname)
        for attr in modname.split('.')[1:]:
            obj = getattr(obj, attr)
        self.load_module(obj)

    def _auto_load(self, path, loadschema, cube=None):
        vobjpath = self.config.cube_vobject_path
        for filename in listdir(path):
            if filename[-3:] == '.py' and filename[:-3] in vobjpath:
                self._import(_pkg_name(cube, filename[:-3]))
            else:
                abspath = join(path, filename)
                if isdir(abspath) and filename in vobjpath:
                    self.load_directory(abspath, _pkg_name(cube, filename))
        if loadschema:
            # when using db.Model defined schema, the defined class is used as
            # entity class as well and so have to be registered
            self._import(_pkg_name(cube, 'schema'))
