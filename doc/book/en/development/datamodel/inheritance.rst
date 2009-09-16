
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


XXX WRITME
