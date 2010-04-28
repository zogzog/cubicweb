# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""Mass mailing form views

"""
__docformat__ = "restructuredtext en"
_ = unicode

import operator

from cubicweb.interfaces import IEmailable
from cubicweb.selectors import implements, authenticated_user
from cubicweb.view import EntityView
from cubicweb.web import stdmsgs, action, form, formfields as ff
from cubicweb.web.formwidgets import CheckBox, TextInput, AjaxWidget, ImgButton
from cubicweb.web.views import forms, formrenderers


class SendEmailAction(action.Action):
    __regid__ = 'sendemail'
    # XXX should check email is set as well
    __select__ = (action.Action.__select__ & implements(IEmailable)
                  & authenticated_user())

    title = _('send email')
    category = 'mainactions'

    def url(self):
        params = {'vid': 'massmailing', '__force_display': 1}
        if self._cw.form.has_key('rql'):
            params['rql'] = self._cw.form['rql']
        return self._cw.build_url(self._cw.relative_path(includeparams=False),
                                  **params)


def recipient_vocabulary(form, field):
    vocab = [(entity.get_email(), entity.eid) for entity in form.cw_rset.entities()]
    return [(label, value) for label, value in vocab if label]

class MassMailingForm(forms.FieldsForm):
    __regid__ = 'massmailing'

    needs_js = ('cubicweb.widgets.js', 'cubicweb.massmailing.js')
    needs_css = ('cubicweb.mailform.css')
    domid = 'sendmail'
    action = 'sendmail'

    sender = ff.StringField(widget=TextInput({'disabled': 'disabled'}),
                            label=_('From:'),
                            value=lambda f: '%s <%s>' % (f._cw.user.dc_title(), f._cw.user.get_email()))
    recipient = ff.StringField(widget=CheckBox(), label=_('Recipients:'),
                               choices=recipient_vocabulary,
                               value= lambda f: [entity.eid for entity in f.cw_rset.entities() if entity.get_email()])
    subject = ff.StringField(label=_('Subject:'), max_length=256)
    mailbody = ff.StringField(widget=AjaxWidget(wdgtype='TemplateTextField',
                                                inputid='mailbody'))

    form_buttons = [ImgButton('sendbutton', "javascript: $('#sendmail').submit()",
                              _('send email'), 'SEND_EMAIL_ICON'),
                    ImgButton('cancelbutton', "javascript: history.back()",
                              stdmsgs.BUTTON_CANCEL, 'CANCEL_EMAIL_ICON')]
    form_renderer_id = __regid__

    def __init__(self, *args, **kwargs):
        super(MassMailingForm, self).__init__(*args, **kwargs)
        field = self.field_by_name('mailbody')
        field.widget.attrs['cubicweb:variables'] = ','.join(self.get_allowed_substitutions())

    def get_allowed_substitutions(self):
        attrs = []
        for coltype in self.cw_rset.column_types(0):
            eclass = self._cw.vreg['etypes'].etype_class(coltype)
            attrs.append(eclass.allowed_massmail_keys())
        return sorted(reduce(operator.and_, attrs))

    def build_substitutions_help(self):
        insertLink = u'<a href="javascript: insertText(\'%%(%s)s\', \'emailarea\');">%%(%s)s</a>'
        substs = (u'<div class="substitution">%s</div>' % (insertLink % (subst, subst))
                  for subst in self.get_allowed_substitutions())
        helpmsg = self._cw._('You can use any of the following substitutions in your text')
        return u'<div id="substitutions"><span>%s</span>%s</div>' % (
            helpmsg, u'\n'.join(substs))


class MassMailingFormRenderer(formrenderers.FormRenderer):
    __regid__ = 'massmailing'

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
    __regid__ = 'massmailing'
    __select__ = implements(IEmailable) & authenticated_user()

    def call(self):
        form = self._cw.vreg['forms'].select('massmailing', self._cw,
                                             rset=self.cw_rset)
        self.w(form.render())
