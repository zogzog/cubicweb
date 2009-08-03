"""
* the vregistry handles various types of objects interacting
  together. The vregistry handles registration of dynamically loaded
  objects and provides a convenient api to access those objects
  according to a context

* to interact with the vregistry, objects should inherit from the
  AppObject abstract class

* the selection procedure has been generalized by delegating to a
  selector, which is responsible to score the appobject according to the
  current state (req, rset, row, col). At the end of the selection, if
  a appobject class has been found, an instance of this class is
  returned. The selector is instantiated at appobject registration


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import sys
from os import listdir, stat
from os.path import dirname, join, realpath, split, isdir, exists
from logging import getLogger
from warnings import warn

from logilab.common.deprecation import deprecated, class_moved
from logilab.common.logging_ext import set_log_methods

from cubicweb import CW_SOFTWARE_ROOT
from cubicweb import (RegistryNotFound, ObjectNotFound, NoSelectableObject,
                      RegistryOutOfDate)
from cubicweb.appobject import AppObject

# XXX depending on cubicweb.web is ugly, we should deal with uicfg
#     reset with a good old event / callback system
try:
    from cubicweb.web import uicfg
except ImportError: # cubicweb.web not installed
    uicfg = None

def _toload_info(path, extrapath, _toload=None):
    """return a dictionary of <modname>: <modpath> and an ordered list of
    (file, module name) to load
    """
    from logilab.common.modutils import modpath_from_file
    if _toload is None:
        assert isinstance(path, list)
        _toload = {}, []
    for fileordir in path:
        if isdir(fileordir) and exists(join(fileordir, '__init__.py')):
            subfiles = [join(fileordir, fname) for fname in listdir(fileordir)]
            _toload_info(subfiles, extrapath, _toload)
        elif fileordir[-3:] == '.py':
            modname = '.'.join(modpath_from_file(fileordir, extrapath))
            _toload[0][modname] = fileordir
            _toload[1].append((fileordir, modname))
    return _toload


class Registry(dict):

    def __init__(self, config):
        super(Registry, self).__init__()
        self.config = config

    def __getitem__(self, name):
        """return the registry (dictionary of class objects) associated to
        this name
        """
        try:
            return super(Registry, self).__getitem__(name)
        except KeyError:
            raise ObjectNotFound(name), None, sys.exc_info()[-1]

    def register(self, obj, oid=None, clear=False):
        """base method to add an object in the registry"""
        assert not '__abstract__' in obj.__dict__
        oid = oid or obj.id
        assert oid
        if clear:
            appobjects = self[oid] =  []
        else:
            appobjects = self.setdefault(oid, [])
        # registered() is technically a classmethod but is not declared
        # as such because we need to compose registered in some cases
        appobject = obj.registered.im_func(obj, self)
        assert not appobject in appobjects, \
               'object %s is already registered' % appobject
        assert callable(appobject.__select__), appobject
        appobjects.append(appobject)

    def register_and_replace(self, obj, replaced):
        # XXXFIXME this is a duplication of unregister()
        # remove register_and_replace in favor of unregister + register
        # or simplify by calling unregister then register here
        if hasattr(replaced, 'classid'):
            replaced = replaced.classid()
        registered_objs = self.get(obj.id, ())
        for index, registered in enumerate(registered_objs):
            if registered.classid() == replaced:
                del registered_objs[index]
                break
        else:
            self.warning('trying to replace an unregistered view %s by %s',
                         replaced, obj)
        self.register(obj)

    def unregister(self, obj):
        oid = obj.classid()
        for registered in self.get(obj.id, ()):
            # use classid() to compare classes because vreg will probably
            # have its own version of the class, loaded through execfile
            if registered.classid() == oid:
                # XXX automatic reloading management
                self[obj.id].remove(registered)
                break
        else:
            self.warning('can\'t remove %s, no id %s in the registry',
                         oid, obj.id)

    def all_objects(self):
        """return a list containing all objects in this registry.
        """
        result = []
        for objs in self.values():
            result += objs
        return result

    # dynamic selection methods ################################################

    def object_by_id(self, oid, *args, **kwargs):
        """return object with the given oid. Only one object is expected to be
        found.

        raise `ObjectNotFound` if not object with id <oid> in <registry>
        raise `AssertionError` if there is more than one object there
        """
        objects = self[oid]
        assert len(objects) == 1, objects
        return objects[0](*args, **kwargs)

    def select(self, oid, *args, **kwargs):
        """return the most specific object among those with the given oid
        according to the given context.

        raise `ObjectNotFound` if not object with id <oid> in <registry>
        raise `NoSelectableObject` if not object apply
        """
        return self.select_best(self[oid], *args, **kwargs)

    def select_object(self, oid, *args, **kwargs):
        """return the most specific object among those with the given oid
        according to the given context, or None if no object applies.
        """
        try:
            return self.select(oid, *args, **kwargs)
        except (NoSelectableObject, ObjectNotFound):
            return None

    def possible_objects(self, *args, **kwargs):
        """return an iterator on possible objects in this registry for the given
        context
        """
        for appobjects in self.itervalues():
            try:
                yield self.select_best(appobjects, *args, **kwargs)
            except NoSelectableObject:
                continue

    def select_best(self, appobjects, *args, **kwargs):
        """return an instance of the most specific object according
        to parameters

        raise `NoSelectableObject` if not object apply
        """
        if len(args) > 1:
            warn('only the request param can not be named when calling select',
                 DeprecationWarning, stacklevel=3)
        score, winners = 0, []
        for appobject in appobjects:
            appobjectscore = appobject.__select__(appobject, *args, **kwargs)
            if appobjectscore > score:
                score, winners = appobjectscore, [appobject]
            elif appobjectscore > 0 and appobjectscore == score:
                winners.append(appobject)
        if not winners:
            raise NoSelectableObject('args: %s\nkwargs: %s %s'
                                     % (args, kwargs.keys(),
                                        [repr(v) for v in appobjects]))
        if len(winners) > 1:
            if self.config.mode == 'installed':
                self.error('select ambiguity, args: %s\nkwargs: %s %s',
                           args, kwargs.keys(), [repr(v) for v in winners])
            else:
                raise Exception('select ambiguity, args: %s\nkwargs: %s %s'
                                % (args, kwargs.keys(),
                                   [repr(v) for v in winners]))
        # return the result of calling the appobject
        return winners[0](*args, **kwargs)


class VRegistry(dict):
    """class responsible to register, propose and select the various
    elements used to build the web interface. Currently, we have templates,
    views, actions and components.
    """

    def __init__(self, config):
        super(VRegistry, self).__init__()
        self.config = config

    def reset(self, force_reload=None):
        self.clear()
        self._lastmodifs = {}
        # don't reload uicfg when appobjects modules won't be reloaded as well
        if uicfg is not None:
            if force_reload is None:
                force_reload = self.config.mode == 'dev'
            if force_reload:
                reload(uicfg)

    def __getitem__(self, name):
        """return the registry (dictionary of class objects) associated to
        this name
        """
        try:
            return super(VRegistry, self).__getitem__(name)
        except KeyError:
            raise RegistryNotFound(name), None, sys.exc_info()[-1]

    # dynamic selection methods ################################################

    @deprecated('use vreg[registry].object_by_id(oid, *args, **kwargs)')
    def object_by_id(self, registry, oid, *args, **kwargs):
        """return object in <registry>.<oid>

        raise `ObjectNotFound` if not object with id <oid> in <registry>
        raise `AssertionError` if there is more than one object there
        """
        return self[registry].object_by_id(oid)

    @deprecated('use vreg[registry].select(oid, *args, **kwargs)')
    def select(self, registry, oid, *args, **kwargs):
        """return the most specific object in <registry>.<oid> according to
        the given context

        raise `ObjectNotFound` if not object with id <oid> in <registry>
        raise `NoSelectableObject` if not object apply
        """
        return self[registry].select(oid, *args, **kwargs)

    @deprecated('use vreg[registry].select_object(oid, *args, **kwargs)')
    def select_object(self, registry, oid, *args, **kwargs):
        """return the most specific object in <registry>.<oid> according to
        the given context, or None if no object apply
        """
        return self[registry].select_object(oid, *args, **kwargs)

    @deprecated('use vreg[registry].possible_objects(*args, **kwargs)')
    def possible_objects(self, registry, *args, **kwargs):
        """return an iterator on possible objects in <registry> for the given
        context
        """
        return self[registry].possible_objects(*args, **kwargs)

    # methods for explicit (un)registration ###################################

    # default class, when no specific class set
    REGISTRY_FACTORY = {None: Registry}

    def registry_class(self, regid):
        try:
            return self.REGISTRY_FACTORY[regid]
        except KeyError:
            return self.REGISTRY_FACTORY[None]

    def setdefault(self, regid):
        try:
            return self[regid]
        except KeyError:
            self[regid] = self.registry_class(regid)(self.config)
            return self[regid]

#     def clear(self, key):
#         regname, oid = key.split('.')
#         self[regname].pop(oid, None)

    def register_all(self, objects, modname, butclasses=()):
        for obj in objects:
            try:
                if obj.__module__ != modname or obj in butclasses:
                    continue
                oid = obj.id
            except AttributeError:
                continue
            if oid and not '__abstract__' in obj.__dict__:
                self.register(obj)

    def register(self, obj, registryname=None, oid=None, clear=False):
        """base method to add an object in the registry"""
        assert not '__abstract__' in obj.__dict__
        registryname = registryname or obj.__registry__
        registry = self.setdefault(registryname)
        registry.register(obj, oid=oid, clear=clear)
        try:
            vname = obj.__name__
        except AttributeError:
            vname = obj.__class__.__name__
        self.debug('registered appobject %s in registry %s with id %s',
                   vname, registryname, oid)
        self._loadedmods[obj.__module__]['%s.%s' % (obj.__module__, oid)] = obj

    def unregister(self, obj, registryname=None):
        self[registryname or obj.__registry__].unregister(obj)

    def register_and_replace(self, obj, replaced, registryname=None):
        self[registryname or obj.__registry__].register_and_replace(obj, replaced)

    # initialization methods ###################################################

    def init_registration(self, path, extrapath=None):
        # compute list of all modules that have to be loaded
        self._toloadmods, filemods = _toload_info(path, extrapath)
        # XXX is _loadedmods still necessary ? It seems like it's useful
        #     to avoid loading same module twice, especially with the
        #     _load_ancestors_then_object logic but this needs to be checked
        self._loadedmods = {}
        return filemods

    def register_objects(self, path, force_reload=None, extrapath=None):
        if force_reload is None:
            force_reload = self.config.mode == 'dev'
        elif not force_reload:
            # force_reload == False usually mean modules have been reloaded
            # by another connection, so we want to update the registry
            # content even if there has been no module content modification
            self.reset()
        # need to clean sys.path this to avoid import confusion pb (i.e.
        # having the same module loaded as 'cubicweb.web.views' subpackage and
        # as views'  or 'web.views' subpackage
        # this is mainly for testing purpose, we should'nt need this in
        # production environment
        for webdir in (join(dirname(realpath(__file__)), 'web'),
                       join(dirname(__file__), 'web')):
            if webdir in sys.path:
                sys.path.remove(webdir)
        if CW_SOFTWARE_ROOT in sys.path:
            sys.path.remove(CW_SOFTWARE_ROOT)
        # load views from each directory in the instance's path
        filemods = self.init_registration(path, extrapath)
        change = False
        for filepath, modname in filemods:
            if self.load_file(filepath, modname, force_reload):
                change = True
        return change

    def load_file(self, filepath, modname, force_reload=False):
        """load app objects from a python file"""
        from logilab.common.modutils import load_module_from_name
        if modname in self._loadedmods:
            return
        self._loadedmods[modname] = {}
        try:
            modified_on = stat(filepath)[-2]
        except OSError:
            # this typically happens on emacs backup files (.#foo.py)
            self.warning('Unable to load %s. It is likely to be a backup file',
                         filepath)
            return False
        if filepath in self._lastmodifs:
            # only load file if it was modified
            if modified_on <= self._lastmodifs[filepath]:
                return
            # if it was modified, raise RegistryOutOfDate to reload everything
            self.info('File %s changed since last visit', filepath)
            raise RegistryOutOfDate()
        # load the module
        module = load_module_from_name(modname, use_sys=not force_reload)
        self.load_module(module)
        self._lastmodifs[filepath] = modified_on
        return True

    def load_module(self, module):
        self.info('loading %s', module)
        if hasattr(module, 'registration_callback'):
            module.registration_callback(self)
        else:
            for objname, obj in vars(module).items():
                if objname.startswith('_'):
                    continue
                self._load_ancestors_then_object(module.__name__, obj)
        self.debug('loaded %s', module)

    def _load_ancestors_then_object(self, modname, obj):
        # imported classes
        objmodname = getattr(obj, '__module__', None)
        if objmodname != modname:
            if objmodname in self._toloadmods:
                self.load_file(self._toloadmods[objmodname], objmodname)
            return
        # skip non registerable object
        try:
            if not issubclass(obj, AppObject):
                return
        except TypeError:
            return
        objname = '%s.%s' % (modname, obj.__name__)
        if objname in self._loadedmods[modname]:
            return
        self._loadedmods[modname][objname] = obj
        for parent in obj.__bases__:
            self._load_ancestors_then_object(modname, parent)
        self.load_object(obj)

    def load_object(self, obj):
        try:
            self.register_appobject_class(obj)
        except Exception, ex:
            if self.config.mode in ('test', 'dev'):
                raise
            self.exception('appobject %s registration failed: %s', obj, ex)

    # old automatic registration XXX deprecated ###############################

    def register_appobject_class(self, cls):
        """handle appobject class registration

        appobject class with __abstract__ == True in their local dictionnary or
        with a name starting starting by an underscore are not registered.
        Also a appobject class needs to have __registry__ and id attributes set
        to a non empty string to be registered.
        """
        if (cls.__dict__.get('__abstract__') or cls.__name__[0] == '_'
            or not cls.__registry__ or not cls.id):
            return
        regname = cls.__registry__
        if '%s.%s' % (regname, cls.id) in self.config['disable-appobjects']:
            return
        self.register(cls)

# init logging
set_log_methods(VRegistry, getLogger('cubicweb.vreg'))
set_log_methods(Registry, getLogger('cubicweb.registry'))


# XXX bw compat functions #####################################################

from cubicweb.appobject import objectify_selector, AndSelector, OrSelector, Selector

objectify_selector = deprecated('objectify_selector has been moved to appobject module')(objectify_selector)

Selector = class_moved(Selector)

@deprecated('use & operator (binary and)')
def chainall(*selectors, **kwargs):
    """return a selector chaining given selectors. If one of
    the selectors fail, selection will fail, else the returned score
    will be the sum of each selector'score
    """
    assert selectors
    # XXX do we need to create the AndSelector here, a tuple might be enough
    selector = AndSelector(*selectors)
    if 'name' in kwargs:
        selector.__name__ = kwargs['name']
    return selector

@deprecated('use | operator (binary or)')
def chainfirst(*selectors, **kwargs):
    """return a selector chaining given selectors. If all
    the selectors fail, selection will fail, else the returned score
    will be the first non-zero selector score
    """
    assert selectors
    selector = OrSelector(*selectors)
    if 'name' in kwargs:
        selector.__name__ = kwargs['name']
    return selector
