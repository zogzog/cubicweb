
Relation tags
--------------
XXX cubicweb.rtags
    ref to action box and auto edit form


*rtags* allow to specify certain behaviors of relations relative to a given
entity type (see later). They are defined  for ::

  <relation type>, <context position ("subject" ou "object")>, <subject entity type or *>, <object entity type or *> 

and as values may be a `set` or single value, depending on what the relation tags is used for.

It is possible to simplify this dictionary:

* if we want a marker to apply independently from a subject or object entity type,
  we have to use the string `*` as entity type


Please note that this dictionary is *treated at the time the class is created*.
It is automatically merged with the parent class(es) (no need to copy the
dictionary from the parent class to modify it). Also, modifying it after the 
class is created will not have any effect...
