"""This file contains some basic registerers required by application objects
registry to handle registration at startup time.

A registerer is responsible to tell if an object should be registered according
to the application's schema or to already registered object

:organization: Logilab
:copyright: 2006-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.vregistry import registerer


def _accepts_interfaces(obj):
    return sorted(getattr(obj, 'accepts_interfaces', ()))


class yes_registerer(registerer):
    """register without any other action"""
    def do_it_yourself(self, registered):
        return self.vobject

class priority_registerer(registerer):
    """systematically kick previous registered class and register the
    wrapped class (based on the fact that directory containing vobjects
    are loaded from the most generic to the most specific).

    This is usually for templates or startup views where we want to
    keep only the latest in the load path
    """
    def do_it_yourself(self, registered):
        if registered:
            if len(registered) > 1:
                self.warning('priority_registerer found more than one registered objects '
                             '(registerer monkey patch ?)')
            for regobj in registered[:]:
                self.kick(registered, regobj)
        return self.vobject
    
    def remove_equivalents(self, registered):
        for _obj in registered[:]:
            if self.equivalent(_obj):
                self.kick(registered, _obj)
                break
            
    def remove_all_equivalents(self, registered):
        for _obj in registered[:]:
            if _obj is self.vobject:
                continue
            if self.equivalent(_obj):
                self.kick(registered, _obj)

    def equivalent(self, other):
        raise NotImplementedError(self, self.vobject)


class kick_registerer(registerer):
    """systematically kick previous registered class and don't register the
    wrapped class. This is temporarily used to discard library object registrable
    but that we don't want to use
    """
    def do_it_yourself(self, registered):
        if registered:
            self.kick(registered, registered[-1])
        return 
    

class accepts_registerer(priority_registerer):
    """register according to the .accepts attribute of the wrapped
    class, which should be a tuple refering some entity's types

    * if no type is defined the application'schema, skip the wrapped
      class
    * if the class defines a requires attribute, each entity type defined
      in the requires list must be in the schema
    * if an object previously registered has equivalent .accepts
      attribute, kick it out
    * register
    """
    def do_it_yourself(self, registered):
        # if object is accepting interface, we have register it now and
        # remove it latter if no object is implementing accepted interfaces
        if _accepts_interfaces(self.vobject):
            return self.vobject
        if not 'Any' in self.vobject.accepts:
            for ertype in self.vobject.accepts:
                if ertype in self.schema:
                    break
            else:
                self.skip()
                return None
        for required in getattr(self.vobject, 'requires', ()):
            if required not in self.schema:
                self.skip()
                return
        self.remove_equivalents(registered)
        return self.vobject
    
    def equivalent(self, other):
        if _accepts_interfaces(self.vobject) != _accepts_interfaces(other):
            return False
        if getattr(self.vobject, 'require_groups', ()) != getattr(other, 'require_groups', ()):
            return False
        try:
            newaccepts = list(other.accepts)
            for etype in self.vobject.accepts:
                try:
                    newaccepts.remove(etype)
                except ValueError:
                    continue
            if newaccepts:
                other.accepts = tuple(newaccepts)
                return False
            return True
        except AttributeError:
            return False


class id_registerer(priority_registerer):
    """register according to the "id" attribute of the wrapped class,
    refering to an entity type.
    
    * if the type is not Any and is not defined the application'schema,
      skip the wrapped class
    * if an object previously registered has the same .id attribute,
      kick it out
    * register
    """
    def do_it_yourself(self, registered):
        etype = self.vobject.id
        if etype != 'Any' and not self.schema.has_entity(etype):
            self.skip()
            return
        self.remove_equivalents(registered)
        return self.vobject
    
    def equivalent(self, other):
        return other.id == self.vobject.id


class etype_rtype_registerer(registerer):
    """registerer handling optional .etype and .rtype attributes.:
    
    * if .etype is set and is not an entity type defined in the
      application schema, skip the wrapped class
    * if .rtype or .relname is set and is not a relation type defined in
      the application schema, skip the wrapped class
    * register
    """
    def do_it_yourself(self, registered):
        cls = self.vobject
        if hasattr(cls, 'etype'):
            if not self.schema.has_entity(cls.etype):
                return
        rtype = getattr(cls, 'rtype', None)
        if rtype and not self.schema.has_relation(rtype):
            return
        return cls

class etype_rtype_priority_registerer(etype_rtype_registerer):
    """add priority behaviour to the etype_rtype_registerer
    """
    def do_it_yourself(self, registered):
        cls = super(etype_rtype_priority_registerer, self).do_it_yourself(registered)
        if cls:
            registerer = priority_registerer(self.registry, cls)
            cls = registerer.do_it_yourself(registered)
        return cls

class action_registerer(etype_rtype_registerer):
    """'all in one' actions registerer, handling optional .accepts,
    .etype and .rtype attributes:
    
    * if .etype is set and is not an entity type defined in the
      application schema, skip the wrapped class
    * if .rtype or .relname is set and is not a relation type defined in
      the application schema, skip the wrapped class
    * if .accepts is set, delegate to the accepts_registerer
    * register
    """
    def do_it_yourself(self, registered):
        cls = super(action_registerer, self).do_it_yourself(registered)
        if hasattr(cls, 'accepts'):
            registerer = accepts_registerer(self.registry, cls)
            cls = registerer.do_it_yourself(registered)
        return cls


class extresources_registerer(priority_registerer):
    """'registerer according to a .need_resources attributes which
    should list necessary resource identifiers for the wrapped object.
    If one of its resources is missing, don't register
    """
    def do_it_yourself(self, registered):
        if not hasattr(self.config, 'has_resource'):
            return
        for resourceid in self.vobject.need_resources:
            if not self.config.has_resource(resourceid):
                return
        return super(extresources_registerer, self).do_it_yourself(registered)
    

__all__ = [cls.__name__ for cls in globals().values()
           if isinstance(cls, type) and issubclass(cls, registerer)
           and not cls is registerer]
