Access to persistent data
--------------------------

Python-level access to persistent data is provided by the
:class:`Entity <cubicweb.entity>` class.

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

  * `printable_value(attr, value=_marker, attrtype=None, format='text/html')`,
    returns a string enabling the display of an attribute value in a given format
    (the value is automatically recovered if necessary)

:Data handling:

  * `as_rset()`, converts the entity into an equivalent result set simulating the
    ._cwuest `Any X WHERE X eid _eid_`

  * `complete(skip_bytes=True)`, executes a._cwuest that recovers all at once
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

  * `delete()` allows to delete the entity


The :class:`AnyEntity` class
----------------------------

To provide a specific behavior for each entity, we have to define a class
inheriting from `cubicweb.entities.AnyEntity`. In general, we define this class
in `mycube.entities` module (or in a submodule if we want to split code among
multiple files) so that it will be available on both server and client side.

The class `AnyEntity` is a sub-class of Entity that add methods to it,
and helps specializing (by further subclassing) the handling of a
given entity type.

The methods defined for `AnyEntity`, in addition to `Entity`, are the
following ones:

:Standard meta-data (Dublin Core):

  * `dc_title()`, returns a unicode string corresponding to the
    meta-data `Title` (used by default is the first non-meta attribute
    of the entity schema)

  * `dc_long_title()`, same as dc_title but can return a more
    detailed title

  * `dc_description(format='text/plain')`, returns a unicode string
    corresponding to the meta-data `Description` (looks for a
    description attribute by default)

  * `dc_authors()`, returns a unicode string corresponding to the meta-data
    `Authors` (owners by default)

  * `dc_date(date_format=None)`, returns a unicode string corresponding to
    the meta-data `Date` (update date by default)

  * `dc_type(form='')`, returns a string to display the entity type by
    specifying the preferred form (`plural` for a plural form)


Inheritance
-----------

When describing a data model, entities can inherit from other entities as is
common in object-oriented programming.

You have the possibility to adapt some entity attributes, as follow:

.. sourcecode:: python

    from cubes.OTHER_CUBE import entities
    class EntityExample(entities.EntityExample):
        def dc_long_title(self):
            return '%s (%s)' % (self.name, self.description)

Notice this is different than yams schema inheritance.

