Access to persistent data
--------------------------

XXX is provided by the :class:`Entity <cubicweb.entity.entity>` class

An entity class is bound to a schema entity type.  Descriptors are added when
classes are registered in order to initialize the class according to its schema:

* we can access the defined attributes in the schema thanks to the attributes of
  the same name on instances (typed value)

* we can access the defined relations in the schema thanks to the relations of
  the same name on instances (entities instances list)


:Formatting and output generation:

  * `view(vid, **kwargs)`, applies the given view to the entity

  * `absolute_url(**kwargs)`, returns an absolute URL to access the primary view
    of an entity

  * `rest_path()`, returns a relative REST URL to get the entity

  * `format(attr)`, returns the format (MIME type) of the field given un parameter

  * `printable_value(attr, value=_marker, attrtype=None, format='text/html')`,
    returns a string enabling the display of an attribute value in a given format
    (the value is automatically recovered if necessary)

:Data handling:

  * `as_rset()`, converts the entity into an equivalent result set simulating the
     request `Any X WHERE X eid _eid_`

  * `complete(skip_bytes=True)`, executes a request that recovers in one time
    all the missing attributes of an entity

  * `get_value(name)`, returns the value associated to the attribute name given
    in parameter

  * `related(rtype, x='subject', limit=None, entities=False)`, returns a list
    of entities related to the current entity by the relation given in parameter

  * `unrelated(rtype, targettype, x='subject', limit=None)`, returns a result set
    corresponding to the entities not related to the current entity by the
    relation given in parameter and satisfying its constraints

  * `set_attributes(**kwargs)`, updates the attributes list with the corresponding
    values given named parameters

  * `copy_relations(ceid)`, copies the relations of the entities having the eid
    given in the parameters on the current entity

  * `last_modified(view)`, returns the date the object has been modified
    (used by HTTP cache handling)

  * `delete()` allows to delete the entity


Tne :class:`AnyEntity` class
----------------------------

To provide a specific behavior for each entity, we have to define
a class inheriting from `cubicweb.entities.AnyEntity`. In general, we
define this class in a module of `mycube.entities` package of an application
so that it will be available on both server and client side.

The class `AnyEntity` is loaded dynamically from the class `Entity`
(`cubciweb.entity`). We define a sub-class to add methods or to
specialize the handling of a given entity type

The methods defined for `AnyEntity` or `Entity` are the following ones:

:Standard meta-data (Dublin Core):

  * `dc_title()`, returns a unicode string corresponding to the meta-data
    `Title` (used by default the first attribute non-meta of the entity
    schema)

  * `dc_long_title()`, same as dc_title but can return a more
    detailled title

  * `dc_description(format='text/plain')`, returns a unicode string
    corresponding to the meta-data `Description` (look for a description
    attribute by default)

  * `dc_authors()`, returns a unicode string corresponding to the meta-data
    `Authors` (owners by default)

  * `dc_date(date_format=None)`, returns a unicode string corresponding to
    the meta-data `Date` (update date by default)

  * `dc_type(form='')`, returns a string to display the entity type by
    specifying the preferred form (`plural` for a plural form)
