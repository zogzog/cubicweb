.. _adapters:

Interfaces and Adapters
-----------------------

Interfaces are the same thing as object-oriented programming `interfaces`_.
Adapter refers to a well-known `adapter`_ design pattern that helps separating
concerns in object oriented applications.

.. _`interfaces`: http://java.sun.com/docs/books/tutorial/java/concepts/interface.html
.. _`adapter`: http://en.wikipedia.org/wiki/Adapter_pattern

In |cubicweb| adapters provide logical functionalities to entity types.

Definition of an adapter is quite trivial. An excerpt from cubicweb
itself (found in :mod:`cubicweb.entities.adapters`):

.. sourcecode:: python


    class ITreeAdapter(EntityAdapter):
        """This adapter has to be overriden to be configured using the
        tree_relation, child_role and parent_role class attributes to
        benefit from this default implementation
        """
        __regid__ = 'ITree'

        child_role = 'subject'
        parent_role = 'object'

        def children_rql(self):
            """returns RQL to get children """
            return self.entity.cw_related_rql(self.tree_relation, self.parent_role)

The adapter object has ``self.entity`` attribute which represents the
entity being adapted.

.. Note::

   Adapters came with the notion of service identified by the registry identifier
   of an adapters, hence dropping the need for explicit interface and the
   :class:`cubicweb.predicates.implements` selector. You should instead use
   :class:`cubicweb.predicates.is_instance` when you want to select on an entity
   type, or :class:`cubicweb.predicates.adaptable` when you want to select on a
   service.


Specializing and binding an adapter
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. sourcecode:: python

  from cubicweb.entities.adapters import ITreeAdapter

  class MyEntityITreeAdapter(ITreeAdapter):
      __select__ = is_instance('MyEntity')
      tree_relation = 'filed_under'

The ITreeAdapter here provides a default implementation. The
tree_relation class attribute is actually used by this implementation
to help implement correct behaviour.

Here we provide a specific implementation which will be bound for
``MyEntity`` entity type (the `adaptee`).


.. _interfaces_to_adapters:

Converting code from Interfaces/Mixins to Adapters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here we go with a small example. Before:

.. sourcecode:: python

    from cubicweb.predicates import implements
    from cubicweb.interfaces import ITree
    from cubicweb.mixins import ITreeMixIn

    class MyEntity(ITreeMixIn, AnyEntity):
        __implements__ = AnyEntity.__implements__ + (ITree,)


    class ITreeView(EntityView):
        __select__ = implements('ITree')
        def cell_call(self, row, col):
            entity = self.cw_rset.get_entity(row, col)
            children = entity.children()

After:

.. sourcecode:: python

    from cubicweb.predicates import adaptable, is_instance
    from cubicweb.entities.adapters import ITreeAdapter

    class MyEntityITreeAdapter(ITreeAdapter):
        __select__ = is_instance('MyEntity')

    class ITreeView(EntityView):
        __select__ = adaptable('ITree')
        def cell_call(self, row, col):
            entity = self.cw_rset.get_entity(row, col)
            itree = entity.cw_adapt_to('ITree')
            children = itree.children()

As we can see, the interface/mixin duality disappears and the entity
class itself is completely freed from these concerns. When you want
to use the ITree interface of an entity, call its `cw_adapt_to` method
to get an adapter for this interface, then access to members of the
interface on the adapter

Let's look at an example where we defined everything ourselves. We
start from:

.. sourcecode:: python

    class IFoo(Interface):
        def bar(self, *args):
            raise NotImplementedError

    class MyEntity(AnyEntity):
        __regid__ = 'MyEntity'
        __implements__ = AnyEntity.__implements__ + (IFoo,)

        def bar(self, *args):
            return sum(captain.age for captain in self.captains)

    class FooView(EntityView):
        __regid__ = 'mycube.fooview'
        __select__ = implements('IFoo')

        def cell_call(self, row, col):
            entity = self.cw_rset.get_entity(row, col)
            self.w('bar: %s' % entity.bar())

Converting to:

.. sourcecode:: python

   class IFooAdapter(EntityAdapter):
       __regid__ = 'IFoo'
       __select__ = is_instance('MyEntity')

       def bar(self, *args):
           return sum(captain.age for captain in self.entity.captains)

   class FooView(EntityView):
        __regid__ = 'mycube.fooview'
        __select__ = adaptable('IFoo')

        def cell_call(self, row, col):
            entity = self.cw_rset.get_entity(row, col)
            self.w('bar: %s' % entity.cw_adapt_to('IFoo').bar())

.. note::

   When migrating an entity method to an adapter, the code can be moved as is
   except for the `self` of the entity class, which in the adapter must become `self.entity`.

Adapters defined in the library
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: cubicweb.entities.adapters
   :members:

More are defined in web/views.
