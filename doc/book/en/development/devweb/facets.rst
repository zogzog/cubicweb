The facets system
-----------------
XXX feed me more (below is the extracted of adim blog)


Recently, for internal purposes, we've made a little cubicweb application to
help us
organizing visits to find new office locations. Here's an *excerpt* of the
schema:

.. sourcecode:: python

  class Office(WorkflowableEntityType):
      price = Int(description='euros / m2 / HC / HT')
      surface = Int(description='m2')
      description = RichString(fulltextindexed=True)
      has_address = SubjectRelation('PostalAddress', cardinality='1?', composite='subject')
      proposed_by = SubjectRelation('Agency')
      comments = ObjectRelation('Comment', cardinality='1*', composite='object')
      screenshots = SubjectRelation(('File', 'Image'), cardinality='*1',
                                    composite='subject')

The two other entity types defined in the schema are `Visit` and `Agency` but we
can also guess from the above that this application uses the two cubes
`comment`_ and
`addressbook`_ (remember, cubicweb is only a game where you assemble cubes !). 

While we know that just defining the schema in enough to have a full, usable,
(testable !) application, we also know that every application needs to be 
customized to fulfill the needs it was built for. So in this case, what we
needed most was some custom filters that would let us restrict searches
according
to surfaces, prices or zipcodes. Fortunately for us, Cubicweb provides the
**facets** (image_) mechanism and a few base classes that make the task quite
easy:

.. sourcecode:: python

  class PostalCodeFacet(RelationFacet): 
      id = 'postalcode-facet'             # every registered class must have an id
      __select__ = implements('Office')   # this facet should only be selected when 
                                          # visualizing offices
      rtype = 'has_address'               # this facet is a filter on the entity linked to
                                          # the office thrhough the relation
                                          # has_address
      target_attr = 'postalcode'          # the filter's key is the attribute "postal_code"
                                          # of the target PostalAddress entity

This is a typical `RelationFacet`: we want to be able to filter offices
according
to the attribute `postalcode` of their associated `PostalAdress`. Each line in
the class is explained by the comment on its right.

Now, here is the code to define a filter based on the `surface` attribute of the
`Office`:

.. sourcecode:: python

  class SurfaceFacet(AttributeFacet):
      id = 'surface-facet'              # every registered class must have an id
      __select__ = implements('Office') # this facet should only be selected when 
                                        # visualizing offices
      rtype = 'surface'                 # the filter's key is the attribute "surface" 
      comparator = '>='                 # override the default value of operator since 
                                        # we want to filter according to a
                                        # minimal 
                                        # value, not an exact one

      def rset_vocabulary(self, ___):
          """override the default vocabulary method since we want to hard-code
          our threshold values. 
          Not overriding would generate a filter box with all existing surfaces
          defined in the database.
          """
          return [('> 200', '200'), ('> 250', '250'),
                  ('> 275', '275'), ('> 300', '300')]


And that's it: we have two filter boxes automatically displayed on each page
presenting more than one office. The `price` facet is basically the same as the
`surface` one but with a different vocabulary and with ``rtype = 'price'``.

(The cube also benefits from the builtin google map views defined by
cubicweb but that's for another blog).

.. _image: http://www.cubicweb.org/image/197646?vid=download
.. _comment: http://www.cubicweb.org/project/cubicweb-comment
.. _addressbook: http://www.cubicweb.org/project/cubicweb-addressbook

CubicWeb has this really nice builtin `facet`_ system to
define restrictions `filters`_ really as easily as possible.

We've just added two new kind of facets in CubicWeb :

- The **RangeFacet** which displays a slider using `jquery`_
  to choose a lower bound and an upper bound. The **RangeWidget** 
  works with either numerical values or date values

- The **HasRelationFacet** which displays a simple checkbox and
  lets you refine your selection in order to get only entities
  that actually use this relation.

.. image :: http://www.cubicweb.org/Image/343498?vid=download


Here's an example of code that defines a facet to filter 
musical works according to their composition date:

.. sourcecode:: python

    class CompositionDateFacet(DateRangeFacet):
        # 1. make sure this facet is displayed only on Track selection
        __select__ = DateRangeFacet.__select__ & implements('Track')
        # 2. give the facet an id ._cwuired by CubicWeb)
        id = 'compdate-facet'
        # 3. specify the attribute name that actually stores the date in the DB
        rtype = 'composition_date'

And that's it, on each page displaying tracks, you'll be able to filter them
according to their composition date with a jquery slider.

All this, brought by CubicWeb (in the next 3.3 version)

.. _facet: http://en.wikipedia.org/wiki/Faceted_browser
.. _filters: http://www.cubicweb.org/blogentry/154152
.. _jquery: http://www.jqueryui.com/

To use **HasRelationFacet** on a reverse relation add ``role = 'object'`` in
it's definitions.
