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

.. autodocstring:: cubicweb.cwvreg 
   :noindex:
.. autodocstring:: cubicweb.predicates
   :noindex:
.. automodule:: cubicweb.appobject
   :noindex:

Base predicates
---------------

Predicates are scoring functions that are called by the registry to tell whenever
an appobject can be selected in a given context. Predicates may be chained
together using operators to build a selector. A selector is the glue that tie
views to the data model or whatever input context. Using them appropriately is an
essential part of the construction of well behaved cubes.

Of course you may have to write your own set of predicates as your needs grows
and you get familiar with the framework (see :ref:`CustomPredicates`).

Here is a description of generic predicates provided by CubicWeb that should suit
most of your needs.

Bare predicates
~~~~~~~~~~~~~~~

Those predicates are somewhat dumb, which doesn't mean they're not (very) useful.

.. autoclass:: cubicweb.appobject.yes
   :noindex:
.. autoclass:: cubicweb.predicates.match_kwargs
   :noindex:
.. autoclass:: cubicweb.predicates.appobject_selectable
   :noindex:
.. autoclass:: cubicweb.predicates.adaptable
   :noindex:
.. autoclass:: cubicweb.predicates.configuration_values
   :noindex:


Result set predicates
~~~~~~~~~~~~~~~~~~~~~

Those predicates are looking for a result set in the context ('rset' argument or
the input context) and match or not according to its shape. Some of these
predicates have different behaviour if a particular cell of the result set is
specified using 'row' and 'col' arguments of the input context or not.

.. autoclass:: cubicweb.predicates.none_rset
   :noindex:
.. autoclass:: cubicweb.predicates.any_rset
   :noindex:
.. autoclass:: cubicweb.predicates.nonempty_rset
   :noindex:
.. autoclass:: cubicweb.predicates.empty_rset
   :noindex:
.. autoclass:: cubicweb.predicates.one_line_rset
   :noindex:
.. autoclass:: cubicweb.predicates.multi_lines_rset
   :noindex:
.. autoclass:: cubicweb.predicates.multi_columns_rset
   :noindex:
.. autoclass:: cubicweb.predicates.paginated_rset
   :noindex:
.. autoclass:: cubicweb.predicates.sorted_rset
   :noindex:
.. autoclass:: cubicweb.predicates.one_etype_rset
   :noindex:
.. autoclass:: cubicweb.predicates.multi_etypes_rset
   :noindex:


Entity predicates
~~~~~~~~~~~~~~~~~

Those predicates are looking for either an `entity` argument in the input context,
or entity found in the result set ('rset' argument or the input context) and
match or not according to entity's (instance or class) properties.

.. autoclass:: cubicweb.predicates.non_final_entity
   :noindex:
.. autoclass:: cubicweb.predicates.is_instance
   :noindex:
.. autoclass:: cubicweb.predicates.score_entity
   :noindex:
.. autoclass:: cubicweb.predicates.rql_condition
   :noindex:
.. autoclass:: cubicweb.predicates.relation_possible
   :noindex:
.. autoclass:: cubicweb.predicates.partial_relation_possible
   :noindex:
.. autoclass:: cubicweb.predicates.has_related_entities
   :noindex:
.. autoclass:: cubicweb.predicates.partial_has_related_entities
   :noindex:
.. autoclass:: cubicweb.predicates.has_permission
   :noindex:
.. autoclass:: cubicweb.predicates.has_add_permission
   :noindex:
.. autoclass:: cubicweb.predicates.has_mimetype
   :noindex:
.. autoclass:: cubicweb.predicates.is_in_state
   :noindex:
.. autofunction:: cubicweb.predicates.on_fire_transition
   :noindex:


Logged user predicates
~~~~~~~~~~~~~~~~~~~~~~

Those predicates are looking for properties of the user issuing the request.

.. autoclass:: cubicweb.predicates.match_user_groups
   :noindex:


Web request predicates
~~~~~~~~~~~~~~~~~~~~~~

Those predicates are looking for properties of *web* request, they can not be
used on the data repository side.

.. autoclass:: cubicweb.predicates.no_cnx
   :noindex:
.. autoclass:: cubicweb.predicates.anonymous_user
   :noindex:
.. autoclass:: cubicweb.predicates.authenticated_user
   :noindex:
.. autoclass:: cubicweb.predicates.match_form_params
   :noindex:
.. autoclass:: cubicweb.predicates.match_search_state
   :noindex:
.. autoclass:: cubicweb.predicates.match_context_prop
   :noindex:
.. autoclass:: cubicweb.predicates.match_context
   :noindex:
.. autoclass:: cubicweb.predicates.match_view
   :noindex:
.. autoclass:: cubicweb.predicates.primary_view
   :noindex:
.. autoclass:: cubicweb.predicates.contextual
   :noindex:
.. autoclass:: cubicweb.predicates.specified_etype_implements
   :noindex:
.. autoclass:: cubicweb.predicates.attribute_edited
   :noindex:
.. autoclass:: cubicweb.predicates.match_transition
   :noindex:


Other predicates
~~~~~~~~~~~~~~~~
.. autoclass:: cubicweb.predicates.match_exception
   :noindex:
.. autoclass:: cubicweb.predicates.debug_mode
   :noindex:

You'll also find some other (very) specific predicates hidden in other modules
than :mod:`cubicweb.predicates`.
