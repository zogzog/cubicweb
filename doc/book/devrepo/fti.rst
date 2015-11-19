.. _fti:

Full Text Indexing in CubicWeb
------------------------------

When an attribute is tagged as *fulltext-indexable* in the datamodel,
CubicWeb will automatically trigger hooks to update the internal
fulltext index (i.e the ``appears`` SQL table) each time this attribute
is modified.

CubicWeb also provides a ``db-rebuild-fti`` command to rebuild the whole
fulltext on demand:

.. sourcecode:: bash

   cubicweb@esope~$ cubicweb db-rebuild-fti my_tracker_instance

You can also rebuild the fulltext index for a given set of entity types:

.. sourcecode:: bash

   cubicweb@esope~$ cubicweb db-rebuild-fti my_tracker_instance Ticket Version

In the above example, only fulltext index of entity types ``Ticket`` and ``Version``
will be rebuilt.


Standard FTI process
~~~~~~~~~~~~~~~~~~~~

Considering an entity type ``ET``, the default *fti* process is to :

1. fetch all entities of type ``ET``

2. for each entity, adapt it to ``IFTIndexable`` (see
   :class:`~cubicweb.entities.adapters.IFTIndexableAdapter`)

3. call
   :meth:`~cubicweb.entities.adapters.IFTIndexableAdapter.get_words` on
   the adapter which is supposed to return a dictionary *weight* ->
   *list of words* as expected by
   :meth:`~logilab.database.fti.FTIndexerMixIn.index_object`. The
   tokenization of each attribute value is done by
   :meth:`~logilab.database.fti.tokenize`.


See :class:`~cubicweb.entities.adapters.IFTIndexableAdapter` for more documentation.


Yams and ``fulltext_container``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is possible in the datamodel to indicate that fulltext-indexed
attributes defined for an entity type will be used to index not the
entity itself but a related entity. This is especially useful for
composite entities. Let's take a look at (a simplified version of)
the base schema defined in CubicWeb (see :mod:`cubicweb.schemas.base`):

.. sourcecode:: python

  class CWUser(WorkflowableEntityType):
      login     = String(required=True, unique=True, maxsize=64)
      upassword = Password(required=True)

  class EmailAddress(EntityType):
      address = String(required=True,  fulltextindexed=True,
                       indexed=True, unique=True, maxsize=128)


  class use_email_relation(RelationDefinition):
      name = 'use_email'
      subject = 'CWUser'
      object = 'EmailAddress'
      cardinality = '*?'
      composite = 'subject'


The schema above states that there is a relation between ``CWUser`` and ``EmailAddress``
and that the ``address`` field of ``EmailAddress`` is fulltext indexed. Therefore,
in your application, if you use fulltext search to look for an email address, CubicWeb
will return the ``EmailAddress`` itself. But the objects we'd like to index
are more likely to be the associated ``CWUser`` than the ``EmailAddress`` itself.

The simplest way to achieve that is to tag the ``use_email`` relation in
the datamodel:

.. sourcecode:: python

  class use_email(RelationType):
      fulltext_container = 'subject'


Customizing how entities are fetched during ``db-rebuild-fti``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``db-rebuild-fti`` will call the
:meth:`~cubicweb.entities.AnyEntity.cw_fti_index_rql_limit` class
method on your entity type.

.. automethod:: cubicweb.entities.AnyEntity.cw_fti_index_rql_limit


Customizing :meth:`~cubicweb.entities.adapters.IFTIndexableAdapter.get_words`
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can also customize the FTI process by providing your own ``get_words()``
implementation:

.. sourcecode:: python

    from cubicweb.entities.adapters import IFTIndexableAdapter

    class SearchIndexAdapter(IFTIndexableAdapter):
        __regid__ = 'IFTIndexable'
        __select__ = is_instance('MyEntityClass')

        def fti_containers(self, _done=None):
            """this should yield any entity that must be considered to
            fulltext-index self.entity

            CubicWeb's default implementation will look for yams'
            ``fulltex_container`` property.
            """
            yield self.entity
            yield self.entity.some_related_entity


        def get_words(self):
            # implement any logic here
            # see http://www.postgresql.org/docs/9.1/static/textsearch-controls.html
            # for the actual signification of 'C'
            return {'C': ['any', 'word', 'I', 'want']}
