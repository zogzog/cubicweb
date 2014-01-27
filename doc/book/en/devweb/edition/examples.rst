Examples
--------

(Automatic) Entity form
~~~~~~~~~~~~~~~~~~~~~~~

Looking at some cubes available on the `cubicweb forge`_ we find some
with form manipulation. The following example comes from the the
`conference`_ cube. It extends the change state form for the case
where a ``Talk`` entity is getting into ``submitted`` state. The goal
is to select reviewers for the submitted talk.

.. _`cubicweb forge`: http://www.cubicweb.org/view?rql=Any+P+ORDERBY+N+WHERE+P+name+LIKE+%22cubicweb-%25%22%2C+P+is+Project%2C+P+name+N
.. _`conference`: http://www.cubicweb.org/project/cubicweb-conference

.. sourcecode:: python

 from cubicweb.web import formfields as ff, formwidgets as fwdgs
 class SendToReviewerStatusChangeView(ChangeStateFormView):
     __select__ = (ChangeStateFormView.__select__ &
                   is_instance('Talk') &
                   rql_condition('X in_state S, S name "submitted"'))

     def get_form(self, entity, transition, **kwargs):
         form = super(SendToReviewerStatusChangeView, self).get_form(entity, transition, **kwargs)
         relation = ff.RelationField(name='reviews', role='object',
                                     eidparam=True,
                                     label=_('select reviewers'),
                                     widget=fwdgs.Select(multiple=True))
         form.append_field(relation)
         return form

Simple extension of a form can be done from within the `FormView`
wrapping the form. FormView instances have a handy ``get_form`` method
that returns the form to be rendered. Here we add a ``RelationField``
to the base state change form.

One notable point is the ``eidparam`` argument: it tells both the
field and the ``edit controller`` that the field is linked to a
specific entity.

It is hence entirely possible to add ad-hoc fields that will be
processed by some specialized instance of the edit controller.


Ad-hoc fields form
~~~~~~~~~~~~~~~~~~

We want to define a form doing something else than editing an entity. The idea is
to propose a form to send an email to entities in a resultset which implements
:class:`IEmailable`.  Let's take a simplified version of what you'll find in
:mod:`cubicweb.web.views.massmailing`.

Here is the source code:

.. sourcecode:: python

    def sender_value(form, field):
	return '%s <%s>' % (form._cw.user.dc_title(), form._cw.user.get_email())

    def recipient_choices(form, field):
	return [(e.get_email(), e.eid)
                 for e in form.cw_rset.entities()
		 if e.get_email()]

    def recipient_value(form, field):
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
resource identifier (see :ref:`uiprops`) given as last argument to
:class:`cubicweb.web.formwidgets.ImgButton`.

To see this form, we still have to wrap it in a view. This is pretty simple:

.. sourcecode:: python

    class MassMailingFormView(form.FormViewMixIn, EntityView):
	__regid__ = 'massmailing'
	__select__ = is_instance(IEmailable) & authenticated_user()

	def call(self):
	    form = self._cw.vreg['forms'].select('massmailing', self._cw,
	                                         rset=self.cw_rset)
	    form.render(w=self.w)

As you see, we simply define a view with proper selector so it only apply to a
result set containing :class:`IEmailable` entities, and so that only users in the
managers or users group can use it. Then in the `call()` method for this view we
simply select the above form and call its `.render()` method with our output
stream as argument.

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
           if not self._cw.vreg.config.sendmails([(msg, recipients)]):
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

