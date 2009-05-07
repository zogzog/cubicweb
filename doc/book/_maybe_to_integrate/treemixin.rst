
Class `TreeMixIn`
-----------------

This class provides a tree interface. This mixin has to be inherited 
explicitly and configured using the tree_attribute, parent_target and 
children_target class attribute to benefit from this default implementation.

This class provides the following methods:

  * `different_type_children(entities=True)`, returns children entities
    of different type as this entity. According to the `entities` parameter, 
    returns entity objects (if entity=True) or the equivalent result set.

  * `same_type_children(entities=True)`, returns children entities of 
    the same type as this entity. According to the `entities` parameter, 
    return entity objects (if entity=True) or the equivalent result set.
  
  * `iterchildren( _done=None)`, iters on the children of the entity.
  
  * `prefixiter( _done=None)`
  
  * `path()`, returns the list of eids from the root object to this object.
  
  * `iterparents()`, iters on the parents of the entity.
  
  * `notification_references(view)`, used to control References field 
    of email send on notification for this entity. `view` is the notification view.
    Should return a list of eids which can be used to generate message ids
    of previously sent email.

`TreeMixIn` implements also the ITree interface (``cubicweb.interfaces``):

  * `parent()`, returns the parent entity if any, else None (e.g. if we are on the
    root)

  * `children(entities=True, sametype=False)`, returns children entities
    according to the `entities` parameter, return entity objects or the
    equivalent result set.

  * `children_rql()`, returns the RQL query corresponding to the children
    of the entity.

  * `is_leaf()`, returns True if the entity does not have any children.

  * `is_root()`, returns True if the entity does not have any parent.

  * `root()`, returns the root object of the tree representation of
    the entity and its related entities.

Example of use
``````````````

Imagine you defined three types of entities in your schema, and they
relates to each others as follows in ``schema.py``::

  class Entity1(EntityType):
      title = String()
      is_related_to = SubjectRelation('Entity2', 'subject')

  class Entity2(EntityType):
      title = String()
      belongs_to = SubjectRelation('Entity3', 'subject')

  class Entity3(EntityType):
      name = String()

You would like to create a view that applies to both entity types
`Entity1` and `Entity2` and which lists the entities they are related to.
That means when you view `Entity1` you want to list all `Entity2`, and
when you view `Entity2` you want to list all `Entity3`.

In ``entities.py``::

  class Entity1(TreeMixIn, AnyEntity):
      id = 'Entity1'
      __implements__ = AnyEntity.__implements__ + (ITree,)
      __rtags__ = {('is_related_to', 'Entity2', 'object'): 'link'}
      tree_attribute = 'is_related_to'

      def children(self, entities=True):
          return self.different_type_children(entities)

  class Entity2(TreeMixIn, AnyEntity):
      id = 'Entity2'
      __implements__ = AnyEntity.__implements__ + (ITree,)
      __rtags__ = {('belongs_to', 'Entity3', 'object'): 'link'}
      tree_attribute = 'belongs_to'

      def children(self, entities=True):
          return self.different_type_children(entities)

Once this is done, you can define your common view as follows::

  class E1E2CommonView(baseviews.PrimaryView):
      accepts = ('Entity11, 'Entity2')
      
      def render_entity_relations(self, entity, siderelations):
          self.wview('list', entity.children(entities=False))

