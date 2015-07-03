The Registry, selectors and application objects
===============================================

This chapter deals with some of the  core concepts of the |cubicweb| framework
which make it different from other frameworks (and maybe not easy to
grasp at a first glance). To be able to do advanced development with
|cubicweb| you need a good understanding of what is explained below.

This chapter goes deep into details. You don't have to remember them
all but keep it in mind so you can go back there later.

An overview of AppObjects, the VRegistry and Selectors is given in the
:ref:`VRegistryIntro` chapter.



The :class:`CWRegistryStore`
----------------------------

The :class:`CWRegistryStore <cubicweb.cwvreg.CWRegistryStore>` can be
seen as a two-level dictionary. It contains all dynamically loaded
objects (subclasses of :class:`AppObject <cubicweb.appobject.AppObject>`)
to build a |cubicweb| application. Basically:

* the first level key returns a *registry*. This key corresponds to the
  `__registry__` attribute of application object classes

* the second level key returns a list of application objects which
  share the same identifier. This key corresponds to the `__regid__`
  attribute of application object classes.

A *registry* holds a specific kind of application objects. There is
for instance a registry for entity classes, another for views, etc...

The :class:`CWRegistryStore <cubicweb.cwvreg.CWRegistryStore>` has two
main responsibilities:

- being the access point to all registries

- handling the registration process at startup time, and during automatic
  reloading in debug mode.


Details of the recording process
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. index::
   vregistry: registration_callback

On startup, |cubicweb| loads application objects defined in its library
and in cubes used by the instance. Application objects from the
library are loaded first, then those provided by cubes are loaded in
dependency order (e.g. if your cube depends on an other, objects from
the dependency will be loaded first). The layout of the modules or packages
in a cube  is explained in :ref:`cubelayout`.

For each module:

* by default all objects are registered automatically

* if some objects have to replace other objects, or have to be
  included only if some condition is met, you'll have to define a
  `registration_callback(vreg)` function in your module and explicitly
  register **all objects** in this module, using the api defined
  below.

.. Note::
    Once the function `registration_callback(vreg)` is implemented in a module,
    all the objects from this module have to be explicitly registered as it
    disables the automatic objects registration.


API for objects registration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here are the registration methods that you can use in the
`registration_callback` to register your objects to the
:class:`CWRegistryStore` instance given as argument (usually named
`vreg`):

- :py:meth:`register_all() <cubicweb.cwvreg.CWRegistryStore.register_all>`
- :py:meth:`register_and_replace() <cubicweb.cwvreg.CWRegistryStore.register_and_replace>`
- :py:meth:`register() <cubicweb.cwvreg.CWRegistryStore.register>`
- :py:meth:`unregister() <logilab.common.registry.RegistryStore.unregister>`

Examples:

.. sourcecode:: python

   # web/views/basecomponents.py
   def registration_callback(vreg):
      # register everything in the module except SeeAlsoComponent
      vreg.register_all(globals().itervalues(), __name__, (SeeAlsoVComponent,))
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



Runtime objects selection
~~~~~~~~~~~~~~~~~~~~~~~~~

Now that we have all application objects loaded, the question is : when
I want some specific object, for instance the primary view for a given
entity, how do I get the proper object ? This is what we call the
**selection mechanism**.

As explained in the :ref:`Concepts` section:

* each application object has a **selector**, defined by its
  `__select__` class attribute

* this selector is responsible to return a **score** for a given context

  - 0 score means the object doesn't apply to this context

  - else, the higher the score, the better the object suits the context

* the object with the highest score is selected.

.. Note::

  When no single object has the highest score, an exception is raised in development
  mode to let you know that the engine was not able to identify the view to
  apply. This error is silenced in production mode and one of the objects with
  the highest score is picked.

  In such cases you would need to review your design and make sure
  your selectors or appobjects are properly defined. Such an error is
  typically caused by either forgetting to change the __regid__ in a
  derived class, or by having copy-pasted some code.

For instance, if you are selecting the primary (`__regid__ =
'primary'`) view (`__registry__ = 'views'`) for a result set
containing a `Card` entity, two objects will probably be selectable:

* the default primary view (`__select__ = is_instance('Any')`), meaning
  that the object is selectable for any kind of entity type

