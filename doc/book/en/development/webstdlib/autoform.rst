The automatic entity form (:mod:`cubicweb.web.views.autoform`)
---------------------------------------------------------------

It is possible to manage attributes/relations in the simple or multiple
editing form thanks to the following *rtags*: 

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
