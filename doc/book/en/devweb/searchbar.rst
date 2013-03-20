.. _searchbar:

RQL search bar
--------------

The RQL search bar is a visual component, hidden by default, the tiny *search*
input being enough for common use cases.

An autocompletion helper is provided to help you type valid queries, both
in terms of syntax and in terms of schema validity.

.. autoclass:: cubicweb.web.views.magicsearch.RQLSuggestionsBuilder


How search is performed
+++++++++++++++++++++++

You can use the *rql search bar* to either type RQL queries, plain text queries
or standard shortcuts such as *<EntityType>* or *<EntityType> <attrname> <value>*.

Ultimately, all queries are translated to rql since it's the only
language understood on the server (data) side. To transform the user
query into RQL, CubicWeb uses the so-called *magicsearch component*,
defined in :mod:`cubicweb.web.views.magicsearch`, which in turn
delegates to a number of query preprocessor that are responsible of
interpreting the user query and generating corresponding RQL.

The code of the main processor loop is easy to understand:

.. sourcecode:: python

  for proc in self.processors:
      try:
          return proc.process_query(uquery, req)
      except (RQLSyntaxError, BadRQLQuery):
          pass

The idea is simple: for each query processor, try to translate the
query. If it fails, try with the next processor, if it succeeds,
we're done and the RQL query will be executed.

