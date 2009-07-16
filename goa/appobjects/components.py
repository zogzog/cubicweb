"""overrides some base views for cubicweb on google appengine

:organization: Logilab
:copyright: 2008-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import xml_escape

from cubicweb import typed_eid
from cubicweb.selectors import one_line_rset, match_search_state, accept
from cubicweb.schema import display_name
from cubicweb.common.view import StartupView, EntityView
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
        entity = self.entity(0, 0)
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
        if eschema.is_final() or not (eschema.has_perm(req, 'read') or
                                      eschema.has_local_role('read')):
            continue
        etype = eschema.type
        label = display_name(req, etype, 'plural')
        view = self.vreg.select('views', 'list', req, req.etype_rset(etype))
        url = view.url()
        etypelink = u'&nbsp;<a href="%s">%s</a>' % (xml_escape(url), label)
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
