
.. _FetchAttrs:

Loaded attributes and default sorting management
````````````````````````````````````````````````

* The class attribute `fetch_attrs` allows to define in an entity class a list of
  names of attributes that should be automatically loaded when entities of this
  type are fetched from the database using ORM methods retrieving entity of this
  type (such as :meth:`related` and :meth:`unrelated`). You can also put relation
  names in there, but we are limited to *subject relations of cardinality `?` or
  `1`*.

* The :meth:`cw_fetch_order` and :meth:`cw_fetch_unrelated_order` class methods
  are respectively responsible to control how entities will be sorted when:

  - retrieving all entities of a given type, or entities related to another

  - retrieving a list of entities for use in drop-down lists enabling relations
    creation in the editing view of an entity

By default entities will be listed on their modification date descending,
i.e. you'll get entities recently modified first. While this is usually a good
default in drop-down list, you'll probably want to change `cw_fetch_order`.

This may easily be done using the :func:`~cubicweb.entities.fetch_config`
function, which simplifies the definition of attributes to load and sorting by
returning a list of attributes to pre-load (considering automatically the
attributes of `AnyEntity`) and a sorting function as described below:

.. autofunction:: cubicweb.entities.fetch_config

In you want something else (such as sorting on the result of a registered
procedure), here is the prototype of those methods:


.. automethod:: cubicweb.entity.Entity.cw_fetch_order

.. automethod:: cubicweb.entity.Entity.cw_fetch_unrelated_order

