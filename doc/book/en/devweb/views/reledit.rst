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
:mod:`cubicweb.web.uicfg`.

This rtag provides three control variables:

* ``default_value``
* ``reload``, to specificy if edition of the relation entails a full page
  reload, which defaults to False
* ``noedit``, to explicitly inhibit edition

Let's see how to use these controls.

.. sourcecode:: python

    from logilab.mtconverter import xml_escape
    from cubicweb.web.uicfg import reledit_ctrl
    reledit_ctrl.tag_attribute(('Company', 'name'),
                               {'reload': lambda x:x.eid,
                                'default_value': xml_escape(u'<logilab tastes better>')})
    reledit_ctrl.tag_object_of(('*', 'boss', 'Person'), {'noedit': True})

The `default_value` needs to be an xml escaped unicode string.

The `noedit` attribute is convenient to programmatically disable some
relation edition on views that apply it systematically (the prime
example being the primary view). Here we use it to forbid changing the
`boss` relation from a `Person` side (as it could have unwanted
effects).

Finally, the `reload` key accepts either a boolean, an eid or an
unicode string representing an url. If an eid is provided, it will be
internally transformed into an url. The eid/url case helps when one
needs to reload and the current url is inappropriate. A common case is
edition of a key attribute, which is part of the current url. If one
user changed the Company's name from `lozilab` to `logilab`, reloading
on http://myapp/company/lozilab would fail. Providing the entity's
eid, then, forces to reload on something like http://myapp/company/42,
which always work.






