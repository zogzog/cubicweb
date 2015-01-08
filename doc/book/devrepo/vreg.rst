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
.. autodocstring:: cubicweb.predicates
.. automodule:: cubicweb.appobject

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
.. autoclass:: cubicweb.predicates.match_kwargs
.. autoclass:: cubicweb.predicates.appobject_selectable
.. autoclass:: cubicweb.predicates.adaptable
.. autoclass:: cubicweb.predicates.configuration_values


Result set predicates
~~~~~~~~~~~~~~~~~~~~~
Those predicates are looking for a result set in the context ('rset' argument or
the input context) and match or not according to its shape. Some of these
predicates have different behaviour if a particular cell of the result set is
specified using 'row' and 'col' arguments of the input context or not.

.. autoclass:: cubicweb.predicates.none_rset
.. autoclass:: cubicweb.predicates.any_rset
.. autoclass:: cubicweb.predicates.nonempty_rset
.. autoclass:: cubicweb.predicates.empty_rset
.. autoclass:: cubicweb.predicates.one_line_rset
.. autoclass:: cubicweb.predicates.multi_lines_rset
.. autoclass:: cubicweb.predicates.multi_columns_rset
.. autoclass:: cubicweb.predicates.paginated_rset
.. autoclass:: cubicweb.predicates.sorted_rset
.. autoclass:: cubicweb.predicates.one_etype_rset
.. autoclass:: cubicweb.predicates.multi_etypes_rset


Entity predicates
~~~~~~~~~~~~~~~~~
Those predicates are looking for either an `entity` argument in the input context,
or entity found in the result set ('rset' argument or the input context) and
match or not according to entity's (instance or class) properties.

.. autoclass:: cubicweb.predicates.non_final_entity
.. autoclass:: cubicweb.predicates.is_instance
.. autoclass:: cubicweb.predicates.score_entity
.. autoclass:: cubicweb.predicates.rql_condition
.. autoclass:: cubicweb.predicates.relation_possible
.. autoclass:: cubicweb.predicates.partial_relation_possible
.. autoclass:: cubicweb.predicates.has_related_entities
.. autoclass:: cubicweb.predicates.partial_has_related_entities
.. autoclass:: cubicweb.predicates.has_permission
.. autoclass:: cubicweb.predicates.has_add_permission
.. autoclass:: cubicweb.predicates.has_mimetype
.. autoclass:: cubicweb.predicates.is_in_state
.. autofunction:: cubicweb.predicates.on_fire_transition


Logged user predicates
~~~~~~~~~~~~~~~~~~~~~~
Those predicates are looking for properties of the user issuing the request.

.. autoclass:: cubicweb.predicates.match_user_groups


Web request predicates
~~~~~~~~~~~~~~~~~~~~~~
Those predicates are looking for properties of *web* request, they can not be
used on the data repository side.

.. autoclass:: cubicweb.predicates.no_cnx
.. autoclass:: cubicweb.predicates.anonymous_user
.. autoclass:: cubicweb.predicates.authenticated_user
.. autoclass:: cubicweb.predicates.match_form_params
.. autoclass:: cubicweb.predicates.match_search_state
.. autoclass:: cubicweb.predicates.match_context_prop
.. autoclass:: cubicweb.predicates.match_context
.. autoclass:: cubicweb.predicates.match_view
.. autoclass:: cubicweb.predicates.primary_view
.. autoclass:: cubicweb.predicates.contextual
.. autoclass:: cubicweb.predicates.specified_etype_implements
.. autoclass:: cubicweb.predicates.attribute_edited
.. autoclass:: cubicweb.predicates.match_transition


Other predicates
~~~~~~~~~~~~~~~~
.. autoclass:: cubicweb.predicates.match_exception
.. autoclass:: cubicweb.predicates.debug_mode

You'll also find some other (very) specific predicates hidden in other modules
than :mod:`cubicweb.predicates`.
