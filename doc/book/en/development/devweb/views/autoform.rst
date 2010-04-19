The automatic entity form
-------------------------

(:mod:`cubicweb.web.views.autoform`)

Tags declaration
````````````````

It is possible to manage attributes/relations in the simple or multiple
editing form using proper uicfg tags.

.. sourcecode:: python

  uicfg.autoform_section.tag_subject_of(<relation>, tag)
  uicfg.autoform_section.tag_object_of(<relation>, tag)
  uicfg.autoform_field.tag_attribute(<attribut_def>, tag)

The details of the uicfg syntax can be found in the :ref:`uicfg`
chapter.

Possible tags are detailled below

Automatic form configuration
````````````````````````````

Attributes/relations display location
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``uicfg.autoform_section`` specifies where to display a relation in
creation/edition entity form for a given form type.  ``tag_attribute``,
``tag_subject_of`` and ``tag_object_of`` methods for this relation tag expect
two arguments additionally to the relation key: a ``formtype`` and a
``section``.

``formtype`` may be one of:

* ``main``, the main entity form (via the modify action)
* ``inlined``, the form for an entity inlined into another form
* ``muledit``, the table form to edit multiple entities

section may be one of:

* ``hidden``, don't display

* ``attributes``, display in the attributes section

* ``relations``, display in the relations section, using the generic relation
  selector combobox (available in main form only, and not for attribute
  relation)

* ``inlined``, display target entity of the relation in an inlined form
  (available in main form only, and not for attribute relation)

* ``metadata``, display in a special metadata form (NOT YET IMPLEMENTED, subject
  to changes)

By default, mandatory relations are displayed in the ``attributes`` section,
others in ``relations`` section.

Change default fields
^^^^^^^^^^^^^^^^^^^^^

Use ``autoform_field`` to replace the default field type of an attribute.

.. warning::

   ``autoform_field_kwargs`` should usually be used instead of
   ``autoform_field``. Do not use both methods for the same relation!


Customize field options
^^^^^^^^^^^^^^^^^^^^^^^

In order to customize field options (see :class:`cubicweb.web.formfields.Field`
for a detailed list of options), use ``autoform_field_kwargs``. This rtag takes
a relation triplet and a dictionary as arguments.

.. sourcecode:: python

   # Change the content of the combobox
   # here ``ticket_done_in_choices`` is a function which returns a list of
   # elements to populate the combobox
   uicfg.autoform_field_kwargs.tag_subject_of(('Ticket', 'done_in', '*'), {'sort': False,
                                                  'choices': ticket_done_in_choices})



Overriding permissions
^^^^^^^^^^^^^^^^^^^^^^

``autoform_permissions_overrides`` provides a way to by-pass security checking
for dark-corner case where it can't be verified properly. XXX documents.
