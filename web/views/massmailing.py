"""Mass mailing form views

:organization: Logilab
:copyright: 2007-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

import operator

from cubicweb.interfaces import IEmailable
from cubicweb.selectors import implements, match_user_groups
from cubicweb.view import EntityView
from cubicweb.web import stdmsgs, action, form, formfields as ff
from cubicweb.web.formwidgets import CheckBox, TextInput, AjaxWidget, ImgButton
from cubicweb.web.views import forms, formrenderers


class SendEmailAction(action.Action):
    id = 'sendemail'
    # XXX should check email is set as well
    __select__ = (action.Action.__select__ & implements(IEmailable)
                  & match_user_groups('managers', 'users'))

    title = _('send email')
    category = 'mainactions'

    def url(self):
        params = {'vid': 'massmailing', '__force_display': 1}
        if self.req.form.has_key('rql'):
            params['rql'] = self.req.form['rql']
        return self.build_url(self.req.relative_path(includeparams=False),
                              **params)


class MassMailingForm(forms.FieldsForm):
    id = 'massmailing'

    sender = ff.StringField(widget=TextInput({'disabled': 'disabled'}),
                            label=_('From:'))
    recipient = ff.StringField(widget=CheckBox(), label=_('Recipients:'))
    subject = ff.StringField(label=_('Subject:'), max_length=256)
    mailbody = ff.StringField(widget=AjaxWidget(wdgtype='TemplateTextField',
                                                inputid='mailbody'))

    form_buttons = [ImgButton('sendbutton', "javascript: $('#sendmail').submit()",
                              _('send email'), 'SEND_EMAIL_ICON'),
                    ImgButton('cancelbutton', "javascript: history.back()",
                              stdmsgs.BUTTON_CANCEL, 'CANCEL_EMAIL_ICON')]
    form_renderer_id = id

    def form_field_vocabulary(self, field):
        if field.name == 'recipient':
            vocab = [(entity.get_email(), entity.eid) for entity in self.rset.entities()]
            return [(label, value) for label, value in vocab if label]
        return super(MassMailingForm, self).form_field_vocabulary(field)

    def form_field_value(self, field, values):
        if field.name == 'recipient':
            return [entity.eid for entity in self.rset.entities() if entity.get_email()]
        elif field.name == 'mailbody':
            field.widget.attrs['cubicweb:variables'] = ','.join(self.get_allowed_substitutions())
        return super(MassMailingForm, self).form_field_value(field, values)

    def get_allowed_substitutions(self):
        attrs = []
        for coltype in self.rset.column_types(0):
            eclass = self.vreg['etypes'].etype_class(coltype)
            attrs.append(eclass.allowed_massmail_keys())
        return sorted(reduce(operator.and_, attrs))

    def build_substitutions_help(self):
        insertLink = u'<a href="javascript: insertText(\'%%(%s)s\', \'emailarea\');">%%(%s)s</a>'
        substs = (u'<div class="substitution">%s</div>' % (insertLink % (subst, subst))
                  for subst in self.get_allowed_substitutions())
        helpmsg = self.req._('You can use any of the following substitutions in your text')
        return u'<div id="substitutions"><span>%s</span>%s</div>' % (
            helpmsg, u'\n'.join(substs))


class MassMailingFormRenderer(formrenderers.FormRenderer):
    id = 'massmailing'
    button_bar_class = u'toolbar'

    def _render_fields(self, fields, w, form):
        w(u'<table class="headersform">')
        for field in fields:
            if field.name == 'mailbody':
                w(u'</table>')
                self._render_toolbar(w, form)
                w(u'<table>')
                w(u'<tr><td><div>')
            else:
                w(u'<tr>')
                w(u'<td class="hlabel">%s</td>' % self.render_label(form, field))
                w(u'<td class="hvalue">')
            w(field.render(form, self))
            if field.name == 'mailbody':
                w(u'</div></td>')
                w(u'<td>%s</td>' % form.build_substitutions_help())
                w(u'</tr>')
            else:
                w(u'</td></tr>')
        w(u'</table>')

    def _render_toolbar(self, w, form):
        w(u'<div id="toolbar">')
        w(u'<ul>')
        for button in form.form_buttons:
            w(u'<li>%s</li>' % button.render(form))
        w(u'</ul>')
        w(u'</div>')

    def render_buttons(self, w, form):
        pass

class MassMailingFormView(form.FormViewMixIn, EntityView):
    id = 'massmailing'
    __select__ = implements(IEmailable) & match_user_groups('managers', 'users')

    def call(self):
        req = self.req
        req.add_js('cubicweb.widgets.js', 'cubicweb.massmailing.js')
        req.add_css('cubicweb.mailform.css')
        from_addr = '%s <%s>' % (req.user.dc_title(), req.user.get_email())
        form = self.vreg['forms'].select('massmailing', self.req, rset=self.rset,
                                action='sendmail', domid='sendmail')
        self.w(form.render(formvalues=dict(sender=from_addr)))
