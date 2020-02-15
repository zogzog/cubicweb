.. _reledit:

The "Click and Edit" (also `reledit`) View
------------------------------------------

The principal way to update data through the Web UI is through the
`modify` action on entities, which brings a full form. This is
described in the :ref:`webform` chapter.

There is however another way to perform piecewise edition of entities
and relations, using a specific `reledit` (for *relation edition*)
view from the :mod:`cubicweb.web.views.reledit` module.

This is typically applied from the default Primary View (see
:ref:`primary_view`) on the attributes and relation section. It makes
small editions more convenient.

Of course, this can be used customely in any other view. Here come
some explanation about its capabilities and instructions on the way to
use it.

Using `reledit`
***************

Let's start again with a simple example:

.. sourcecode:: python

   class Company(EntityType):
        name = String(required=True, unique=True)
        boss = SubjectRelation('Person', cardinality='1*')
        status = SubjectRelation('File', cardinality='?*', composite='subject')

In some view code we might want to show these attributes/relations and
allow the user to edit each of them in turn without having to leave
the current page. We would write code as below:

.. sourcecode:: python

   company.view('reledit', rtype='name', default_value='<name>') # editable name attribute
   company.view('reledit', rtype='boss') # editable boss relation
   company.view('reledit', rtype='status') # editable attribute-like relation

If one wanted to edit the company from a boss's point of view, one
would have to indicate the proper relation's role. By default the role
is `subject`.

.. sourcecode:: python

   person.view('reledit', rtype='boss', role='object')

Each of these will provide with a different editing widget. The `name`
attribute will obviously get a text input field. The `boss` relation
will be edited through a selection box, allowing to pick another
`Person` as boss. The `status` relation, given that it defines Company
as a composite entity with one file inside, will provide additional actions

* to `add` a `File` when there is one
* to `delete` the `File` (if the cardinality allows it)

Moreover, editing the relation or using the `add` action leads to an
embedded edition/creation form allowing edition of the target entity
(which is `File` in our example) instead of merely allowing to choose
amongst existing files.

The `reledit_ctrl` rtag
***********************

The behaviour of reledited attributes/relations can be finely
controlled using the reledit_ctrl rtag, defined in
:mod:`cubicweb.web.views.uicfg`.

This rtag provides four control variables:

* ``default_value``: alternative default value
   The default value is what is shown when there is no value.
* ``reload``: boolean, eid (to reload to) or function taking subject
   and returning bool/eid This is useful when editing a relation (or
   attribute) that impacts the url or another parts of the current
   displayed page. Defaults to false.
* ``rvid``: alternative view id (as str) for relation or composite
   edition Default is 'incontext' or 'csv' depending on the
   cardinality. They can also be statically changed by subclassing
   ClickAndEditFormView and redefining _one_rvid (resp. _many_rvid).
* ``edit_target``: 'rtype' (to edit the relation) or 'related' (to
   edit the related entity) This controls whether to edit the relation
   or the target entity of the relation.  Currently only one-to-one
   relations support target entity edition. By default, the 'related'
   option is taken whenever the relation is composite and one-to-one.

Let's see how to use these controls.

.. sourcecode:: python

    from logilab.mtconverter import xml_escape
    from cubicweb.web.views.uicfg import reledit_ctrl
    reledit_ctrl.tag_attribute(('Company', 'name'),
                               {'reload': lambda x:x.eid,
                                'default_value': xml_escape(u'<logilab tastes better>')})
    reledit_ctrl.tag_object_of(('*', 'boss', 'Person'), {'edit_target': 'related'})

The `default_value` needs to be an xml escaped unicode string.

The `edit_target` tag on the `boss` relation being set to `related` will
ensure edition of the `Person` entity instead (using a standard
automatic form) of the association of Company and Person.

Finally, the `reload` key accepts either a boolean, an eid or a
unicode string representing a url. If an eid is provided, it will be
internally transformed into a url. The eid/url case helps when one
needs to reload and the current url is inappropriate. A common case is
edition of a key attribute, which is part of the current url. If one
user changed the Company's name from `lozilab` to `logilab`, reloading
on http://myapp/company/lozilab would fail. Providing the entity's
eid, then, forces to reload on something like http://myapp/company/42,
which always work.


Disable `reledit`
*****************

By default, `reledit` is available on attributes and relations displayed in
the 'attribute' section of the default primary view.  If you want to disable
it for some attribute or relation, you have use `uicfg`:

.. sourcecode:: python

    from cubicweb.web.views.uicfg import primaryview_display_ctrl as _pvdc
    _pvdc.tag_attribute(('Company', 'name'), {'vid': 'incontext'})

To deactivate it everywhere it's used automatically, you may use the code snippet
below somewhere in your cube's views:

.. sourcecode:: python

    from cubicweb.web.views import reledit

    class DeactivatedAutoClickAndEditFormView(reledit.AutoClickAndEditFormView):
        def _should_edit_attribute(self, rschema):
            return False

        def _should_edit_attribute(self, rschema, role):
            return False

    def registration_callback(vreg):
        vreg.register_and_replace(DeactivatedAutoClickAndEditFormView,
                                  reledit.AutoClickAndEditFormView)


