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
"""Specific views for SIOC (Semantically-Interlinked Online Communities)

http://sioc-project.org
"""

__docformat__ = "restructuredtext en"
_ = unicode

from logilab.mtconverter import xml_escape

from cubicweb.view import EntityView, EntityAdapter, implements_adapter_compat
from cubicweb.selectors import implements, adaptable
from cubicweb.interfaces import ISiocItem, ISiocContainer


class ISIOCItemAdapter(EntityAdapter):
    """interface for entities which may be represented as an ISIOC items"""
    __regid__ = 'ISIOCItem'
    __select__ = implements(ISiocItem, warn=False) # XXX for bw compat, should be abstract

    @implements_adapter_compat('ISIOCItem')
    def isioc_content(self):
        """return item's content"""
        raise NotImplementedError

    @implements_adapter_compat('ISIOCItem')
    def isioc_container(self):
        """return container entity"""
        raise NotImplementedError

    @implements_adapter_compat('ISIOCItem')
    def isioc_type(self):
        """return container type (post, BlogPost, MailMessage)"""
        raise NotImplementedError

    @implements_adapter_compat('ISIOCItem')
    def isioc_replies(self):
        """return replies items"""
        raise NotImplementedError

    @implements_adapter_compat('ISIOCItem')
    def isioc_topics(self):
        """return topics items"""
        raise NotImplementedError


class ISIOCContainerAdapter(EntityAdapter):
    """interface for entities which may be represented as an ISIOC container"""
    __regid__ = 'ISIOCContainer'
    __select__ = implements(ISiocContainer, warn=False) # XXX for bw compat, should be abstract

    @implements_adapter_compat('ISIOCContainer')
    def isioc_type(self):
        """return container type (forum, Weblog, MailingList)"""
        raise NotImplementedError

    @implements_adapter_compat('ISIOCContainer')
    def isioc_items(self):
        """return contained items"""
        raise NotImplementedError


class SIOCView(EntityView):
    __regid__ = 'sioc'
    __select__ = adaptable('ISIOCItem', 'ISIOCContainer')
    title = _('sioc')
    templatable = False
    content_type = 'text/xml'

    def call(self):
        self.w(u'<?xml version="1.0" encoding="%s"?>\n' % self._cw.encoding)
        self.w(u'''<rdf:RDF
             xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
             xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
             xmlns:owl="http://www.w3.org/2002/07/owl#"
             xmlns:foaf="http://xmlns.com/foaf/0.1/"
             xmlns:sioc="http://rdfs.org/sioc/ns#"
             xmlns:sioctype="http://rdfs.org/sioc/types#"
             xmlns:dcterms="http://purl.org/dc/terms/">\n''')
        for i in xrange(self.cw_rset.rowcount):
            self.cell_call(i, 0)
        self.w(u'</rdf:RDF>\n')

    def cell_call(self, row, col):
        self.wview('sioc_element', self.cw_rset, row=row, col=col)

class SIOCContainerView(EntityView):
    __regid__ = 'sioc_element'
    __select__ = adaptable('ISIOCContainer')
    templatable = False
    content_type = 'text/xml'

    def cell_call(self, row, col):
        entity = self.cw_rset.complete_entity(row, col)
        isioc = entity.cw_adapt_to('ISIOCContainer')
        isioct = isioc.isioc_type()
        self.w(u'<sioc:%s rdf:about="%s">\n'
               % (isioct, xml_escape(entity.absolute_url())))
        self.w(u'<dcterms:title>%s</dcterms:title>'
               % xml_escape(entity.dc_title()))
        self.w(u'<dcterms:created>%s</dcterms:created>'
               % entity.creation_date) # XXX format
        self.w(u'<dcterms:modified>%s</dcterms:modified>'
               % entity.modification_date) # XXX format
        self.w(u'<!-- FIXME : here be items -->')#entity.isioc_items()
        self.w(u'</sioc:%s>\n' % isioct)


class SIOCItemView(EntityView):
    __regid__ = 'sioc_element'
    __select__ = adaptable('ISIOCItem')
    templatable = False
    content_type = 'text/xml'

    def cell_call(self, row, col):
        entity = self.cw_rset.complete_entity(row, col)
        isioc = entity.cw_adapt_to('ISIOCItem')
        isioct = isioc.isioc_type()
        self.w(u'<sioc:%s rdf:about="%s">\n'
               % (isioct, xml_escape(entity.absolute_url())))
        self.w(u'<dcterms:title>%s</dcterms:title>'
               % xml_escape(entity.dc_title()))
        self.w(u'<dcterms:created>%s</dcterms:created>'
               % entity.creation_date) # XXX format
        self.w(u'<dcterms:modified>%s</dcterms:modified>'
               % entity.modification_date) # XXX format
        content = isioc.isioc_content()
        if content:
            self.w(u'<sioc:content>%s</sioc:content>' % xml_escape(content))
        container = isioc.isioc_container()
        if container:
            self.w(u'<sioc:has_container rdf:resource="%s"/>\n'
                   % xml_escape(container.absolute_url()))
        if entity.creator:
            self.w(u'<sioc:has_creator>\n')
            self.w(u'<sioc:User rdf:about="%s">\n'
                   % xml_escape(entity.creator.absolute_url()))
            self.w(entity.creator.view('foaf'))
            self.w(u'</sioc:User>\n')
            self.w(u'</sioc:has_creator>\n')
        self.w(u'<!-- FIXME : here be topics -->')#entity.isioc_topics()
        self.w(u'<!-- FIXME : here be replies -->')#entity.isioc_replies()
        self.w(u' </sioc:%s>\n' % isioct)

