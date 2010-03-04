Interfaces
----------

Same thing as object-oriented programming interfaces.

Definition of an interface is quite trivial. An example from cubicweb
itself (found in cubicweb/interfaces.py):

.. sourcecode:: python

    class ITree(Interface):

        def parent(self):
            """returns the parent entity"""

        def children(self):
            """returns the item's children"""

        def children_rql(self):
            """XXX returns RQL to get children"""

        def iterchildren(self):
            """iterates over the item's children"""

        def is_leaf(self):
            """returns true if this node as no child"""

        def is_root(self):
            """returns true if this node has no parent"""

        def root(self):
            """returns the root object"""


Declaration of interfaces implemented by a class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. sourcecode:: python

  from cubicweb.interfaces import ITree
  from cubicweb.mixins import TreeMixIn

  class MyEntity(TreeMixIn, AnyEntity):
      __regid__ = 'MyEntity'
      __implements__ = AnyEntity.__implements__ + ('ITree',)

      tree_attribute = 'filed_under'

The TreeMixIn here provides a default implementation for the
interface. The tree_attribute class attribute is actually used by this
implementation to help implement correct behaviour.

Interfaces (and some implementations as mixins) defined in the library
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: cubicweb.interface
   :members:

.. automodule:: cubicweb.mixins
   :members:



