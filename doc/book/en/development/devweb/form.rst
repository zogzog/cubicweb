Form construction
------------------

Forms
~~~~~
XXX feed me
:Vocabulary control on relations:

  * `vocabulary(rtype, x='subject', limit=None)`, called by the
    editing views, it returns a list of couples (label, eid) of entities
    that could be related to the entity by the relation `rtype`
  * `subject_relation_vocabulary(rtype, limit=None)`, called internally 
    by  `vocabulary` in the case of a subject relation
  * `object_relation_vocabulary(rtype, limit=None)`, called internally 
    by  `vocabulary` in the case of an object relation
  * `relation_vocabulary(rtype, targettype, x, limit=None)`, called
    internally by `subject_relation_vocabulary` and `object_relation_vocabulary`

Fields
~~~~~~
XXX feed me

Widgets
~~~~~~~
XXX feed me

Renderers
~~~~~~~~~
XXX feed me
