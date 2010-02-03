The VRegistry
--------------

The recording process on startup
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Details of the recording process
````````````````````````````````

.. index::
   vregistry: registration_callback

On startup, |cubicweb| have to fill the vregistry with appobjects defined
in its library and in cubes used by the instance. Appobjects from the library
are loaded first, then appobjects provided by cubes are loaded in an ordered
way (e.g. if your cube depends on an other, appobjects from the dependancy will
be loaded first). Cube's modules or packages where appobject are looked at is explained
in :ref:`cubelayout`.

For each module:

* by default all objects are registered automatically

* if some objects have to replace other objects or be included only if a
  condition is true, you'll have to define a `registration_callback(vreg)`
  function in your module and explicitly register *all objects* in this
  module, using the vregistry api defined below.

.. note::
    Once the function `registration_callback(vreg)` is implemented, all the objects
    have to be explicitly registered as it disables the automatic object registering.


API d'enregistrement des objets
```````````````````````````````
.. automethod:: cubicweb.cwvreg.CubicWebVRegistry.register_all
.. automethod:: cubicweb.cwvreg.CubicWebVRegistry.register_and_replace
.. automethod:: cubicweb.cwvreg.CubicWebVRegistry.register
.. automethod:: cubicweb.cwvreg.CubicWebVRegistry.register_if_interface_found
.. automethod:: cubicweb.cwvreg.CubicWebVRegistry.unregister


Examples
````````
.. sourcecode:: python

   # web/views/basecomponents.py
   def registration_callback(vreg):
      # register everything in the module except SeeAlsoComponent
      vreg.register_all(globals().values(), __name__, (SeeAlsoVComponent,))
      # conditionally register SeeAlsoVComponent
      if 'see_also' in vreg.schema:
          vreg.register(SeeAlsoVComponent)

   # goa/appobjects/sessions.py
   def registration_callback(vreg):
      vreg.register(SessionsCleaner)
      # replace AuthenticationManager by GAEAuthenticationManager 
      vreg.register_and_replace(GAEAuthenticationManager, AuthenticationManager)
      # replace PersistentSessionManager by GAEPersistentSessionManager
      vreg.register_and_replace(GAEPersistentSessionManager, PersistentSessionManager)


Runtime objects selection
~~~~~~~~~~~~~~~~~~~~~~~~~

Using and combining existant selectors
``````````````````````````````````````

The object's selector is defined by its `__select__` class attribute.

When two selectors are combined using the `&` operator (formerly `chainall`), it
means that both should return a positive score. On success, the sum of scores is returned.

When two selectors are combined using the `|` operator (former `chainfirst`), it
means that one of them should return a positive score. On success, the first
positive score is returned.

You can also "negate"  a selector by precedeing it by the `~` operator.

Of course you can use paren to balance expressions.


For instance, if you are selecting the primary (eg `__regid__ = 'primary'`) view (eg
`__registry__ = 'view'`) for a result set containing a `Card` entity, 2 objects
will probably be selectable:

* the default primary view (`__select__ = implements('Any')`), meaning
  that the object is selectable for any kind of entity type

* the specific `Card` primary view (`__select__ = implements('Card')`,
  meaning that the object is selectable for Card entities

Other primary views specific to other entity types won't be selectable
in this case. Among selectable objects, the implements selector will
return a higher score than the second view since it's more specific,
so it will be selected as expected.


Example
````````

The goal: when on a Blog, one wants the RSS link to refer to blog
entries, not to the blog entity itself.

To do that, one defines a method on entity classes that returns the
RSS stream url for a given entity. The default implementation on
AnyEntity and a specific implementation on Blog will do what we want.

But when we have a result set containing several Blog entities (or
different entities), we don't know on which entity to call the
aforementioned method. In this case, we keep the current behaviour
(e.g : call to limited_rql).

Hence we have two cases here, one for a single-entity rsets, the other
for multi-entities rsets.

In web/views/boxes.py lies the RSSIconBox class. Look at its selector ::

  class RSSIconBox(ExtResourcesBoxTemplate):
    """just display the RSS icon on uniform result set"""
    __select__ = ExtResourcesBoxTemplate.__select__ & non_final_entity()

It takes into account:

* the inherited selection criteria (one has to look them up in the
  class hierarchy to know the details)

* non_final_entity, which filters on rsets containing non final
  entities (a 'final entity' being synonym for entity attribute)

This matches our second case. Hence we have to provide a specific
component for the first case::

  class EntityRSSIconBox(RSSIconBox):
    """just display the RSS icon on uniform result set for a single entity"""
    __select__ = RSSIconBox.__select__ & one_line_rset()

Here, one adds the one_line_rset selector, which filters result sets
of size 1. When one chains selectors, the final score is the sum of
the score of each individual selector (unless one of them returns 0,
in which case the object is non selectable). Thus, on a multiple
entities selector, one_line_rset makes the EntityRSSIconBox class non
selectable. For an rset with one entity, the EntityRSSIconBox class
will have a higher score then RSSIconBox, which is what we wanted.

Of course, once this is done, you have to:

* fill in the call method of EntityRSSIconBox

* provide the default implementation of the method returning the RSS
  stream url on AnyEntity

* redefine this method on Blog.

When to use selectors?
``````````````````````

Selectors are to be used whenever arises the need of dispatching on the shape or
content of a result set or whatever else context (value in request form params,
authenticated user groups, etc...). That is, almost all the time.

XXX add and example of a single view w/ big "if" inside splitted into two views
with appropriate selectors.


.. CustomSelectors_

Defining your own selectors
```````````````````````````
XXX objectify_selector, EntitySelector, EClassSelector...


Debugging
`````````

Once in a while, one needs to understand why a view (or any AppObject)
is, or is not selected appropriately. Looking at which selectors fired
(or did not) is the way. There exists a traced_selection context
manager to help with that.

Here is an example:

.. sourcecode:: python

     from cubicweb.selectors import traced_selection
     with traced_selection():
         mycomp = self._cw.vreg['views'].select('wfhistory', self._cw, rset=rset)

Don't forget the 'from __future__ import with_statement' at the module
top-level if you're using python 2.5.

This will yield additional WARNINGs in the logs, like this::

    2009-01-09 16:43:52 - (cubicweb.selectors) WARNING: selector one_line_rset returned 0 for <class 'cubicweb.web.views.basecomponents.WFHistoryVComponent'>

Take care not filtering-out messages whose log level is <= LOG_WARNING!

You can also give to traced_selection the registry ids of objects on which to debug
you want to debug selection ('wfhistory' in the example above).

Also, if you're using python 2.4, which as no 'with' yet, you'll have to to it
the following way:

.. sourcecode:: python

         from cubicweb import selectors
         selectors.TRACED_OIDS = ('wfhistory',)
         mycomp = self._cw.vreg['views'].select('wfhistory', self._cw, rset=rset)
         selectors.TRACED_OIDS = ()
