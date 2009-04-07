"""This file contains some basic registerers required by application objects
registry to handle registration at startup time.

A registerer is responsible to tell if an object should be registered according
to the application's schema or to already registered object

:organization: Logilab
:copyright: 2006-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cubicweb.vregistry import registerer, yes_registerer
from cubicweb.cwvreg import use_interfaces

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
        # remove it later if no object is implementing accepted interfaces
        if use_interfaces(self.vobject):
            return self.vobject
        self.remove_equivalents(registered)
        return self.vobject
    
    def equivalent(self, other):
        if use_interfaces(self.vobject) != use_interfaces(other):
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


__all__ = [cls.__name__ for cls in globals().values()
           if isinstance(cls, type) and issubclass(cls, registerer)
           and not cls is registerer]
