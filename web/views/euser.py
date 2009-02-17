"""Specific views for users

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.common.decorators import cached
from logilab.mtconverter import html_escape

from cubicweb.schema import display_name
from cubicweb.common.selectors import one_line_rset, implements, match_user_groups
from cubicweb.web import INTERNAL_FIELD_VALUE
from cubicweb.web.form import EntityForm
from cubicweb.web.action import Action
from cubicweb.web.views.baseviews import PrimaryView, EntityView


class UserPreferencesEntityAction(Action):
    id = 'prefs'
    __selectors__ = (one_line_rset, implements('EUser'),
                     match_user_groups('owners', 'managers'))
    
    title = _('preferences')
    category = 'mainactions'
    
    def url(self):
        login = self.rset.get_entity(self.row or 0, self.col or 0).login
        return self.build_url('euser/%s'%login, vid='epropertiesform')


class EUserPrimaryView(PrimaryView):
    __selectors__ = (implements('EUser'),)
    
    skip_attrs = ('firstname', 'surname')
    
    def iter_relations(self, entity):
        # don't want to display user's entities
        for rschema, targetschemas, x in super(EUserPrimaryView, self).iter_relations(entity):
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
    __selectors__ = (implements('EUser'),)
    
    title = _('foaf')
    templatable = False
    content_type = 'text/xml'

    def call(self):
        self.w('''<?xml version="1.0" encoding="%s"?>
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


class FoafUsableView(FoafView):
    id = 'foaf_usable'
  
    def call(self):
        self.cell_call(0, 0)

            
class EditGroups(EntityForm):
    """displays a simple euser / egroups editable table"""
    
    id = 'editgroups'
    accepts = ('EUser',)
    
    def call(self):
        self.req.add_css('cubicweb.acl.css')            
        _ = self.req._
        self.w(u'<form id="editgroup" method="post" action="edit">')
        self.w(u'<table id="groupedit">\n')
        self.w(u'<tr>')
        self.w(u'<th>%s</th>' % display_name(self.req, 'EUser'))
        self.w(u''.join(u'<th>%s</th>' % _(gname) for geid, gname in self.egroups))
        self.w(u'</tr>')
        for row in xrange(len(self.rset)):
            self.build_table_line(row)
        self.w(u'</table>')
        self.w(u'<fieldset>')
        self.w(self.button_cancel())
        self.w(self.button_ok())
        self.w(u'</fieldset>')
        self.w(u'</form>')


    def build_table_line(self, row):
        euser = self.entity(row)
        euser_groups = [group.name for group in euser.in_group]
        if euser_groups:
            self.w(u'<tr>')
        else:
            self.w(u'<tr class="nogroup">')
        self.w(u'<th><fieldset>')
        self.w(u'<input type="hidden" name="eid" value="%s" />' % euser.eid)
        self.w(u'<input type="hidden" name="__type:%s" value="EUser" />' % euser.eid)
        # this should not occur (for now) since in_group relation is mandatory
        if not euser_groups:
            self.w(u'<input type="hidden" name="edits-in_group:%s" value="%s">' %
                   (euser.eid, INTERNAL_FIELD_VALUE))
        self.w(euser.dc_title())
        self.w(u'</fieldset></th>')
        for geid, gname in self.egroups:
            self.w(u'<td><fieldset>')
            if gname in euser_groups:
                self.w(u'<input type="hidden" name="edits-in_group:%s" value="%s" />' %
                       (euser.eid, geid))
                self.w(u'<input type="checkbox" name="in_group:%s" value="%s" checked="checked" />' %
                       (euser.eid, geid))
            else:
                self.w(u'<input type="checkbox" name="in_group:%s" value="%s" />' %
                       (euser.eid, geid))
            self.w(u'</fieldset></td>')
        self.w(u'</tr>\n')

        
    @property
    @cached
    def egroups(self):
        groups = self.req.execute('Any G, N ORDERBY N WHERE G is EGroup, G name N')
        return [(geid, gname) for geid, gname in groups.rows if gname != 'owners']
                
        
