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
"""overrides some base views for cubicweb on google appengine

"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import xml_escape

from cubicweb import typed_eid
from cubicweb.selectors import one_line_rset, match_search_state, accept
from cubicweb.schema import display_name
from cubicweb.view import StartupView, EntityView
from cubicweb.web import Redirect
from cubicweb.web.views import vid_from_rset

from google.appengine.api import mail


class SearchForAssociationView(EntityView):
    """view called by the edition view when the user asks
    to search for something to link to the edited eid
    """
    id = 'search-associate'

    __select__ = one_line_rset() & match_search_state('linksearch') & accept

    def cell_call(self, row, col):
        entity = self.rset.get_entity(0, 0)
        role, eid, rtype, etype = self.req.search_state[1]
        assert entity.eid == typed_eid(eid)
        rset = entity.unrelated(rtype, etype, role, ordermethod='fetch_order')
        vid = vid_from_rset(self.req, rset, self.schema)
        self.w(u'<div id="search-associate-content">')
        self.pagination(self.req, rset, w=self.w)
        self.wview(vid, rset)
        self.w(u'</div>')


class SchemaImageView(StartupView):
    id = 'schemagraph'
    binary = True
    content_type = 'image/png'
    def call(self):
        """display global schema information"""
        skipmeta = int(self.req.form.get('skipmeta', 1))
        if skipmeta:
            url = self.build_url('data/schema.png')
        else:
            url = self.build_url('data/metaschema.png')
        raise Redirect(url)


from cubicweb.web.views.baseviews import MetaDataView

class GAEMetaDataView(MetaDataView):
    show_eid = False


from cubicweb.web.views.startup import ManageView

def entity_types_no_count(self, eschemas):
    """return a list of formatted links to get a list of entities of
    a each entity's types
    """
    req = self.req
    for eschema in eschemas:
        if eschema.final or not (eschema.has_perm(req, 'read') or
                                      eschema.has_local_role('read')):
            continue
        etype = eschema.type
        label = display_name(req, etype, 'plural')
        view = self.vreg.select('views', 'list', req, req.etype_rset(etype))
        url = view.url()
        etypelink = u'&#160;<a href="%s">%s</a>' % (xml_escape(url), label)
        yield (label, etypelink, self.add_entity_link(eschema, req))

ManageView.entity_types = entity_types_no_count


from cubicweb.web.views.basecontrollers import SendMailController

def sendmail(self, recipient, subject, body):
    sender = '%s <%s>' % (
        self.req.user.dc_title() or self.config['sender-name'],
        self.req.user.get_email() or self.config['sender-addr'])
    mail.send_mail(sender=sender, to=recipient,
                   subject=subject, body=body)

SendMailController.sendmail = sendmail
