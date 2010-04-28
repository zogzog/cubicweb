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
"""Specific views for email addresses entities

"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import xml_escape

from cubicweb.schema import display_name
from cubicweb.selectors import implements
from cubicweb import Unauthorized
from cubicweb.web import uicfg
from cubicweb.web.views import baseviews, primary

_pvs = uicfg.primaryview_section
_pvs.tag_subject_of(('*', 'use_email', '*'), 'attributes')
_pvs.tag_subject_of(('*', 'primary_email', '*'), 'hidden')

class EmailAddressPrimaryView(primary.PrimaryView):
    __select__ = implements('EmailAddress')

    def cell_call(self, row, col, skipeids=None):
        self.skipeids = skipeids
        super(EmailAddressPrimaryView, self).cell_call(row, col)

    def render_entity_attributes(self, entity):
        self.w(u'<h3>')
        entity.view('oneline', w=self.w)
        if entity.prefered:
            self.w(u'&#160;(<i>%s</i>)' % entity.prefered.view('oneline'))
        self.w(u'</h3>')
        try:
            persons = entity.reverse_primary_email
        except Unauthorized:
            persons = []
        if persons:
            emailof = persons[0]
            self.field(display_name(self._cw, 'primary_email', 'object'), emailof.view('oneline'))
            pemaileid = emailof.eid
        else:
            pemaileid = None
        try:
            emailof = 'use_email' in self._cw.vreg.schema and entity.reverse_use_email or ()
            emailof = [e for e in emailof if not e.eid == pemaileid]
        except Unauthorized:
            emailof = []
        if emailof:
            emailofstr = ', '.join(e.view('oneline') for e in emailof)
            self.field(display_name(self._cw, 'use_email', 'object'), emailofstr)

    def render_entity_relations(self, entity):
        for i, email in enumerate(entity.related_emails(self.skipeids)):
            self.w(u'<div class="%s">' % (i%2 and 'even' or 'odd'))
            email.view('oneline', w=self.w, contexteid=entity.eid)
            self.w(u'</div>')


class EmailAddressShortPrimaryView(EmailAddressPrimaryView):
    __select__ = implements('EmailAddress')
    __regid__ = 'shortprimary'
    title = None # hidden view

    def render_entity_attributes(self, entity):
        self.w(u'<h5>')
        entity.view('oneline', w=self.w)
        self.w(u'</h5>')


class EmailAddressOneLineView(baseviews.OneLineView):
    __select__ = implements('EmailAddress')

    def cell_call(self, row, col, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        if entity.reverse_primary_email:
            self.w(u'<b>')
        if entity.alias:
            self.w(u'%s &lt;' % xml_escape(entity.alias))
        self.w('<a href="%s">%s</a>' % (xml_escape(entity.absolute_url()),
                                        xml_escape(entity.display_address())))
        if entity.alias:
            self.w(u'&gt;\n')
        if entity.reverse_primary_email:
            self.w(u'</b>')


class EmailAddressMailToView(baseviews.OneLineView):
    """A one line view that builds a user clickable URL for an email with
    'mailto:'"""

    __regid__ = 'mailto'
    __select__ = implements('EmailAddress')

    def cell_call(self, row, col, **kwargs):
        entity = self.cw_rset.get_entity(row, col)
        if entity.reverse_primary_email:
            self.w(u'<b>')
        if entity.alias:
            alias = entity.alias
        elif entity.reverse_use_email:
            alias = entity.reverse_use_email[0].dc_title()
        else:
            alias = None
        if alias:
            mailto = "mailto:%s <%s>" % (alias, entity.display_address())
        else:
            mailto = "mailto:%s" % entity.display_address()
        self.w(u'<a href="%s">%s</a>' % (xml_escape(mailto),
                                         xml_escape(entity.display_address())))
        if entity.reverse_primary_email:
            self.w(u'</b>')


class EmailAddressInContextView(baseviews.InContextView):
    __select__ = implements('EmailAddress')

    def cell_call(self, row, col, **kwargs):
        self.wview('mailto', self.cw_rset, row=row, col=col, **kwargs)


class EmailAddressTextView(baseviews.TextView):
    __select__ = implements('EmailAddress')

    def cell_call(self, row, col, **kwargs):
        self.w(self.cw_rset.get_entity(row, col).display_address())