* the specific `Card` primary view (`__select__ = is_instance('Card')`,
  meaning that the object is selectable for Card entities

Other primary views specific to other entity types won't be selectable in this
case. Among selectable objects, the `is_instance('Card')` selector will return a higher
score since it's more specific, so the correct view will be selected as expected.


API for objects selections
~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is the selection API you'll get on every registry. Some of them, as the
'etypes' registry, containing entity classes, extend it. In those methods,
`*args, **kwargs` is what we call the **context**. Those arguments are given to
selectors that will inspect their content and return a score accordingly.

:py:meth:`select() <logilab.common.registry.Registry.select>`

:py:meth:`select_or_none() <logilab.common.registry.Registry.select_or_none>`

:py:meth:`possible_objects() <logilab.common.registry.Registry.possible_objects>`

:py:meth:`object_by_id() <logilab.common.registry.Registry.object_by_id>`


The `AppObject` class
---------------------

The :py:class:`cubicweb.appobject.AppObject` class is the base class
for all dynamically loaded objects (application objects) accessible
through the :py:class:`cubicweb.cwvreg.CWRegistryStore`.


Predicates and selectors
------------------------

Predicates are scoring functions that are called by the registry to tell whenever
an appobject can be selected in a given context. Predicates may be chained
together using operators to build a selector. A selector is the glue that tie
views to the data model or whatever input context. Using them appropriately is an
essential part of the construction of well behaved cubes.

Of course you may have to write your own set of predicates as your needs grows
and you get familiar with the framework (see :ref:`CustomPredicates`).

A predicate is a class testing a particular aspect of a context. A selector is
built by combining existant predicates or even selectors.

Using and combining existant predicates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can combine predicates using the `&`, `|` and `~` operators.

When two predicates are combined using the `&` operator, it means that
both should return a positive score. On success, the sum of scores is
returned.

When two predicates are combined using the `|` operator, it means that
one of them should return a positive score. On success, the first
positive score is returned.

You can also "negate" a predicate by precedeing it by the `~` unary operator.

Of course you can use parenthesis to balance expressions.

Example
~~~~~~~

The goal: when on a blog, one wants the RSS link to refer to blog entries, not to
the blog entity itself.

To do that, one defines a method on entity classes that returns the
RSS stream url for a given entity. The default implementation on
:class:`~cubicweb.entities.AnyEntity` (the generic entity class used
as base for all others) and a specific implementation on `Blog` will
do what we want.

But when we have a result set containing several `Blog` entities (or
different entities), we don't know on which entity to call the
aforementioned method. In this case, we keep the generic behaviour.

Hence we have two cases here, one for a single-entity rsets, the other for
multi-entities rsets.

In web/views/boxes.py lies the RSSIconBox class. Look at its selector:

.. sourcecode:: python

  class RSSIconBox(box.Box):
    ''' just display the RSS icon on uniform result set '''
    __select__ = box.Box.__select__ & non_final_entity()

It takes into account:

* the inherited selection criteria (one has to look them up in the class
  hierarchy to know the details)

* :class:`~cubicweb.predicates.non_final_entity`, which filters on result sets
  containing non final entities (a 'final entity' being synonym for entity
  attributes type, eg `String`, `Int`, etc)

This matches our second case. Hence we have to provide a specific component for
the first case:

.. sourcecode:: python

  class EntityRSSIconBox(RSSIconBox):
    '''just display the RSS icon on uniform result set for a single entity'''
    __select__ = RSSIconBox.__select__ & one_line_rset()

Here, one adds the :class:`~cubicweb.predicates.one_line_rset` predicate, which
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

Here is a quick example:

.. sourcecode:: python

    class UserLink(component.Component):
	'''if the user is the anonymous user, build a link to login else a link
	to the connected user object with a logout link
	'''
	__regid__ = 'loggeduserlink'

	def call(self):
	    if self._cw.session.anonymous_session:
		# display login link
		...
	    else:
		# display a link to the connected user object with a loggout link
		...

The proper way to implement this with |cubicweb| is two have two different
classes sharing the same identifier but with different selectors so you'll get
the correct one according to the context.

.. sourcecode:: python

    class UserLink(component.Component):
	'''display a link to the connected user object with a loggout link'''
	__regid__ = 'loggeduserlink'
	__select__ = component.Component.__select__ & authenticated_user()

	def call(self):
            # display useractions and siteactions
	    ...

    class AnonUserLink(component.Component):
	'''build a link to login'''
	__regid__ = 'loggeduserlink'
	__select__ = component.Component.__select__ & anonymous_user()

	def call(self):
	    # display login link
            ...

The big advantage, aside readability once you're familiar with the
system, is that your cube becomes much more easily customizable by
improving componentization.


.. _CustomPredicates:

Defining your own predicates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can use the :py:func:`objectify_predicate <logilab.common.registry.objectify_predicate>`
decorator to easily write your own predicates as simple python
functions.

In other cases, you can take a look at the following abstract base classes:

- :py:class:`ExpectedValuePredicate <cubicweb.predicates.ExpectedValuePredicate>`
- :py:class:`EClassPredicate <cubicweb.predicates.EClassPredicate>`
- :py:class:`EntityPredicate <cubicweb.predicates.EntityPredicate>`


.. _DebuggingSelectors:

Debugging selection
~~~~~~~~~~~~~~~~~~~

Once in a while, one needs to understand why a view (or any
application object) is, or is not selected appropriately. Looking at
which predicates fired (or did not) is the way. The
:class:`traced_selection <logilab.common.registry.traced_selection>`
context manager to help with that, *if you're running your instance in
debug mode*.


Base predicates
---------------

Here is a description of generic predicates provided by CubicWeb that should suit
most of your needs.

Bare predicates
~~~~~~~~~~~~~~~

Those predicates are somewhat dumb, which doesn't mean they're not (very) useful.

- :py:class:`yes <cubicweb.appobject.yes>`
- :py:class:`match_kwargs <cubicweb.predicates.match_kwargs>`
- :py:class:`appobject_selectable <cubicweb.predicates.appobject_selectable>`
- :py:class:`adaptable <cubicweb.predicates.adaptable>`
- :py:class:`configuration_values <cubicweb.predicates.configuration_values>`


Result set predicates
~~~~~~~~~~~~~~~~~~~~~

Those predicates are looking for a result set in the context ('rset' argument or
the input context) and match or not according to its shape. Some of these
predicates have different behaviour if a particular cell of the result set is
specified using 'row' and 'col' arguments of the input context or not.

- :py:class:`none_rset <cubicweb.predicates.none_rset>`
- :py:class:`any_rset <cubicweb.predicates.any_rset>`
- :py:class:`nonempty_rset <cubicweb.predicates.nonempty_rset>`
- :py:class:`empty_rset <cubicweb.predicates.empty_rset>`
- :py:class:`one_line_rset <cubicweb.predicates.one_line_rset>`
- :py:class:`multi_lines_rset <cubicweb.predicates.multi_lines_rset>`
- :py:class:`multi_columns_rset <cubicweb.predicates.multi_columns_rset>`
- :py:class:`paginated_rset <cubicweb.predicates.paginated_rset>`
- :py:class:`sorted_rset <cubicweb.predicates.sorted_rset>`
- :py:class:`one_etype_rset <cubicweb.predicates.one_etype_rset>`
- :py:class:`multi_etypes_rset <cubicweb.predicates.multi_etypes_rset>`


Entity predicates
~~~~~~~~~~~~~~~~~

Those predicates are looking for either an `entity` argument in the input context,
or entity found in the result set ('rset' argument or the input context) and
match or not according to entity's (instance or class) properties.

- :py:class:`non_final_entity <cubicweb.predicates.non_final_entity>`
- :py:class:`is_instance <cubicweb.predicates.is_instance>`
- :py:class:`score_entity <cubicweb.predicates.score_entity>`
- :py:class:`rql_condition <cubicweb.predicates.rql_condition>`
- :py:class:`relation_possible <cubicweb.predicates.relation_possible>`
- :py:class:`partial_relation_possible <cubicweb.predicates.partial_relation_possible>`
- :py:class:`has_related_entities <cubicweb.predicates.has_related_entities>`
- :py:class:`partial_has_related_entities <cubicweb.predicates.partial_has_related_entities>`
- :py:class:`has_permission <cubicweb.predicates.has_permission>`
- :py:class:`has_add_permission <cubicweb.predicates.has_add_permission>`
- :py:class:`has_mimetype <cubicweb.predicates.has_mimetype>`
- :py:class:`is_in_state <cubicweb.predicates.is_in_state>`
- :py:func:`on_fire_transition <cubicweb.predicates.on_fire_transition>`


Logged user predicates
~~~~~~~~~~~~~~~~~~~~~~

Those predicates are looking for properties of the user issuing the request.

- :py:class:`match_user_groups <cubicweb.predicates.match_user_groups>`


Web request predicates
~~~~~~~~~~~~~~~~~~~~~~

Those predicates are looking for properties of *web* request, they can not be
used on the data repository side.

- :py:class:`no_cnx <cubicweb.predicates.no_cnx>`
- :py:class:`anonymous_user <cubicweb.predicates.anonymous_user>`
- :py:class:`authenticated_user <cubicweb.predicates.authenticated_user>`
- :py:class:`match_form_params <cubicweb.predicates.match_form_params>`
- :py:class:`match_search_state <cubicweb.predicates.match_search_state>`
- :py:class:`match_context_prop <cubicweb.predicates.match_context_prop>`
- :py:class:`match_context <cubicweb.predicates.match_context>`
- :py:class:`match_view <cubicweb.predicates.match_view>`
- :py:class:`primary_view <cubicweb.predicates.primary_view>`
- :py:class:`contextual <cubicweb.predicates.contextual>`
- :py:class:`specified_etype_implements <cubicweb.predicates.specified_etype_implements>`
- :py:class:`attribute_edited <cubicweb.predicates.attribute_edited>`
- :py:class:`match_transition <cubicweb.predicates.match_transition>`


Other predicates
~~~~~~~~~~~~~~~~

- :py:class:`match_exception <cubicweb.predicates.match_exception>`
- :py:class:`debug_mode <cubicweb.predicates.debug_mode>`

You'll also find some other (very) specific predicates hidden in other modules
than :mod:`cubicweb.predicates`.
