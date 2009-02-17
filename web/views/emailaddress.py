"""Specific views for email addresses entities

:organization: Logilab
:copyright: 2001-2008 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape

from cubicweb.selectors import implements
from cubicweb.common import Unauthorized
from cubicweb.web.views import baseviews

class EmailAddressPrimaryView(baseviews.PrimaryView):
    __select__ = implements('EmailAddress')
    
    def cell_call(self, row, col, skipeids=None):
        self.skipeids = skipeids
        super(EmailAddressPrimaryView, self).cell_call(row, col)
        
    def render_entity_attributes(self, entity, siderelations):
        self.w(u'<h3>')
        entity.view('oneline', w=self.w)
        if not entity.canonical:
            canonemailaddr = entity.canonical_form()
            if canonemailaddr:
                self.w(u'&nbsp;(<i>%s</i>)' % canonemailaddr.view('oneline'))
            self.w(u'</h3>')
        elif entity.identical_to:
            self.w(u'</h3>')
            identicaladdr = [e.view('oneline') for e in entity.identical_to]
            self.field('identical_to', ', '.join(identicaladdr))
        else:
            self.w(u'</h3>')
        try:
            persons = entity.reverse_primary_email
        except Unauthorized:
            persons = []
        if persons:
            emailof = persons[0]
            self.field(display_name(self.req, 'primary_email', 'object'), emailof.view('oneline'))
            pemaileid = emailof.eid
        else:
            pemaileid = None
        try:
            emailof = 'use_email' in self.schema and entity.reverse_use_email or ()
            emailof = [e for e in emailof if not e.eid == pemaileid]
        except Unauthorized:
            emailof = []
        if emailof:
            emailofstr = ', '.join(e.view('oneline') for e in emailof)
            self.field(display_name(self.req, 'use_email', 'object'), emailofstr)

    def render_entity_relations(self, entity, siderelations):
        for i, email in enumerate(entity.related_emails(self.skipeids)):
            self.w(u'<div class="%s">' % (i%2 and 'even' or 'odd'))
            email.view('oneline', w=self.w, contexteid=entity.eid)
            self.w(u'</div>')


class EmailAddressShortPrimaryView(EmailAddressPrimaryView):
    __select__ = implements('EmailAddress')
    id = 'shortprimary'
    title = None # hidden view
    def render_entity_attributes(self, entity, siderelations):
        self.w(u'<h5>')
        entity.view('oneline', w=self.w)
        self.w(u'</h5>')

    
class EmailAddressOneLineView(baseviews.OneLineView):
    __select__ = implements('EmailAddress')
    
    def cell_call(self, row, col, **kwargs):
        entity = self.entity(row, col)
        if entity.reverse_primary_email:
            self.w(u'<b>')
        if entity.alias:
            self.w(u'%s &lt;' % html_escape(entity.alias))
        self.w('<a href="%s">%s</a>' % (html_escape(entity.absolute_url()),
                                        html_escape(entity.display_address())))
        if entity.alias:
            self.w(u'&gt;\n')
        if entity.reverse_primary_email:
            self.w(u'</b>')

class EmailAddressMailToView(baseviews.OneLineView):
    """A one line view that builds a user clickable URL for an email with
    'mailto:'"""

    id = 'mailto'
    __select__ = implements('EmailAddress')
    
    def cell_call(self, row, col, **kwargs):
        entity = self.entity(row, col)
        if entity.reverse_primary_email:
            self.w(u'<b>')
        if entity.alias:
            mailto = u'%s <%s>' % (entity.alias, entity.display_address())
        elif entity.reverse_use_email:
            mailto = "mailto:%s <%s>" % \
                (entity.reverse_use_email[0].dc_title(),
                 entity.display_address())
        else:
            mailto = "mailto:%s" % entity.display_address()
        self.w(u'<a href="%s">%s</a>' % (html_escape(mailto),
                                         html_escape(entity.display_address())))
            
        if entity.alias:
            self.w(u'&gt;\n')
        if entity.reverse_primary_email:
            self.w(u'</b>')

    
class EmailAddressTextView(baseviews.TextView):
    __select__ = implements('EmailAddress')
    
    def cell_call(self, row, col, **kwargs):
        self.w(self.entity(row, col).display_address())
