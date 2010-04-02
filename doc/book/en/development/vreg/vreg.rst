.. VRegistry:

The `VRegistry`
---------------

The `VRegistry` can be seen as a two level dictionary. It contains all objects
loaded dynamically to build a |cubicweb| application. Basically:

* first level key return a *registry*. This key corresponds to the `__registry__`
  attribute of application object classes

* second level key return a list of application objects which share the same
  identifier. This key corresponds to the `__regid__` attribute of application
  object classes.

A *registry* hold a specific kind of application objects. You've for instance
a registry for entity classes, another for views, etc...

The `VRegistry` has two main responsibilities:

- being the access point to all registries

- handling the registration process at startup time, and during automatic
  reloading in debug mode.


.. _AppObjectRecording:

Managing the recording process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Details of the recording process
````````````````````````````````

.. index::
   vregistry: registration_callback

On startup, |cubicweb| have to load application objects defined in its library
and in cubes used by the instance. Application objects from the library are
loaded first, then those provided by cubes are loaded in an ordered way (e.g. if
your cube depends on an other, objects from the dependancy will be loaded
first). Cube's modules or packages where appobject are looked at is explained in
:ref:`cubelayout`.

For each module:

* by default all objects are registered automatically

* if some objects have to replace other objects, or be included only if some
  condition is true, you'll have to define a `registration_callback(vreg)`
  function in your module and explicitly register **all objects** in this module,
  using the api defined below.

.. Note::
    Once the function `registration_callback(vreg)` is implemented in a module,
    all the objects from this module have to be explicitly registered as it
    disables the automatic objects registration.


API for objects registration
````````````````````````````

Here are the registration methods that you can use in the `registration_callback`
to register your objects to the `VRegistry` instance given as argument (usually
named `vreg`):

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

In this example, we register all application object classes defined in the module
except `SeeAlsoVComponent`. This class is then registered only if the 'see_also'
relation type is defined in the instance'schema.

.. sourcecode:: python

   # goa/appobjects/sessions.py
   def registration_callback(vreg):
      vreg.register(SessionsCleaner)
      # replace AuthenticationManager by GAEAuthenticationManager
      vreg.register_and_replace(GAEAuthenticationManager, AuthenticationManager)
      # replace PersistentSessionManager by GAEPersistentSessionManager
      vreg.register_and_replace(GAEPersistentSessionManager, PersistentSessionManager)

In this example, we explicitly register classes one by one:

* the `SessionCleaner` class
* the `GAEAuthenticationManager` to replace the `AuthenticationManager`
* the `GAEPersistentSessionManager` to replace the `PersistentSessionManager`

If at some point we register a new appobject class in this module, it won't be
registered at all without modification to the `registration_callback`
implementation. The previous example will register it though, thanks to the call
to the `register_all` method.

.. _Selection:

Runtime objects selection
~~~~~~~~~~~~~~~~~~~~~~~~~

Now that we've all application objects loaded, the question is : when I want some
specific object, for instance the primary view for a given entity, how do I get
the proper object ? This is what we call the **selection mechanism**.

As explained in the :ref:`Concepts` section:

* each application object has a **selector**, defined by its `__select__` class attribute

* this selector is responsible to return a **score** for a given context

  - 0 score means the object doesn't apply to this context

  - else, the higher the score, the better the object suits the context

* the object with the higher score is selected.

.. Note::

  When no score is higher than the others, an exception is raised in development
  mode to let you know that the engine was not able to identify the view to
  apply. This error is silenced in production mode and one of the objects with
  the higher score is picked.

  In such cases you would need to review your design and make sure your selectors
  or appobjects are properly defined.

For instance, if you are selecting the primary (eg `__regid__ = 'primary'`) view (eg
`__registry__ = 'views'`) for a result set containing a `Card` entity, 2 objects
will probably be selectable:

* the default primary view (`__select__ = implements('Any')`), meaning
  that the object is selectable for any kind of entity type

