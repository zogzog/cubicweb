"""Specific views for SIOC interfaces

:organization: Logilab
:copyright: 2003-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape

from cubicweb.view import EntityView
from cubicweb.selectors import implements
from cubicweb.interfaces import ISiocItem, ISiocContainer

class SIOCView(EntityView):
    id = 'sioc'
    __select__ = EntityView.__select__ & implements(ISiocItem, ISiocContainer)
    title = _('sioc')
    templatable = False
    content_type = 'text/xml'

    def call(self):
        self.w(u'<?xml version="1.0" encoding="%s"?>\n' % self.req.encoding)
        self.w(u'''<rdf:RDF
             xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
             xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
             xmlns:owl="http://www.w3.org/2002/07/owl#"
             xmlns:foaf="http://xmlns.com/foaf/0.1/"
             xmlns:sioc="http://rdfs.org/sioc/ns#"
             xmlns:sioctype="http://rdfs.org/sioc/types#"
             xmlns:dcterms="http://purl.org/dc/terms/">\n''')
        for i in xrange(self.rset.rowcount):
            self.cell_call(i, 0)
        self.w(u'</rdf:RDF>\n')

    def cell_call(self, row, col):
        self.wview('sioc_element', self.rset, row=row, col=col)

class SIOCContainerView(EntityView):
    id = 'sioc_element'
    __select__ = EntityView.__select__ & implements(ISiocContainer)
    templatable = False
    content_type = 'text/xml'

    def cell_call(self, row, col):
        entity = self.complete_entity(row, col)
        sioct = html_escape(entity.isioc_type())
        self.w(u'<sioc:%s rdf:about="%s">\n'
               % (sioct, html_escape(entity.absolute_url())))
        self.w(u'<dcterms:title>%s</dcterms:title>'
               % html_escape(entity.dc_title()))
        self.w(u'<dcterms:created>%s</dcterms:created>'
               % entity.creation_date)
        self.w(u'<dcterms:modified>%s</dcterms:modified>'
               % entity.modification_date)
        self.w(u'<!-- FIXME : here be items -->')#entity.isioc_items()
        self.w(u'</sioc:%s>\n' % sioct)


class SIOCItemView(EntityView):
    id = 'sioc_element'
    __select__ = EntityView.__select__ & implements(ISiocItem)
    templatable = False
    content_type = 'text/xml'

    def cell_call(self, row, col):
        entity = self.complete_entity(row, col)
        sioct = html_escape(entity.isioc_type())
        self.w(u'<sioc:%s rdf:about="%s">\n'
               %  (sioct, html_escape(entity.absolute_url())))
        self.w(u'<dcterms:title>%s</dcterms:title>'
               % html_escape(entity.dc_title()))
        self.w(u'<dcterms:created>%s</dcterms:created>'
               % entity.creation_date)
        self.w(u'<dcterms:modified>%s</dcterms:modified>'
               % entity.modification_date)
        if entity.content:
            self.w(u'<sioc:content>%s</sioc:content>'''
                   % html_escape(entity.isioc_content()))
        if entity.related('entry_of'):
            self.w(u'<sioc:has_container rdf:resource="%s"/>\n'
                   % html_escape(entity.isioc_container().absolute_url()))
        if entity.creator:
            self.w(u'<sioc:has_creator>\n')
            self.w(u'<sioc:User rdf:about="%s">\n'
                   % html_escape(entity.creator.absolute_url()))
            self.w(entity.creator.view('foaf'))
            self.w(u'</sioc:User>\n')
            self.w(u'</sioc:has_creator>\n')
        self.w(u'<!-- FIXME : here be topics -->')#entity.isioc_topics()
        self.w(u'<!-- FIXME : here be replies -->')#entity.isioc_replies()
        self.w(u' </sioc:%s>\n' % sioct)

