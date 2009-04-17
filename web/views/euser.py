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
from cubicweb.web.views.baseviews import PrimaryView


uicfg.rcategories.set_rtag('secondary', 'firstname', 'subject', 'CWUser')
uicfg.rcategories.set_rtag('secondary', 'surname', 'subject', 'CWUser')
uicfg.rcategories.set_rtag('metadata', 'last_login_time', 'subject', 'CWUser')
uicfg.rcategories.set_rtag('primary', 'in_group', 'subject', 'CWUser')
uicfg.rcategories.set_rtag('generated', 'owned_by', 'object', otype='CWUser')
uicfg.rcategories.set_rtag('generated', 'created_by', 'object', otype='CWUser')
uicfg.rcategories.set_rtag('metadata', 'bookmarked_by', 'object', otype='CWUser')
uicfg.rinlined.set_rtag(True, 'use_email', 'subject', 'CWUser')
uicfg.rmode.set_rtag('create', 'in_group', 'subject', 'CWGroup')
uicfg.rmode.set_rtag('link', 'owned_by', 'object', 'CWUser')
uicfg.rmode.set_rtag('link', 'created_by', 'object', 'CWUser')
uicfg.rmode.set_rtag('create', 'bookmarked_by', 'object', 'CWUser')
    

class UserPreferencesEntityAction(action.Action):
    id = 'prefs'
    __select__ = (one_line_rset() & implements('CWUser') &
                  match_user_groups('owners', 'managers'))
    
    title = _('preferences')
    category = 'mainactions'
    
    def url(self):
        login = self.rset.get_entity(self.row or 0, self.col or 0).login
        return self.build_url('euser/%s'%login, vid='epropertiesform')


class CWUserPrimaryView(PrimaryView):
    __select__ = implements('CWUser')
    
    skip_attrs = ('firstname', 'surname')
    
    def iter_relations(self, entity):
        # don't want to display user's entities
        for rschema, targetschemas, x in super(CWUserPrimaryView, self).iter_relations(entity):
            if x == 'object' and rschema.type in ('owned_by', 'for_user'):
                continue
            yield rschema, targetschemas, x

    def content_title(self, entity):
        return entity.name()

    def is_side_related(self, rschema, eschema):
        return  rschema.type in ['interested_in', 'tags', 
                                 'todo_by', 'bookmarked_by',

                                 ]
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
