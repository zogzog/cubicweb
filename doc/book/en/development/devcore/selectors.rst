Base selectors
--------------

Selectors are scoring functions that are called by the view dispatcher to tell
whenever a view can be applied to a given result set of a._cwuest. Selector sets
are the glue that tie views to the data model. Using them appropriately is an
essential part of the construction of well behaved cubes.


*CubicWeb* provides its own set of selectors that you can use and here is a
description of some of the most common used:

Of course you will write your own set of selectors as you get familiar with the
framework.


:yes([score=1]):
  Return the score given as parameter (default to 1). Usually used for appobjects
  which can be selected whatever the context, or also sometimes to add arbitrary
  points to a score. Take care, `yes(0)` could be named 'no'...


Rset selectors
~~~~~~~~~~~~~~
:none_rset():
  Return 1 if the result set is None.

:any_rset():
  Return 1 for any result set, whatever the number of rows in it.

:nonempty_rset():
  Return 1 for non empty result set.

:empty_rset():
  Return 1 for empty result set.

:one_line_rset():
  Return 1 if the result set is of size 1 or if a row is specified.

:two_lines_rset():
  Return 1 if the result set has *at least* two rows.

:two_cols_rset():
  Return 1 if the result set is not empty and has *at least* two columns per
  row.

:paginated_rset():
  Return 1 if the result set has more rows the specified by the
  `navigation.page-size` property.

:sorted_rset():
  Return 1 if the result set has an ORDERBY clause.

:one_etype_rset():
  Return 1 if the result set has entities which are all of the same type in a
  given column (default to column 0).

:non_final_entity():
  Return 1 if the result set contains entities in a given column (the first one
  by default), and no "final" values such as string of int.

:implements(<iface or etype>, ...):
  Return positive score if entities in the result set are of the given entity
  type or implements given interface.  If multiple arguments are given, matching
  one of them is enough. Returned score reflects the "distance" between expected
  type or interface and matched entities. Entity types are usually given as
  string, the corresponding class will be fetched from the vregistry.

:two_etypes_rset(): XXX
:entity_implements(): XXX
:relation_possible(): XXX
:partial_relation_possible(): XXX
:may_add_relation(): XXX
:partial_may_add_relation(): XXX
:has_related_entities(): XXX
:partial_has_related_entities(): XXX
:has_permission(): XXX
:has_add_permission(): XXX
:rql_condition(): XXX
:but_etype(): XXX
:score_entity(): XXX

Request selectors
~~~~~~~~~~~~~~~~~~
:anonymous_user():
  Return 1 if user isn't authenticated (eg is the anonymous user).

:authenticated_user():
  Return 1 if user is authenticated.

:match_user_groups(): XXX
:match_search_state(): XXX
:match_form_params(): XXX

Other selectors
~~~~~~~~~~~~~~~
:match_kwargs(): XXX
:match_context_prop(): XXX
:appobject_selectable(): XXX
:specified_etype_implements(): XXX
:primary_view(): XXX