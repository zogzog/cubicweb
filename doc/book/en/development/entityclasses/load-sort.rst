
.. _FetchAttrs:

Loaded attributes and default sorting management
````````````````````````````````````````````````

* The class attribute `fetch_attrs` allows to define in an entity class a list
  of names of attributes or relations that should be automatically loaded when
  entities of this type are fetched from the database. In the case of relations,
  we are limited to *subject of cardinality `?` or `1`* relations.

* The class method `fetch_order(attr, var)` expects an attribute (or relation)
  name as a parameter and a variable name, and it should return a string
  to use in the requirement `ORDERBY` of an RQL query to automatically
  sort the list of entities of such type according to this attribute, or
  `None` if we do not want to sort on the attribute given in the parameter.
  By default, the entities are sorted according to their creation date.

* The class method `fetch_unrelated_order(attr, var)` is similar to
  the method `fetch_order` except that it is essentially used to
  control the sorting of drop-down lists enabling relations creation
  in the editing view of an entity. The default implementation uses
  the modification date. Here's how to adapt it for one entity (sort
  on the name attribute): ::

   class MyEntity(AnyEntity):
       fetch_attrs = ('modification_date', 'name')

       @classmethod
       def fetch_unrelated_order(cls, attr, var):
           if attr == 'name':
              return '%s ASC' % var
           return None


The function `fetch_config(fetchattrs, mainattr=None)` simplifies the
definition of the attributes to load and the sorting by returning a
list of attributes to pre-load (considering automatically the
attributes of `AnyEntity`) and a sorting function based on the main
attribute (the second parameter if specified, otherwise the first
attribute from the list `fetchattrs`). This function is defined in
`cubicweb.entities`.

For example: ::

  class Transition(AnyEntity):
    """..."""
    id = 'Transition'
    fetch_attrs, fetch_order = fetch_config(['name'])

Indicates that for the entity type "Transition", you have to pre-load
the attribute `name` and sort by default on this attribute.
