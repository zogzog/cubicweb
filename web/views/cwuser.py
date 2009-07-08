"""Specific views for users

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import xml_escape

from cubicweb.selectors import one_line_rset, implements, match_user_groups
from cubicweb.view import EntityView
from cubicweb.web import action
from cubicweb.web.views import primary


class UserPreferencesEntityAction(action.Action):
    id = 'prefs'
    __select__ = (one_line_rset() & implements('CWUser') &
                  match_user_groups('owners', 'managers'))

    title = _('preferences')
    category = 'mainactions'

    def url(self):
        login = self.rset.get_entity(self.row or 0, self.col or 0).login
        return self.build_url('cwuser/%s'%login, vid='epropertiesform')


class FoafView(EntityView):
    id = 'foaf'
    __select__ = implements('CWUser')

    title = _('foaf')
    templatable = False
    content_type = 'text/xml'

    def call(self):
        self.w(u'''<?xml version="1.0" encoding="%s"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:rdfs="http://www.w3org/2000/01/rdf-schema#"
         xmlns:foaf="http://xmlns.com/foaf/0.1/"> '''% self.req.encoding)
        for i in xrange(self.rset.rowcount):
            self.cell_call(i, 0)
        self.w(u'</rdf:RDF>\n')

    def cell_call(self, row, col):
        entity = self.complete_entity(row, col)
        self.w(u'''<foaf:PersonalProfileDocument rdf:about="">
                      <foaf:maker rdf:resource="%s"/>
                      <foaf:primaryTopic rdf:resource="%s"/>
                   </foaf:PersonalProfileDocument>''' % (entity.absolute_url(), entity.absolute_url()))
        self.w(u'<foaf:Person rdf:ID="%s">\n' % entity.eid)
        self.w(u'<foaf:name>%s</foaf:name>\n' % xml_escape(entity.dc_long_title()))
        if entity.surname:
            self.w(u'<foaf:family_name>%s</foaf:family_name>\n'
                   % xml_escape(entity.surname))
        if entity.firstname:
            self.w(u'<foaf:givenname>%s</foaf:givenname>\n'
                   % xml_escape(entity.firstname))
        emailaddr = entity.get_email()
        if emailaddr:
            self.w(u'<foaf:mbox>%s</foaf:mbox>\n' % xml_escape(emailaddr))
        self.w(u'</foaf:Person>\n')