* the specific `Card` primary view (`__select__ = implements('Card')`,
  meaning that the object is selectable for Card entities

Other primary views specific to other entity types won't be selectable in this
case. Among selectable objects, the implements selector will return a higher
score than the second view since it's more specific, so it will be selected as
expected.

.. _SelectionAPI:

API for objects selections
``````````````````````````

Here is the selection API you'll get on every registry. Some of them, as the
'etypes' registry, containing entity classes, extend it. In those methods,
`*args, **kwargs` is what we call the **context**. Those arguments are given to
selectors that will inspect there content and return a score accordingly.

.. automethod:: cubicweb.vregistry.Registry.select

.. automethod:: cubicweb.vregistry.Registry.select_or_none

.. automethod:: cubicweb.vregistry.Registry.possible_objects

.. automethod:: cubicweb.vregistry.Registry.object_by_id


.. _Selectors:

Selectors
---------

Using and combining existant selectors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can combine selectors using the `&`, `|` and `~` operators.

When two selectors are combined using the `&` operator (formerly `chainall`), it
means that both should return a positive score. On success, the sum of scores is returned.

When two selectors are combined using the `|` operator (former `chainfirst`), it
means that one of them should return a positive score. On success, the first
positive score is returned.

You can also "negate" a selector by precedeing it by the `~` unary operator.

Of course you can use parens to balance expressions.

.. Note:
  When one chains selectors, the final score is the sum of the score of each
  individual selector (unless one of them returns 0, in which case the object is
  non selectable)


Example
~~~~~~~

The goal: when on a Blog, one wants the RSS link to refer to blog entries, not to
the blog entity itself.

To do that, one defines a method on entity classes that returns the RSS stream
url for a given entity. The default implementation on
:class:`~cubicweb.entities.AnyEntity` (the generic entity class used as base for
all others) and a specific implementation on Blog will do what we want.

But when we have a result set containing several Blog entities (or different
entities), we don't know on which entity to call the aforementioned method. In
this case, we keep the generic behaviour.

Hence we have two cases here, one for a single-entity rsets, the other for
multi-entities rsets.

In web/views/boxes.py lies the RSSIconBox class. Look at its selector ::

  class RSSIconBox(ExtResourcesBoxTemplate):
    """just display the RSS icon on uniform result set"""
    __select__ = ExtResourcesBoxTemplate.__select__ & non_final_entity()

It takes into account:

* the inherited selection criteria (one has to look them up in the class
  hierarchy to know the details)

* :class:`~cubicweb.selectors.non_final_entity`, which filters on result sets
  containing non final entities (a 'final entity' being synonym for entity
  attributes type, eg `String`, `Int`, etc)

This matches our second case. Hence we have to provide a specific component for
the first case::

  class EntityRSSIconBox(RSSIconBox):
    """just display the RSS icon on uniform result set for a single entity"""
    __select__ = RSSIconBox.__select__ & one_line_rset()

Here, one adds the :class:`~cubicweb.selectors.one_line_rset` selector, which
filters result sets of size 1. Thus, on a result set containing multiple
entities, :class:`one_line_rset` makes the EntityRSSIconBox class non
selectable. However for a result set with one entity, the `EntityRSSIconBox`
class will have a higher score than `RSSIconBox`, which is what we wanted.

Of course, once this is done, you have to:

* fill in the call method of `EntityRSSIconBox`

* provide the default implementation of the method returning the RSS stream url
  on :class:`~cubicweb.entities.AnyEntity`

* redefine this method on `Blog`.


When to use selectors?
~~~~~~~~~~~~~~~~~~~~~~

Selectors are to be used whenever arises the need of dispatching on the shape or
content of a result set or whatever else context (value in request form params,
authenticated user groups, etc...). That is, almost all the time.

.. XXX add and example of a single view w/ big "if" inside splitted into two views with appropriate selectors.


.. _CustomSelectors:

Defining your own selectors
~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. autoclass:: cubicweb.appobject.Selector
   :members: __call__

.. autofunction:: cubicweb.appobject.objectify_selector

Selectors __call__ should *always* return a positive integer, and shall never
return `None`.

Useful abstract base classes for 'entity' selectors:

.. autoclass:: cubicweb.selectors.EClassSelector
.. autoclass:: cubicweb.selectors.EntitySelector

Also, think to use the `lltrace` decorator on your selector class' :meth:`__call__` method
or below the :func:`objectify_selector` decorator of your selector function so it gets
traceable when :class:`traced_selection` is activated (see :ref:DebuggingSelectors).

.. autofunction:: cubicweb.selectors.lltrace


.. _DebuggingSelectors:

Debugging selection
~~~~~~~~~~~~~~~~~~~

Once in a while, one needs to understand why a view (or any AppObject) is, or is
not selected appropriately. Looking at which selectors fired (or did not) is the
way. There exists a traced_selection context manager to help with that, *if
you're running your instance in debug mode*.

Here is an example:

.. sourcecode:: python

     from cubicweb.selectors import traced_selection
     with traced_selection():
         mycomp = self._cw.vreg['views'].select('wfhistory', self._cw, rset=rset)

Don't forget the 'from __future__ import with_statement' at the module
top-level if you're using python 2.5.

This will yield additional WARNINGs in the logs, like this::

    2009-01-09 16:43:52 - (cubicweb.selectors) WARNING: selector one_line_rset returned 0 for <class 'cubicweb.web.views.basecomponents.WFHistoryVComponent'>

You can also give to traced_selection the registry ids of objects on which to debug
you want to debug selection ('wfhistory' in the example above).



.. |cubicweb| replace:: *CubicWeb*
