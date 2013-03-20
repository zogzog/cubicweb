Boxes
-----

(:mod:`cubicweb.web.views.boxes`)

*sidebox*
  This view displays usually a side box of some related entities
  in a primary view.

The action box
~~~~~~~~~~~~~~~

The ``add_related`` is an automatic menu in the action box that allows to create
an entity automatically related to the initial entity (context in
which the box is displayed). By default, the links generated in this
box are computed from the schema properties of the displayed entity,
but it is possible to explicitly specify them thanks to the
`cubicweb.web.views.uicfg.rmode` *relation tag*:

* `link`, indicates that a relation is in general created pointing
  to an existing entity and that we should not to display a link
  for this relation

* `create`, indicates that a relation is in general created pointing
  to new entities and that we should display a link to create a new
  entity and link to it automatically


If necessary, it is possible to overwrite the method
`relation_mode(rtype, targettype, x='subject')` to dynamically
compute a relation creation category.

Please note that if at least one action belongs to the `addrelated` category,
the automatic behavior is desactivated in favor of an explicit behavior
(e.g. display of `addrelated` category actions only).

