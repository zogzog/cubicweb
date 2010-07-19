HTML form construction
----------------------

CubicWeb provides the somewhat usual form / field / widget / renderer abstraction
to provide generic building blocks which will greatly help you in building forms
properly integrated with CubicWeb (coherent display, error handling, etc...),
while keeping things as flexible as possible.

A ``form`` basically only holds a set of ``fields``, and has te be bound to a
``renderer`` which is responsible to layout them. Each field is bound to a
``widget`` that will be used to fill in value(s) for that field (at form
generation time) and 'decode' (fetch and give a proper Python type to) values
sent back by the browser.

The ``field`` should be used according to the type of what you want to edit.
E.g. if you want to edit some date, you'll have to use the
:class:`cubicweb.web.formfields.DateField`. Then you can choose among multiple
widgets to edit it, for instance :class:`cubicweb.web.formwidgets.TextInput` (a
bare text field), :class:`~cubicweb.web.formwidgets.DateTimePicker` (a simple
calendar) or even :class:`~cubicweb.web.formwidgets.JQueryDatePicker` (the JQuery
calendar).  You can of course also write your own widget.

Exploring the available forms
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A small excursion into a |cubicweb| shell is the quickest way to
discover available forms (or application objects in general).

.. sourcecode:: python

 >>> from pprint import pprint
 >>> pprint( session.vreg['forms'] )
 {'base': [<class 'cubicweb.web.views.forms.FieldsForm'>,
           <class 'cubicweb.web.views.forms.EntityFieldsForm'>],
  'changestate': [<class 'cubicweb.web.views.workflow.ChangeStateForm'>,
                  <class 'cubes.tracker.views.forms.VersionChangeStateForm'>],
  'composite': [<class 'cubicweb.web.views.forms.CompositeForm'>,
                <class 'cubicweb.web.views.forms.CompositeEntityForm'>],
  'deleteconf': [<class 'cubicweb.web.views.editforms.DeleteConfForm'>],
  'edition': [<class 'cubicweb.web.views.autoform.AutomaticEntityForm'>,
              <class 'cubicweb.web.views.workflow.TransitionEditionForm'>,
              <class 'cubicweb.web.views.workflow.StateEditionForm'>],
  'logform': [<class 'cubicweb.web.views.basetemplates.LogForm'>],
  'massmailing': [<class 'cubicweb.web.views.massmailing.MassMailingForm'>],
  'muledit': [<class 'cubicweb.web.views.editforms.TableEditForm'>],
  'sparql': [<class 'cubicweb.web.views.sparql.SparqlForm'>]}


The two most important form families here (for all pracitcal purposes)
are `base` and `edition`. Most of the time one wants alterations of
the AutomaticEntityForm (from the `edition` category).

The Automatic Entity Form
~~~~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: cubicweb.web.views.autoform

Anatomy of a choices function
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let's have a look at the `ticket_done_in_choices` function given to
the `choices` parameter of the relation tag that is applied to the
('Ticket', 'done_in', '*') relation definition, as it is both typical
and sophisticated enough. This is a code snippet from the `tracker`_
cube.

.. _`tracker`: http://www.cubicweb.org/project/cubicweb-tracker

The ``Ticket`` entity type can be related to a ``Project`` and a
``Version``, respectively through the ``concerns`` and ``done_in``
relations. When a user is about to edit a ticket, we want to fill the
combo box for the ``done_in`` relation with values pertinent with
respect to the context. The important context here is:

* creation or modification (we cannot fetch values the same way in
  either case)

* ``__linkto`` url parameter given in a creation context

.. sourcecode:: python

    from cubicweb.web import formfields

    def ticket_done_in_choices(form, field):
        entity = form.edited_entity
        # first see if its specified by __linkto form parameters
        linkedto = formfields.relvoc_linkedto(entity, 'done_in', 'subject')
        if linkedto:
            return linkedto
        # it isn't, get initial values
        vocab = formfields.relvoc_init(entity, 'done_in', 'subject')
        veid = None
        # try to fetch the (already or pending) related version and project
        if not entity.has_eid():
            peids = entity.linked_to('concerns', 'subject')
            peid = peids and peids[0]
        else:
            peid = entity.project.eid
            veid = entity.done_in and entity.done_in[0].eid
        if peid:
            # we can complete the vocabulary with relevant values
            rschema = form._cw.vreg.schema['done_in'].rdef('Ticket', 'Version')
            rset = form._cw.execute(
                'Any V, VN ORDERBY version_sort_value(VN) '
                'WHERE V version_of P, P eid %(p)s, V num VN, '
                'V in_state ST, NOT ST name "published"', {'p': peid}, 'p')
            vocab += [(v.view('combobox'), v.eid) for v in rset.entities()
                      if rschema.has_perm(form._cw, 'add', toeid=v.eid)
                      and v.eid != veid]
        return vocab

