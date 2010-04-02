Base selectors
--------------

Selectors are scoring functions that are called by the registry to tell whenever
an appobject can be selected in a given context. Selector sets are for instance
the glue that tie views to the data model. Using them appropriately is an
essential part of the construction of well behaved cubes.

Of course you may have to write your own set of selectors as your needs grows and
you get familiar with the framework (see :ref:`CustomSelectors`).

Here is a description of generic selectors provided by CubicWeb that should suit
most of your needs.

Bare selectors
~~~~~~~~~~~~~~
Those selectors are somewhat dumb, which doesn't mean they're not (very) useful.

.. autoclass:: cubicweb.appobject.yes
.. autoclass:: cubicweb.selectors.match_kwargs
.. autoclass:: cubicweb.selectors.appobject_selectable


Result set selectors
~~~~~~~~~~~~~~~~~~~~~
Those selectors are looking for a result set in the context ('rset' argument or
the input context) and match or not according to its shape. Some of these
selectors have different behaviour if a particular cell of the result set is
specified using 'row' and 'col' arguments of the input context or not.

.. autoclass:: cubicweb.selectors.none_rset
.. autoclass:: cubicweb.selectors.any_rset
.. autoclass:: cubicweb.selectors.nonempty_rset
.. autoclass:: cubicweb.selectors.empty_rset
.. autoclass:: cubicweb.selectors.one_line_rset
.. autoclass:: cubicweb.selectors.multi_lines_rset
.. autoclass:: cubicweb.selectors.multi_columns_rset
.. autoclass:: cubicweb.selectors.paginated_rset
.. autoclass:: cubicweb.selectors.sorted_rset
.. autoclass:: cubicweb.selectors.one_etype_rset
.. autoclass:: cubicweb.selectors.multi_etypes_rset


Entity selectors
~~~~~~~~~~~~~~~~
Those selectors are looking for either an `entity` argument in the input context,
or entity found in the result set ('rset' argument or the input context) and
match or not according to entity's (instance or class) properties.

.. autoclass:: cubicweb.selectors.non_final_entity
.. autoclass:: cubicweb.selectors.implements
.. autoclass:: cubicweb.selectors.score_entity
.. autoclass:: cubicweb.selectors.rql_condition
.. autoclass:: cubicweb.selectors.relation_possible
.. autoclass:: cubicweb.selectors.partial_relation_possible
.. autoclass:: cubicweb.selectors.has_related_entities
.. autoclass:: cubicweb.selectors.partial_has_related_entities
.. autoclass:: cubicweb.selectors.has_permission
.. autoclass:: cubicweb.selectors.has_add_permission


Logged user selectors
~~~~~~~~~~~~~~~~~~~~~
Those selectors are looking for properties of the user issuing the request.

.. autoclass:: cubicweb.selectors.anonymous_user
.. autoclass:: cubicweb.selectors.authenticated_user
.. autoclass:: cubicweb.selectors.match_user_groups


Web request selectors
~~~~~~~~~~~~~~~~~~~~~
Those selectors are looking for properties of *web* request, they can not be
used on the data repository side.

.. autoclass:: cubicweb.selectors.match_form_params
.. autoclass:: cubicweb.selectors.match_search_state
.. autoclass:: cubicweb.selectors.match_context_prop
.. autoclass:: cubicweb.selectors.match_view
.. autoclass:: cubicweb.selectors.primary_view
.. autoclass:: cubicweb.selectors.specified_etype_implements


Other selectors
~~~~~~~~~~~~~~~
.. autoclass:: cubicweb.selectors.match_transition

You'll also find some other (very) specific selectors hidden in other modules
than :mod:`cubicweb.selectors`.
