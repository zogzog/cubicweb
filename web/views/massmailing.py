"""Mass mailing form views

:organization: Logilab
:copyright: 2007-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""

import operator

from logilab.mtconverter import html_escape

from cubicweb.interfaces import IEmailable
from cubicweb.selectors import implements, match_user_groups
from cubicweb.common.view import EntityView
from cubicweb.web.action import Action
from cubicweb.web import stdmsgs


class SendEmailAction(Action):
    category = 'mainactions'
    # XXX should check email is set as well
    __select__ = implements(IEmailable) & match_user_groups('managers', 'users')

    id = 'sendemail'
    title = _('send email')

    def url(self):
        params = {'vid': 'massmailing', '__force_display': 1}
        if self.req.form.has_key('rql'):
            params['rql'] = self.req.form['rql']
        return self.build_url(self.req.relative_path(includeparams=False),
                              **params)


class MassMailingForm(EntityView):
    id = 'massmailing'
    __select__ = implements(IEmailable) & match_user_groups('managers', 'users')

    form_template = u"""
<div id="compose">
<form id="sendemail" action="sendmail" method="post">
<table class="headersform">
<tr>
  <td class="hlabel">%(from_header)s</td>
  <td class="hvalue">%(from)s</td>
</tr>
<tr>
  <td class="hlabel">%(recipients_header)s</td>
  <td class="hvalue">%(recipients)s</td>
</tr>
<tr>
  <td class="hlabel">%(subject)s</td>
  <td class="hvalue"><input id="mailsubj" name="mailsubject" value="" /></td>
</tr>
</table>
<div id="toolbar">
<ul>
<li><a id="sendbutton" href="javascript: $('sendemail').submit()">
    <img src="%(sendimgpath)s" alt="%(send)s"/>%(send)s</a></li>
<li><a id="cancelbutton" href="javascript: history.back()">
    <img src="%(cancelimgpath)s" alt="%(cancel)s"/>%(cancel)s</a></li>
 </ul>
</div>
<table>
<tr>
  <td>
    <div>
      <div id="emailbody" class="widget" cubicweb:loadtype="auto" cubicweb:wdgtype="TemplateTextField"
           cubicweb:inputid="emailarea" cubicweb:inputname="mailbody" cubicweb:variables="%(variables)s"/>
    </div>
  </td>
  <td>%(substitutions)s</td>
</tr>
</table>
</form>
</div>
    """    

    def call(self):
        req = self.req
        req.add_js('cubicweb.widgets.js')
        req.add_css('cubicweb.mailform.css')
        from_addr = '%s <%s>' % (req.user.dc_title(), req.user.get_email())
        ctx = {
            'from_header' : req._('From: '),
            'from' : html_escape(from_addr),
            'substitutions' : self._build_substitutions_help(),
            'recipients_header' : req._('Recipients: '),
            'subject' : req._('Subject: '),
            'body' : req._('Email body: '),
            'variables' : ','.join(self._get_allowed_substitutions()),
            'recipients' : self._build_recipients_list(),
            'cancel' : req._(stdmsgs.BUTTON_CANCEL),
            'cancelimgpath' : req.external_resource('CANCEL_EMAIL_ICON'),
            'send' : req._('send email'),
            'sendimgpath' : req.external_resource('SEND_EMAIL_ICON'),
            }
        self.w(self.form_template % ctx)


    def _get_allowed_substitutions(self):
        coltypes = self.rset.column_types(0)
        attrs = []
        for coltype in coltypes:
            eclass = self.vreg.etype_class(coltype)
            attrs.append(eclass.allowed_massmail_keys())
        return sorted(reduce(operator.and_, attrs))
            
    def _build_recipients_list(self):
        emails = ((entity.eid, entity.get_email()) for entity in self.rset.entities())
        checkboxes = (u'<input name="recipient" type="checkbox" value="%s" checked="checked" />%s'
                      % (eid, html_escape(email)) for eid, email in emails if email)
        boxes = (u'<div class="recipient">%s</div>' % cbox for cbox in checkboxes)
        return u'<div id="recipients">%s</div>' % u'\n'.join(boxes)
            

    def _build_substitutions_help(self):
        insertLink = u'<a href="javascript: insertText(\'%%(%s)s\', \'emailarea\');">%%(%s)s</a>'
        substs = (u'<div class="substitution">%s</div>' % (insertLink % (subst, subst))
                  for subst in self._get_allowed_substitutions())
        helpmsg = self.req._('You can use any of the following substitutions in your text')
        return u'<div id="substitutions"><span>%s</span>%s</div>' % (
            helpmsg, u'\n'.join(substs))

    
