The automatic entity form (:mod:`cubicweb.web.views.autoform`)
---------------------------------------------------------------

Tags declaration
~~~~~~~~~~~~~~~~~~~~

It is possible to manage attributes/relations in the simple or multiple
editing form thanks of the methods bellow ::

  uicfg.autoform_section.tag_subject_of(<relation>, tag)
  uicfg.autoform_section.tag_object_of(<relation>, tag)
  uicfg.autoform_field.tag_attribute(<attribut_def>, tag)

Where ``<relation>`` is a three elements tuple ``(Subject Entity Type,
relation_type, Object Entity Type)``. ``<attribut_def>`` is a two elements tuple
``(Entity Type, Attribut Name)``. Wildcard ``*`` could be used in place of
``Entity Type``

Possible tags are detailled below

Simple Tags
~~~~~~~~~~~~~~~~~~~~

* `primary`, indicates that an attribute or a relation has to be
  inserted **in the simple or multiple editing forms**. In the case of
  a relation, the related entity editing form will be included in the
  editing form and represented as a combobox. Each item of the
  combobox is a link to an existing entity.

* `secondary`, indicates that an attribute or a relation has to be
  inserted **in the simple editing form only**. In the case of a
  relation, the related entity editing form will be included in the
  editing form and represented as a combobox. Each item of the combobox
  is a link to an existing entity.

* `inlineview`, includes the target entity's form in the editing form
  of the current entity. It allows to create the target entity in the
  same time as the current entity.

* `generic`, indicates that a relation has to be inserted in the simple
  editing form, in the generic box of relation creation.

* `generated`, indicates that an attribute is dynamically computed
  or other,  and that it should not be displayed in the editing form.

If necessary, it is possible to overwrite the method
`relation_category(rtype, x='subject')` to dynamically compute
a relation editing category.


Advanced Tags
~~~~~~~~~~~~~~~~~~~~

Tag can also reference a custom Field crafted with the help of
``cubicweb.web.formfields`` and ``cubicweb.web.formwidget``. In the example
bellow, the field ``path`` of ``ExecData`` entities will be done with a standard
file input dialogue ::

  from cubicweb.web import uicfg, formfields, formwidgets

  uicfg.autoform_field.tag_attribute(('Execdata', 'path'),
      formfields.FileField(name='path', widget=formwidgets.FileInput()))







