"""
* the vregistry handle various type of objects interacting
  together. The vregistry handle registration of dynamically loaded
  objects and provide a convenient api access to those objects
  according to a context

* to interact with the vregistry, object should inherit from the
  VObject abstract class

* the selection procedure has been generalized by delegating to a
  selector, which is responsible to score the vobject according to the
  current state (req, rset, row, col). At the end of the selection, if
  a vobject class has been found, an instance of this class is
  returned. The selector is instantiated at vobject registration


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import sys
import types
from os import listdir, stat
from os.path import dirname, join, realpath, split, isdir, exists
from logging import getLogger
from warnings import warn

from cubicweb import CW_SOFTWARE_ROOT, set_log_methods
from cubicweb import RegistryNotFound, ObjectNotFound, NoSelectableObject


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


class VObject(object):
    """visual object, use to be handled somehow by the visual components
    registry.

    The following attributes should be set on concret vobject subclasses:

    :__registry__:
      name of the registry for this object (string like 'views',
      'templates'...)
    :id:
      object's identifier in the registry (string like 'main',
      'primary', 'folder_box')
    :__select__:
      class'selector

    Moreover, the `__abstract__` attribute may be set to True to indicate
    that a vobject is abstract and should not be registered
    """
    # necessary attributes to interact with the registry
    id = None
    __registry__ = None
    __select__ = None

    @classmethod
    def registered(cls, registry):
        """called by the registry when the vobject has been registered.

        It must return the  object that will be actually registered (this
        may be the right hook to create an instance for example). By
        default the vobject is returned without any transformation.
        """
        cls.build___select__()
        return cls

    @classmethod
    def selected(cls, *args, **kwargs):
        """called by the registry when the vobject has been selected.

        It must return the  object that will be actually returned by the
        .select method (this may be the right hook to create an
        instance for example). By default the selected object is
        returned without any transformation.
        """
        return cls

    @classmethod
    def classid(cls):
        """returns a unique identifier for the vobject"""
        return '%s.%s' % (cls.__module__, cls.__name__)

    # XXX bw compat code
    @classmethod
    def build___select__(cls):
        for klass in cls.mro():
            if klass.__name__ == 'AppRsetObject':
                continue # the bw compat __selector__ is there
            klassdict = klass.__dict__
            if ('__select__' in klassdict and '__selectors__' in klassdict
                and '__selgenerated__' not in klassdict):
                raise TypeError("__select__ and __selectors__ can't be used together on class %s" % cls)
            if '__selectors__' in klassdict and '__selgenerated__' not in klassdict:
                cls.__selgenerated__ = True
                # case where __selectors__ is defined locally (but __select__
                # is in a parent class)
                selectors = klassdict['__selectors__']
                if len(selectors) == 1:
                    # micro optimization: don't bother with AndSelector if there's
                    # only one selector
                    select = _instantiate_selector(selectors[0])
                else:
                    select = AndSelector(*selectors)
                cls.__select__ = select


class VRegistry(object):
    """class responsible to register, propose and select the various
    elements used to build the web interface. Currently, we have templates,
    views, actions and components.
    """

    def __init__(self, config):#, cache_size=1000):
        self.config = config
        # dictionnary of registry (themself dictionnary) by name
        self._registries = {}
        self._lastmodifs = {}

    def reset(self):
        self._registries = {}
        self._lastmodifs = {}

    def __getitem__(self, key):
        return self._registries[key]

    def get(self, key, default=None):
        return self._registries.get(key, default)

    def items(self):
        return self._registries.items()

    def values(self):
        return self._registries.values()

    def __contains__(self, key):
        return key in self._registries

    def registry(self, name):
        """return the registry (dictionary of class objects) associated to
        this name
        """
        try:
            return self._registries[name]
        except KeyError:
            raise RegistryNotFound(name), None, sys.exc_info()[-1]

    def registry_objects(self, name, oid=None):
        """returns objects registered with the given oid in the given registry.
        If no oid is given, return all objects in this registry
        """
        registry = self.registry(name)
        if oid is not None:
            try:
                return registry[oid]
            except KeyError:
                raise ObjectNotFound(oid), None, sys.exc_info()[-1]
        result = []
        for objs in registry.values():
            result += objs
        return result

    # dynamic selection methods ################################################

    def object_by_id(self, registry, oid, *args, **kwargs):
        """return object in <registry>.<oid>

        raise `ObjectNotFound` if not object with id <oid> in <registry>
        raise `AssertionError` if there is more than one object there
        """
        objects = self.registry_objects(registry, oid)
        assert len(objects) == 1, objects
        return objects[0].selected(*args, **kwargs)

    def select(self, registry, oid, *args, **kwargs):
        """return the most specific object in <registry>.<oid> according to
        the given context

        raise `ObjectNotFound` if not object with id <oid> in <registry>
        raise `NoSelectableObject` if not object apply
        """
        return self.select_best(self.registry_objects(registry, oid),
                                *args, **kwargs)

    def select_object(self, registry, oid, *args, **kwargs):
        """return the most specific object in <registry>.<oid> according to
        the given context, or None if no object apply
        """
        try:
            return self.select(registry, oid, *args, **kwargs)
        except (NoSelectableObject, ObjectNotFound):
            return None

    def possible_objects(self, registry, *args, **kwargs):
        """return an iterator on possible objects in <registry> for the given
        context
        """
        for vobjects in self.registry(registry).itervalues():
            try:
                yield self.select_best(vobjects, *args, **kwargs)
            except NoSelectableObject:
                continue

    def select_best(self, vobjects, *args, **kwargs):
        """return an instance of the most specific object according
        to parameters

        raise `NoSelectableObject` if not object apply
        """
        if len(args) > 1:
            warn('only the request param can not be named when calling select',
                 DeprecationWarning, stacklevel=2)
        score, winners = 0, []
        for vobject in vobjects:
            vobjectscore = vobject.__select__(vobject, *args, **kwargs)
            if vobjectscore > score:
                score, winners = vobjectscore, [vobject]
            elif vobjectscore > 0 and vobjectscore == score:
                winners.append(vobject)
        if not winners:
            raise NoSelectableObject('args: %s\nkwargs: %s %s'
                                     % (args, kwargs.keys(),
                                        [repr(v) for v in vobjects]))
        if len(winners) > 1:
            if self.config.mode == 'installed':
                self.error('select ambiguity, args: %s\nkwargs: %s %s',
                           args, kwargs.keys(), [repr(v) for v in winners])
            else:
                raise Exception('select ambiguity, args: %s\nkwargs: %s %s'
                                % (args, kwargs.keys(),
                                   [repr(v) for v in winners]))
        # return the result of the .selected method of the vobject
        return winners[0].selected(*args, **kwargs)

    # methods for explicit (un)registration ###################################

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
            if oid:
                self.register(obj)

    def register(self, obj, registryname=None, oid=None, clear=False):
        """base method to add an object in the registry"""
        assert not '__abstract__' in obj.__dict__
        registryname = registryname or obj.__registry__
        oid = oid or obj.id
        assert oid
        registry = self._registries.setdefault(registryname, {})
        if clear:
            vobjects = registry[oid] =  []
        else:
            vobjects = registry.setdefault(oid, [])
        # registered() is technically a classmethod but is not declared
        # as such because we need to compose registered in some cases
        vobject = obj.registered.im_func(obj, self)
        assert not vobject in vobjects, \
               'object %s is already registered' % vobject
        assert callable(vobject.__select__), vobject
        vobjects.append(vobject)
        try:
            vname = vobject.__name__
        except AttributeError:
            vname = vobject.__class__.__name__
        self.debug('registered vobject %s in registry %s with id %s',
                   vname, registryname, oid)
        # automatic reloading management
        self._loadedmods[obj.__module__]['%s.%s' % (obj.__module__, oid)] = obj

    def unregister(self, obj, registryname=None):
        registryname = registryname or obj.__registry__
        registry = self.registry(registryname)
        removed_id = obj.classid()
        for registered in registry.get(obj.id, ()):
            # use classid() to compare classes because vreg will probably
            # have its own version of the class, loaded through execfile
            if registered.classid() == removed_id:
                # XXX automatic reloading management
                registry[obj.id].remove(registered)
                break
        else:
            self.warning('can\'t remove %s, no id %s in the %s registry',
                         removed_id, obj.id, registryname)

    def register_and_replace(self, obj, replaced, registryname=None):
        # XXXFIXME this is a duplication of unregister()
        # remove register_and_replace in favor of unregister + register
        # or simplify by calling unregister then register here
        if hasattr(replaced, 'classid'):
            replaced = replaced.classid()
        registryname = registryname or obj.__registry__
        registry = self.registry(registryname)
        registered_objs = registry.get(obj.id, ())
        for index, registered in enumerate(registered_objs):
            if registered.classid() == replaced:
                del registry[obj.id][index]
                break
        else:
            self.warning('trying to replace an unregistered view %s by %s',
                         replaced, obj)
        self.register(obj, registryname=registryname)

    # intialization methods ###################################################

    def init_registration(self, path, extrapath=None):
        # compute list of all modules that have to be loaded
        self._toloadmods, filemods = _toload_info(path, extrapath)
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
        # load views from each directory in the application's path
        filemods = self.init_registration(path, extrapath)
        change = False
        for filepath, modname in filemods:
            if self.load_file(filepath, modname, force_reload):
                change = True
        return change

    def load_file(self, filepath, modname, force_reload=False):
        """load visual objects from a python file"""
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
            # if it was modified, unregister all exisiting objects
            # from this module, and keep track of what was unregistered
            unregistered = self.unregister_module_vobjects(modname)
        else:
            unregistered = None
        # load the module
        module = load_module_from_name(modname, use_sys=not force_reload)
        self.load_module(module)
        # if something was unregistered, we need to update places where it was
        # referenced
        if unregistered:
            # oldnew_mapping = {}
            registered = self._loadedmods[modname]
            oldnew_mapping = dict((unregistered[name], registered[name])
                                  for name in unregistered if name in registered)
            self.update_registered_subclasses(oldnew_mapping)
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
            if not issubclass(obj, VObject):
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
            self.register_vobject_class(obj)
        except Exception, ex:
            if self.config.mode in ('test', 'dev'):
                raise
            self.exception('vobject %s registration failed: %s', obj, ex)

    # old automatic registration XXX deprecated ###############################

    def register_vobject_class(self, cls):
        """handle vobject class registration

        vobject class with __abstract__ == True in their local dictionnary or
        with a name starting starting by an underscore are not registered.
        Also a vobject class needs to have __registry__ and id attributes set
        to a non empty string to be registered.
        """
        if (cls.__dict__.get('__abstract__') or cls.__name__[0] == '_'
            or not cls.__registry__ or not cls.id):
            return
        regname = cls.__registry__
        if '%s.%s' % (regname, cls.id) in self.config['disable-appobjects']:
            return
        self.register(cls)

    def unregister_module_vobjects(self, modname):
        """removes registered objects coming from a given module

        returns a dictionnary classid/class of all classes that will need
        to be updated after reload (i.e. vobjects referencing classes defined
        in the <modname> module)
        """
        unregistered = {}
        # browse each registered object
        for registry, objdict in self.items():
            for oid, objects in objdict.items():
                for obj in objects[:]:
                    objname = obj.classid()
                    # if the vobject is defined in this module, remove it
                    if objname.startswith(modname):
                        unregistered[objname] = obj
                        objects.remove(obj)
                        self.debug('unregistering %s in %s registry',
                                  objname, registry)
                    # if not, check if the vobject can be found in baseclasses
                    # (because we also want subclasses to be updated)
                    else:
                        if not isinstance(obj, type):
                            obj = obj.__class__
                        for baseclass in obj.__bases__:
                            if hasattr(baseclass, 'classid'):
                                baseclassid = baseclass.classid()
                                if baseclassid.startswith(modname):
                                    unregistered[baseclassid] = baseclass
                # update oid entry
                if objects:
                    objdict[oid] = objects
                else:
                    del objdict[oid]
        return unregistered

    def update_registered_subclasses(self, oldnew_mapping):
        """updates subclasses of re-registered vobjects

        if baseviews.PrimaryView is changed, baseviews.py will be reloaded
        automatically and the new version of PrimaryView will be registered.
        But all existing subclasses must also be notified of this change, and
        that's what this method does

        :param oldnew_mapping: a dict mapping old version of a class to
                               the new version
        """
        # browse each registered object
        for objdict in self.values():
            for objects in objdict.values():
                for obj in objects:
                    if not isinstance(obj, type):
                        obj = obj.__class__
                    # build new baseclasses tuple
                    newbases = tuple(oldnew_mapping.get(baseclass, baseclass)
                                     for baseclass in obj.__bases__)
                    # update obj's baseclasses tuple (__bases__) if needed
                    if newbases != obj.__bases__:
                        self.debug('updating %s.%s base classes',
                                  obj.__module__, obj.__name__)
                        obj.__bases__ = newbases

# init logging
set_log_methods(VObject, getLogger('cubicweb'))
set_log_methods(VRegistry, getLogger('cubicweb.registry'))


# selector base classes and operations ########################################

class Selector(object):
    """base class for selector classes providing implementation
    for operators ``&`` and ``|``

    This class is only here to give access to binary operators, the
    selector logic itself should be implemented in the __call__ method


    a selector is called to help choosing the correct object for a
    particular context by returning a score (`int`) telling how well
    the class given as first argument apply to the given context.

    0 score means that the class doesn't apply.
    """

    @property
    def func_name(self):
        # backward compatibility
        return self.__class__.__name__

    def search_selector(self, selector):
        """search for the given selector or selector instance in the selectors
        tree. Return it of None if not found
        """
        if self is selector:
            return self
        if isinstance(selector, type) and isinstance(self, selector):
            return self
        return None

    def __str__(self):
        return self.__class__.__name__

    def __and__(self, other):
        return AndSelector(self, other)
    def __rand__(self, other):
        return AndSelector(other, self)

    def __or__(self, other):
        return OrSelector(self, other)
    def __ror__(self, other):
        return OrSelector(other, self)

    def __invert__(self):
        return NotSelector(self)

    # XXX (function | function) or (function & function) not managed yet

    def __call__(self, cls, *args, **kwargs):
        return NotImplementedError("selector %s must implement its logic "
                                   "in its __call__ method" % self.__class__)

class MultiSelector(Selector):
    """base class for compound selector classes"""

    def __init__(self, *selectors):
        self.selectors = self.merge_selectors(selectors)

    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__,
                           ','.join(str(s) for s in self.selectors))

    @classmethod
    def merge_selectors(cls, selectors):
        """deal with selector instanciation when necessary and merge
        multi-selectors if possible:

        AndSelector(AndSelector(sel1, sel2), AndSelector(sel3, sel4))
        ==> AndSelector(sel1, sel2, sel3, sel4)
        """
        merged_selectors = []
        for selector in selectors:
            try:
                selector = _instantiate_selector(selector)
            except:
                pass
            #assert isinstance(selector, Selector), selector
            if isinstance(selector, cls):
                merged_selectors += selector.selectors
            else:
                merged_selectors.append(selector)
        return merged_selectors

    def search_selector(self, selector):
        """search for the given selector or selector instance in the selectors
        tree. Return it of None if not found
        """
        for childselector in self.selectors:
            if childselector is selector:
                return childselector
            found = childselector.search_selector(selector)
            if found is not None:
                return found
        return None


def objectify_selector(selector_func):
    """convenience decorator for simple selectors where a class definition
    would be overkill::

        @objectify_selector
        def yes(cls, *args, **kwargs):
            return 1

    """
    return type(selector_func.__name__, (Selector,),
                {'__call__': lambda self, *args, **kwargs: selector_func(*args, **kwargs)})

def _instantiate_selector(selector):
    """ensures `selector` is a `Selector` instance

    NOTE: This should only be used locally in build___select__()
    XXX: then, why not do it ??
    """
    if isinstance(selector, types.FunctionType):
        return objectify_selector(selector)()
    if isinstance(selector, type) and issubclass(selector, Selector):
        return selector()
    return selector


class AndSelector(MultiSelector):
    """and-chained selectors (formerly known as chainall)"""
    def __call__(self, cls, *args, **kwargs):
        score = 0
        for selector in self.selectors:
            partscore = selector(cls, *args, **kwargs)
            if not partscore:
                return 0
            score += partscore
        return score


class OrSelector(MultiSelector):
    """or-chained selectors (formerly known as chainfirst)"""
    def __call__(self, cls, *args, **kwargs):
        for selector in self.selectors:
            partscore = selector(cls, *args, **kwargs)
            if partscore:
                return partscore
        return 0

class NotSelector(Selector):
    """negation selector"""
    def __init__(self, selector):
        self.selector = selector

    def __call__(self, cls, *args, **kwargs):
        score = self.selector(cls, *args, **kwargs)
        return int(not score)

    def __str__(self):
        return 'NOT(%s)' % super(NotSelector, self).__str__()


# XXX bw compat functions #####################################################

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
