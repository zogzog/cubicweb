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
which the current user is allowed to establish the relation. Of
course, we take care *not* to provide a version the ticket is already
linked to (through ``done_in``).


Example of ad-hoc fields form
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

We want to define a form doing something else than editing an entity. The idea is
to propose a form to send an email to entities in a resultset which implements
:class:`IEmailable`.  Let's take a simplified version of what you'll find in
:mod:`cubicweb.web.views.massmailing`.

Here is the source code:

.. sourcecode:: python

    def sender_value(form):
	return '%s <%s>' % (form._cw.user.dc_title(), form._cw.user.get_email())

    def recipient_choices(form, field):
	return [(e.get_email(), e.eid)
                 for e in form.cw_rset.entities()
		 if e.get_email()]

    def recipient_value(form):
	return [e.eid for e in form.cw_rset.entities()
                if e.get_email()]

    class MassMailingForm(forms.FieldsForm):
	__regid__ = 'massmailing'

	needs_js = ('cubicweb.widgets.js',)
	domid = 'sendmail'
	action = 'sendmail'

	sender = ff.StringField(widget=TextInput({'disabled': 'disabled'}),
				label=_('From:'),
				value=sender_value)

	recipient = ff.StringField(widget=CheckBox(),
	                           label=_('Recipients:'),
				   choices=recipient_choices,
				   value=recipients_value)

	subject = ff.StringField(label=_('Subject:'), max_length=256)

	mailbody = ff.StringField(widget=AjaxWidget(wdgtype='TemplateTextField',
						    inputid='mailbody'))

	form_buttons = [ImgButton('sendbutton', "javascript: $('#sendmail').submit()",
				  _('send email'), 'SEND_EMAIL_ICON'),
			ImgButton('cancelbutton', "javascript: history.back()",
				  stdmsgs.BUTTON_CANCEL, 'CANCEL_EMAIL_ICON')]

Let's detail what's going on up there. Our form will hold four fields:

* a sender field, which is disabled and will simply contains the user's name and
  email

* a recipients field, which will be displayed as a list of users in the context
  result set with checkboxes so user can still choose who will receive his mailing
  by checking or not the checkboxes. By default all of them will be checked since
  field's value return a list containing same eids as those returned by the
  vocabulary function.

* a subject field, limited to 256 characters (hence we know a
  :class:`~cubicweb.web.formwidgets.TextInput` will be used, as explained in
  :class:`~cubicweb.web.formfields.StringField`)

* a mailbody field. This field use an ajax widget, defined in `cubicweb.widgets.js`,
  and whose definition won't be shown here. Notice though that we tell this form
  need this javascript file by using `needs_js`

Last but not least, we add two buttons control: one to post the form using
javascript (`$('#sendmail')` being the jQuery call to get the element with DOM id
set to 'sendmail', which is our form DOM id as specified by its `domid`
attribute), another to cancel the form which will go back to the previous page
using another javascript call. Also we specify an image to use as button icon as a
resource identifier (see :ref:`external_resources`) given as last argument to
:class:`cubicweb.web.formwidgets.ImgButton`.

To see this form, we still have to wrap it in a view. This is pretty simple:

.. sourcecode:: python

    class MassMailingFormView(form.FormViewMixIn, EntityView):
	__regid__ = 'massmailing'
	__select__ = implements(IEmailable) & authenticated_user()

	def call(self):
	    form = self._cw.vreg['forms'].select('massmailing', self._cw,
	                                         rset=self.cw_rset)
	    self.w(form.render())

As you see, we simply define a view with proper selector so it only apply to a
result set containing :class:`IEmailable` entities, and so that only users in the
managers or users group can use it. Then in the `call()` method for this view we
simply select the above form and write what its `.render()` method returns.

When this form is submitted, a controller with id 'sendmail' will be called (as
specified using `action`). This controller will be responsible to actually send
the mail to specified recipients.

Here is what it looks like:

.. sourcecode:: python

   class SendMailController(Controller):
       __regid__ = 'sendmail'
       __select__ = (authenticated_user() &
                     match_form_params('recipient', 'mailbody', 'subject'))

       def publish(self, rset=None):
           body = self._cw.form['mailbody']
           subject = self._cw.form['subject']
           eids = self._cw.form['recipient']
           # eids may be a string if only one recipient was specified
           if isinstance(eids, basestring):
               rset = self._cw.execute('Any X WHERE X eid %(x)s', {'x': eids})
           else:
               rset = self._cw.execute('Any X WHERE X eid in (%s)' % (','.join(eids)))
           recipients = list(rset.entities())
           msg = format_mail({'email' : self._cw.user.get_email(),
                              'name' : self._cw.user.dc_title()},
                             recipients, body, subject)
           if not self._cw.vreg.config.sendmails([(msg, recipients]):
               msg = self._cw._('could not connect to the SMTP server')
           else:
               msg = self._cw._('emails successfully sent')
           raise Redirect(self._cw.build_url(__message=msg))


The entry point of a controller is the publish method. In that case we simply get
back post values in request's `form` attribute, get user instances according
to eids found in the 'recipient' form value, and send email after calling
:func:`format_mail` to get a proper email message. If we can't send email or
if we successfully sent email, we redirect to the index page with proper message
to inform the user.

Also notice that our controller has a selector that deny access to it
to anonymous users (we don't want our instance to be used as a spam
relay), but also checks if the expected parameters are specified in
forms. That avoids later defensive programming (though it's not enough
to handle all possible error cases).

To conclude our example, suppose we wish a different form layout and that existent
renderers are not satisfying (we would check that first of course :). We would then
have to define our own renderer:

.. sourcecode:: python

    class MassMailingFormRenderer(formrenderers.FormRenderer):
        __regid__ = 'massmailing'

        def _render_fields(self, fields, w, form):
            w(u'<table class="headersform">')
            for field in fields:
                if field.name == 'mailbody':
                    w(u'</table>')
                    w(u'<div id="toolbar">')
                    w(u'<ul>')
                    for button in form.form_buttons:
                        w(u'<li>%s</li>' % button.render(form))
                    w(u'</ul>')
                    w(u'</div>')
                    w(u'<div>')
                    w(field.render(form, self))
                    w(u'</div>')
                else:
                    w(u'<tr>')
                    w(u'<td class="hlabel">%s</td>' %
                      self.render_label(form, field))
                    w(u'<td class="hvalue">')
                    w(field.render(form, self))
                    w(u'</td></tr>')

        def render_buttons(self, w, form):
            pass

We simply override the `_render_fields` and `render_buttons` method of the base form renderer
to arrange fields as we desire it: here we'll have first a two columns table with label and
value of the sender, recipients and subject field (form order respected), then form controls,
then a div containing the textarea for the email's content.

To bind this renderer to our form, we should add to our form definition above:

.. sourcecode:: python

    form_renderer_id = 'massmailing'

API
~~~

.. automodule:: cubicweb.web.formfields
.. automodule:: cubicweb.web.formwidgets
.. automodule:: cubicweb.web.views.forms
.. automodule:: cubicweb.web.views.formrenderers
