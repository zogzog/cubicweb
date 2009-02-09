from logilab.mtconverter import html_escape

from cubicweb.common.view import EntityView

from urlparse import urlparse

class LinkedDataProjectView(EntityView):
    id = 'project_linked_data'
    title = _('Project linked data')
    accepts = ('Project',)
    templatable = False
    content_type = 'text/xml'

    def call(self):
        '''display all project attribut and project dependencies and external project (in doap format) if
        it is related to'''

        self.w(u'<?xml version="1.0" encoding="%s"?>\n' % self.req.encoding)
        self.w(u'''<rdf:RDF
            xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
            xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
            xmlns:owl="http://www.w3.org/2002/07/owl#"
            xmlns:doap="http://usefulinc.com/ns/doap#"
            >\n''')
        for i in xrange(self.rset.rowcount):
            self.cell_call(row=i, col=0)
        self.w(u'</rdf:RDF>\n')
            
    def cell_call(self, row, col):
        self.wview('project_linked_data_item', self.rset, row=row, col=col)
    
class LinkedDataProjectItemView(EntityView):
    id = 'project_linked_data_item'
    accepts = ('Project',)

    def cell_call(self, row, col):
        entity = self.complete_entity(row, col)
        self.w(u'<Project rdf:about="%s">\n' % html_escape(entity.absolute_url()))
        self.w(u'  <name>%s</name>\n' % html_escape(unicode(entity.dc_title())))
        self.w(u'  <doap:created>%s</doap:created>\n' % (entity.creation_date.strftime('%Y-%m-%d')))
        self.w(u'  <summary>%s</summary>\n' % html_escape(unicode(entity.summary)))
        self.w(u'  <doap:description>%s</doap:description>\n' % html_escape(unicode(entity.description)))           
        self.w(u'  <url>%s</url>\n' % html_escape(entity.url or entity.absolute_url()))
        if entity.modification_date:
            self.w(u'<doap:revision>%s</doap:revision>\n'% (entity.modification_date.strftime('%Y-%m-%d')))
        if entity.vcsurl:
            self.w(u'''<vcurl>
                          <doap:browse rdf:resource="%s" />
                       </vcurl>''' % html_escape(entity.vcsurl))
        if entity.reporturl:
            self.w(u'<reporturl>"%s"</vcurl>' % html_escape(entity.vcsurl))             
        
        if entity.downloadurl:
            self.w(u'  <doap:file-release>%s</doap:file-release>\n' % html_escape(entity.downloadurl))
        liste = urlparse(entity.absolute_url())
        internal_address = liste[1]
        for externalproject in entity.uses:
            self.w(u'<uses>\n')
            if externalproject.e_schema == 'ExtProject':
                if externalproject.absolute_url().find(internal_address) > 0:
                    self.w(u'<!--wrong external url-->')
                self.w(u' <ExtProject>%s</ExtProject>'% externalproject.absolute_url())
            else:
                self.w(u'<Project>%s</Project>'% externalproject.absolute_url())
            self.w(u'</uses>\n')
        for externalproject in entity.recommends:
            self.w(u'<recommends>\n')
            if externalproject.e_schema == 'ExtProject':
                if externalproject.absolute_url().find(internal_address) > 0:
                    self.w(u'<!--wrong external url-->')
                self.w(u'<ExtProject>%s</ExtProject>'% externalproject.absolute_url())
            else:
                self.w(u'<Project>%s</Project>'% externalproject.absolute_url())                
            self.w(u'%s</recommends>'% externalproject.absolute_url())       

        self.w(u'</Project>\n')

    