The first thing we have to do is fetch potential values from the
``__linkto`` url parameter that is often found in entity creation
contexts (the creation action provides such a parameter with a
predetermined value; for instance in this case, ticket creation could
occur in the context of a `Version` entity). The
:mod:`cubicweb.web.formfields` module provides a ``relvoc_linkedto``
utility function that gets a list suitably filled with vocabulary
values.

.. sourcecode:: python

        linkedto = formfields.relvoc_linkedto(entity, 'done_in', 'subject')
        if linkedto:
            return linkedto

Then, if no ``__linkto`` argument was given, we must prepare the
vocabulary with an initial empty value (because `done_in` is not
mandatory, we must allow the user to not select a verson) and already
linked values. This is done with the ``relvoc_init`` function.

.. sourcecode:: python

        vocab = formfields.relvoc_init(entity, 'done_in', 'subject')

But then, we have to give more: if the ticket is related to a project,
we should provide all the non published versions of this project
(`Version` and `Project` can be related through the `version_of`
relation). Conversely, if we do not know yet the project, it would not
make sense to propose all existing versions as it could potentially
lead to incoherences. Even if these will be caught by some
RQLConstraint, it is wise not to tempt the user with error-inducing
candidate values.

The "ticket is related to a project" part must be decomposed as:

* this is a new ticket which is created is the context of a project

* this is an already existing ticket, linked to a project (through the
  `concerns` relation)

* there is no related project (quite unlikely given the cardinality of
  the `concerns` relation, so it can only mean that we are creating a
  new ticket, and a project is about to be selected but there is no
  ``__linkto`` argument)

.. note::

   the last situation could happen in several ways, but of course in a
   polished application, the paths to ticket creation should be
   controlled so as to avoid a suboptimal end-user experience

Hence, we try to fetch the related project.

.. sourcecode:: python

        veid = None
        if not entity.has_eid():
            peids = entity.linked_to('concerns', 'subject')
            peid = peids and peids[0]
        else:
            peid = entity.project.eid
            veid = entity.done_in and entity.done_in[0].eid

We distinguish between entity creation and entity modification using
the ``Entity.has_eid()`` method, which returns `False` on creation. At
creation time the only way to get a project is through the
``__linkto`` parameter. Notice that we fetch the version in which the
ticket is `done_in` if any, for later.

.. note::

  the implementation above assumes that if there is a ``__linkto``
  parameter, it is only about a project. While it makes sense most of
  the time, it is not an absolute. Depending on how an entity creation
  action action url is built, several outcomes could be possible
  there

If the ticket is already linked to a project, fetching it is
trivial. Then we add the relevant version to the initial vocabulary.

.. sourcecode:: python

        if peid:
            rschema = form._cw.vreg.schema['done_in'].rdef('Ticket', 'Version')
            rset = form._cw.execute(
                'Any V, VN ORDERBY version_sort_value(VN) '
                'WHERE V version_of P, P eid %(p)s, V num VN, '
                'V in_state ST, NOT ST name "published"', {'p': peid})
            vocab += [(v.view('combobox'), v.eid) for v in rset.entities()
                      if rschema.has_perm(form._cw, 'add', toeid=v.eid)
                      and v.eid != veid]

.. warning::

   we have to defend ourselves against lack of a project eid. Given
   the cardinality of the `concerns` relation, there *must* be a
   project, but this rule can only be enforced at validation time,
   which will happen of course only after form subsmission

Here, given a project eid, we complete the vocabulary with all
unpublished versions defined in the project (sorted by number) for
which the current user is allowed to establish the relation.

APIs
~~~~

.. automodule:: cubicweb.web.formfields
.. automodule:: cubicweb.web.formwidgets
.. automodule:: cubicweb.web.views.forms
.. automodule:: cubicweb.web.views.formrenderers


