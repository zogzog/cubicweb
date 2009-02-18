"""base xml and rss views


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from time import timezone

from logilab.mtconverter import xml_escape

from cubicweb.view import EntityView, AnyRsetView
from cubicweb.web.httpcache import MaxAgeHTTPCacheManager
from cubicweb.common.uilib import simple_sgml_tag


class XmlView(EntityView):
    """xml view for entities"""
    id = 'xml'
    title = _('xml')
    templatable = False
    content_type = 'text/xml'
    xml_root = 'rset'
    item_vid = 'xmlitem'
    
    def cell_call(self, row, col):
        self.wview(self.item_vid, self.rset, row=row, col=col)
        
    def call(self):
        """display a list of entities by calling their <item_vid> view"""
        self.w(u'<?xml version="1.0" encoding="%s"?>\n' % self.req.encoding)
        self.w(u'<%s size="%s">\n' % (self.xml_root, len(self.rset)))
        for i in xrange(self.rset.rowcount):
            self.cell_call(i, 0)
        self.w(u'</%s>\n' % self.xml_root)


class XmlItemView(EntityView):
    id = 'xmlitem'

    def cell_call(self, row, col):
        """ element as an item for an xml feed """
        entity = self.complete_entity(row, col)
        self.w(u'<%s>\n' % (entity.e_schema))
        for rschema, attrschema in entity.e_schema.attribute_definitions():
            attr = rschema.type
            try:
                value = entity[attr]
            except KeyError:
                # Bytes
                continue
            if value is not None:
                if attrschema == 'Bytes':
                    from base64 import b64encode
                    value = '<![CDATA[%s]]>' % b64encode(value.getvalue())
                elif isinstance(value, basestring):
                    value = xml_escape(value)
                self.w(u'  <%s>%s</%s>\n' % (attr, value, attr))
        self.w(u'</%s>\n' % (entity.e_schema))


    
class XmlRsetView(AnyRsetView):
    """dumps raw rset as xml"""
    id = 'rsetxml'
    title = _('xml export')
    templatable = False
    content_type = 'text/xml'
    xml_root = 'rset'
        
    def call(self):
        w = self.w
        rset, descr = self.rset, self.rset.description
        eschema = self.schema.eschema
        labels = self.columns_labels(False)
        w(u'<?xml version="1.0" encoding="%s"?>\n' % self.req.encoding)
        w(u'<%s query="%s">\n' % (self.xml_root, xml_escape(rset.printable_rql())))
        for rowindex, row in enumerate(self.rset):
            w(u' <row>\n')
            for colindex, val in enumerate(row):
                etype = descr[rowindex][colindex]
                tag = labels[colindex]
                attrs = {}
                if '(' in tag:
                    attrs['expr'] = tag
                    tag = 'funccall'
                if val is not None and not eschema(etype).is_final():
                    attrs['eid'] = val
                    # csvrow.append(val) # val is eid in that case
                    val = self.view('textincontext', rset,
                                    row=rowindex, col=colindex)
                else:
                    val = self.view('final', rset, displaytime=True,
                                    row=rowindex, col=colindex, format='text/plain')
                w(simple_sgml_tag(tag, val, **attrs))
            w(u' </row>\n')
        w(u'</%s>\n' % self.xml_root)
    

class RssView(XmlView):
    id = 'rss'
    title = _('rss')
    templatable = False
    content_type = 'text/xml'
    http_cache_manager = MaxAgeHTTPCacheManager
    cache_max_age = 60*60*2 # stay in http cache for 2 hours by default 
    
    def cell_call(self, row, col):
        self.wview('rssitem', self.rset, row=row, col=col)
        
    def call(self):
        """display a list of entities by calling their <item_vid> view"""
        req = self.req
        self.w(u'<?xml version="1.0" encoding="%s"?>\n' % req.encoding)
        self.w(u'''<rdf:RDF
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns="http://purl.org/rss/1.0/"
>''')
        self.w(u'  <channel rdf:about="%s">\n' % xml_escape(req.url()))
        self.w(u'    <title>%s RSS Feed</title>\n' % xml_escape(self.page_title()))
        self.w(u'    <description>%s</description>\n' % xml_escape(req.form.get('vtitle', '')))
        params = req.form.copy()
        params.pop('vid', None)
        self.w(u'    <link>%s</link>\n' % xml_escape(self.build_url(**params)))
        self.w(u'    <items>\n')
        self.w(u'      <rdf:Seq>\n')
        for entity in self.rset.entities():
            self.w(u'      <rdf:li resource="%s" />\n' % xml_escape(entity.absolute_url()))
        self.w(u'      </rdf:Seq>\n')
        self.w(u'    </items>\n')
        self.w(u'  </channel>\n')
        for i in xrange(self.rset.rowcount):
            self.cell_call(i, 0)
        self.w(u'</rdf:RDF>')


class RssItemView(EntityView):
    id = 'rssitem'
    date_format = '%%Y-%%m-%%dT%%H:%%M%+03i:00' % (timezone / 3600)

    def cell_call(self, row, col):
        entity = self.complete_entity(row, col)
        self.w(u'<item rdf:about="%s">\n' % xml_escape(entity.absolute_url()))
        self._marker('title', entity.dc_long_title())
        self._marker('link', entity.absolute_url())
        self._marker('description', entity.dc_description())
        self._marker('dc:date', entity.dc_date(self.date_format))
        if entity.creator:
            self.w(u'<author>')
            self._marker('name', entity.creator.name())
            email = entity.creator.get_email()
            if email:
                self._marker('email', email)
            self.w(u'</author>')
        self.w(u'</item>\n')
        
    def _marker(self, marker, value):
        if value:
            self.w(u'  <%s>%s</%s>\n' % (marker, xml_escape(value), marker))
