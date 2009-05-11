"""Specific views for users

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape

from cubicweb.selectors import one_line_rset, implements, match_user_groups
from cubicweb.view import EntityView
from cubicweb.web import uicfg, action
from cubicweb.web.views import primary


uicfg.rcategories.tag_relation('secondary', ('CWUser', 'firstname', '*'), 'subject')
uicfg.rcategories.tag_relation('secondary', ('CWUser', 'surname', '*'), 'subject')
uicfg.rcategories.tag_relation('metadata', ('CWUser', 'last_login_time', '*'), 'subject')
uicfg.rcategories.tag_relation('primary', ('CWUser', 'in_group', '*'), 'subject')
uicfg.rcategories.tag_relation('generated', ('*', 'owned_by', 'CWUser'), 'object')
uicfg.rcategories.tag_relation('generated', ('*', 'created_by', 'CWUser'), 'object')
uicfg.rcategories.tag_relation('metadata', ('*', 'bookmarked_by', 'CWUser'), 'object')
uicfg.rmode.tag_relation('create', ('*', 'in_group', 'CWGroup'), 'object')
uicfg.rmode.tag_relation('link', ('*', 'owned_by', 'CWUser'), 'object')
uicfg.rmode.tag_relation('link', ('*', 'created_by', 'CWUser'), 'object')
uicfg.rmode.tag_relation('create', ('*', 'bookmarked_by', 'CWUser'), 'object')
uicfg.rdisplay.tag_attribute({}, 'CWUser', 'firstname')
uicfg.rdisplay.tag_attribute({}, 'CWUser', 'surname')


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
        self.w(u'<foaf:name>%s</foaf:name>\n' % html_escape(entity.dc_long_title()))
        if entity.surname:
            self.w(u'<foaf:family_name>%s</foaf:family_name>\n'
                   % html_escape(entity.surname))
        if entity.firstname:
            self.w(u'<foaf:givenname>%s</foaf:givenname>\n'
                   % html_escape(entity.firstname))
        emailaddr = entity.get_email()
        if emailaddr:
            self.w(u'<foaf:mbox>%s</foaf:mbox>\n' % html_escape(emailaddr))
        self.w(u'</foaf:Person>\n')

from logilab.common.deprecation import class_renamed
EUserPrimaryView = class_renamed('EUserPrimaryView', CWUserPrimaryView)
