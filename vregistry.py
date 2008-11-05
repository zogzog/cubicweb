"""
* the vregistry handle various type of objects interacting
  together. The vregistry handle registration of dynamically loaded
  objects and provide a convenient api access to those objects
  according to a context

* to interact with the vregistry, object should inherit from the
  VObject abstract class
  
* the registration procedure is delegated to a registerer. Each
  registerable vobject must defines its registerer class using the
  __registerer__ attribute.  A registerer is instantianted at
  registration time after what the instance is lost
  
* the selection procedure has been generalized by delegating to a
  selector, which is responsible to score the vobject according to the
  current state (req, rset, row, col). At the end of the selection, if
  a vobject class has been found, an instance of this class is
  returned. The selector is instantiated at vobject registration


:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

import sys
from os import listdir, stat
from os.path import dirname, join, realpath, split, isdir
from logging import getLogger

from cubicweb import CW_SOFTWARE_ROOT, set_log_methods
from cubicweb import RegistryNotFound, ObjectNotFound, NoSelectableObject


class vobject_helper(object):
    """object instantiated at registration time to help a wrapped
    VObject subclass
    """

    def __init__(self, registry, vobject):
        self.registry = registry
        self.vobject = vobject
        self.config = registry.config
        self.schema = registry.schema


class registerer(vobject_helper):
    """do whatever is needed at registration time for the wrapped
    class, according to current application schema and already
    registered objects of the same kind (i.e. same registry name and
    same id).

    The wrapped class may be skipped, some previously selected object
    may be kicked out... After whatever works needed, if the object or
    a transformed object is returned, it will be added to previously
    registered objects.
    """

    def __init__(self, registry, vobject):
        super(registerer, self).__init__(registry, vobject)
        self.kicked = set()
    
    def do_it_yourself(self, registered):
        raise NotImplementedError(str(self.vobject))
        
    def kick(self, registered, kicked):
        self.debug('kicking vobject %s', kicked)
        registered.remove(kicked)
        self.kicked.add(kicked.classid())
        
    def skip(self):
        self.debug('no schema compat, skipping %s', self.vobject)


def selector(cls, *args, **kwargs):
    """selector is called to help choosing the correct object for a
    particular request and result set by returning a score.

    it must implement a .score_method taking a request, a result set and
    optionaly row and col arguments which return an int telling how well
    the wrapped class apply to the given request and result set. 0 score
    means that it doesn't apply.
    
    rset may be None. If not, row and col arguments may be optionally
    given if the registry is scoring a given row or a given cell of
    the result set (both row and col are int if provided).
    """    
    raise NotImplementedError(cls)


class autoselectors(type):
    """implements __selectors__ / __select__ compatibility layer so that:

    __select__ = chainall(classmethod(A, B, C))

    can be replaced by something like:
    
    __selectors__ = (A, B, C)
    """
    def __new__(mcs, name, bases, classdict):
        if '__select__' in classdict and '__selectors__' in classdict:
            raise TypeError("__select__ and __selectors__ "
                            "can't be used together")
        if '__select__' not in classdict and '__selectors__' in classdict:
            selectors = classdict['__selectors__']
            classdict['__select__'] = classmethod(chainall(*selectors))
        return super(autoselectors, mcs).__new__(mcs, name, bases, classdict)

    def __setattr__(self, attr, value):
        if attr == '__selectors__':
            self.__select__ = classmethod(chainall(*value))
        super(autoselectors, self).__setattr__(attr, value)
            

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
    :__registerer__:
      registration helper class
    :__select__:
      selection helper function
    :__selectors__:
      tuple of selectors to be chained
      (__select__ and __selectors__ are mutually exclusive)
      
    Moreover, the `__abstract__` attribute may be set to True to indicate
    that a vobject is abstract and should not be registered
    """
    __metaclass__ = autoselectors
    # necessary attributes to interact with the registry
    id = None
    __registry__ = None
    __registerer__ = None
    __select__ = None

    @classmethod
    def registered(cls, registry):
        """called by the registry when the vobject has been registered.

        It must return the  object that will be actually registered (this
        may be the right hook to create an instance for example). By
        default the vobject is returned without any transformation.
        """
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
        
    def register_vobject_class(self, cls, _kicked=set()):
        """handle vobject class registration
        
        vobject class with __abstract__ == True in their local dictionnary or
        with a name starting starting by an underscore are not registered.
        Also a vobject class needs to have __registry__ and id attributes set
        to a non empty string to be registered.

        Registration is actually handled by vobject's registerer.
        """
        if (cls.__dict__.get('__abstract__') or cls.__name__[0] == '_'
            or not cls.__registry__ or not cls.id):
            return
        # while reloading a module :
        # if cls was previously kicked, it means that there is a more specific
        # vobject defined elsewhere re-registering cls would kick it out
        if cls.classid() in _kicked:
            self.debug('not re-registering %s because it was previously kicked',
                      cls.classid())
        else:
            regname = cls.__registry__
            if cls.id in self.config['disable-%s' % regname]:
                return
            registry = self._registries.setdefault(regname, {})
            vobjects = registry.setdefault(cls.id, [])
            registerer = cls.__registerer__(self, cls)
            cls = registerer.do_it_yourself(vobjects)
            #_kicked |= registerer.kicked
            if cls:
                vobject = cls.registered(self)
                try:
                    vname = vobject.__name__
                except AttributeError:
                    vname = vobject.__class__.__name__
                self.debug('registered vobject %s in registry %s with id %s',
                          vname, cls.__registry__, cls.id)
                vobjects.append(vobject)
            
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
        if oid:
            try:
                return registry[oid]
            except KeyError:
                raise ObjectNotFound(oid), None, sys.exc_info()[-1]
        else:
            result = []
            for objs in registry.values():
                result += objs
            return result
        
    def select(self, vobjects, *args, **kwargs):
        """return an instance of the most specific object according
        to parameters

        raise NoSelectableObject if not object apply
        """
        score, winner = 0, None
        for vobject in vobjects:
            vobjectscore = vobject.__select__(*args, **kwargs)
            if vobjectscore > score:
                score, winner = vobjectscore, vobject
        if winner is None:
            raise NoSelectableObject('args: %s\nkwargs: %s %s'
                                     % (args, kwargs.keys(), [repr(v) for v in vobjects]))
        # return the result of the .selected method of the vobject
        return winner.selected(*args, **kwargs)
    
    def possible_objects(self, registry, *args, **kwargs):
        """return an iterator on possible objects in a registry for this result set

        actions returned are classes, not instances
        """
        for vobjects in self.registry(registry).values():
            try:
                yield self.select(vobjects, *args, **kwargs)
            except NoSelectableObject:
                continue

    def select_object(self, registry, cid, *args, **kwargs):
        """return the most specific component according to the resultset"""
        return self.select(self.registry_objects(registry, cid), *args, **kwargs)

    def object_by_id(self, registry, cid, *args, **kwargs):
        """return the most specific component according to the resultset"""
        objects = self[registry][cid]
        assert len(objects) == 1, objects
        return objects[0].selected(*args, **kwargs)
    
    # intialization methods ###################################################

    
    def register_objects(self, path, force_reload=None):
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
        change = False
        for fileordirectory in path:
            if isdir(fileordirectory):
                if self.read_directory(fileordirectory, force_reload):
                    change = True
            else:
                directory, filename = split(fileordirectory)
                if self.load_file(directory, filename, force_reload):
                    change = True
        if change:
            for registry, objects in self.items():
                self.debug('available in registry %s: %s', registry,
                           sorted(objects))
        return change
    
    def read_directory(self, directory, force_reload=False):
        """read a directory and register available views"""
        modified_on = stat(realpath(directory))[-2]
        # only read directory if it was modified
        _lastmodifs = self._lastmodifs
        if directory in _lastmodifs and modified_on <= _lastmodifs[directory]:
            return False
        self.info('loading directory %s', directory)
        for filename in listdir(directory):
            if filename[-3:] == '.py':
                try:
                    self.load_file(directory, filename, force_reload)
                except OSError:
                    # this typically happens on emacs backup files (.#foo.py)
                    self.warning('Unable to load file %s. It is likely to be a backup file',
                                 filename)
                except Exception, ex:
                    if self.config.mode in ('dev', 'test'):
                        raise
                    self.exception('%r while loading file %s', ex, filename)
        _lastmodifs[directory] = modified_on
        return True

    def load_file(self, directory, filename, force_reload=False):
        """load visual objects from a python file"""
        from logilab.common.modutils import load_module_from_modpath, modpath_from_file
        filepath = join(directory, filename)
        modified_on = stat(filepath)[-2]
        modpath = modpath_from_file(join(directory, filename))
        modname = '.'.join(modpath)
        unregistered = {}
        _lastmodifs = self._lastmodifs
        if filepath in _lastmodifs:
            # only load file if it was modified
            if modified_on <= _lastmodifs[filepath]:
                return
            else:
                # if it was modified, unregister all exisiting objects
                # from this module, and keep track of what was unregistered
                unregistered = self.unregister_module_vobjects(modname)
        # load the module
        module = load_module_from_modpath(modpath, use_sys=not force_reload)
        registered = self.load_module(module)
        # if something was unregistered, we need to update places where it was
        # referenced 
        if unregistered:
            # oldnew_mapping = {}
            oldnew_mapping = dict((unregistered[name], registered[name])
                                  for name in unregistered if name in registered)
            self.update_registered_subclasses(oldnew_mapping)
        _lastmodifs[filepath] = modified_on
        return True

    def load_module(self, module):
        registered = {}
        self.info('loading %s', module)
        for objname, obj in vars(module).items():
            if objname.startswith('_'):
                continue
            self.load_ancestors_then_object(module.__name__, registered, obj)
        return registered
    
    def load_ancestors_then_object(self, modname, registered, obj):
        # skip imported classes
        if getattr(obj, '__module__', None) != modname:
            return
        # skip non registerable object
        try:
            if not issubclass(obj, VObject):
                return
        except TypeError:
            return
        objname = '%s.%s' % (modname, obj.__name__)
        if objname in registered:
            return
        registered[objname] = obj
        for parent in obj.__bases__:
            self.load_ancestors_then_object(modname, registered, parent)
        self.load_object(obj)
            
    def load_object(self, obj):
        try:
            self.register_vobject_class(obj)
        except Exception, ex:
            if self.config.mode in ('test', 'dev'):
                raise
            self.exception('vobject %s registration failed: %s', obj, ex)
        
# init logging 
set_log_methods(VObject, getLogger('cubicweb'))
set_log_methods(VRegistry, getLogger('cubicweb.registry'))
set_log_methods(registerer, getLogger('cubicweb.registration'))


# advanced selector building functions ########################################

def chainall(*selectors):
    """return a selector chaining given selectors. If one of
    the selectors fail, selection will fail, else the returned score
    will be the sum of each selector'score
    """
    assert selectors
    def selector(cls, *args, **kwargs):
        score = 0
        for selector in selectors:
            partscore = selector(cls, *args, **kwargs)
            if not partscore:
                return 0
            score += partscore
        return score
    return selector

def chainfirst(*selectors):
    """return a selector chaining given selectors. If all
    the selectors fail, selection will fail, else the returned score
    will be the first non-zero selector score
    """
    assert selectors
    def selector(cls, *args, **kwargs):
        for selector in selectors:
            partscore = selector(cls, *args, **kwargs)
            if partscore:
                return partscore
        return 0
    return selector

