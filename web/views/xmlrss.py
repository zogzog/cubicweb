"""base xml and rss views

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from time import timezone

from logilab.mtconverter import xml_escape

from cubicweb.selectors import non_final_entity, one_line_rset, appobject_selectable
from cubicweb.view import EntityView, AnyRsetView, Component
from cubicweb.common.uilib import simple_sgml_tag
from cubicweb.web import httpcache, box


# base xml views ##############################################################

class XMLView(EntityView):
    """xml view for entities"""
    __regid__ = 'xml'
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


class XMLItemView(EntityView):
    __regid__ = 'xmlitem'

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


class XMLRsetView(AnyRsetView):
    """dumps raw rset as xml"""
    __regid__ = 'rsetxml'
    title = _('xml export')
    templatable = False
    content_type = 'text/xml'
    xml_root = 'rset'

    def call(self):
        w = self.w
        rset, descr = self.rset, self.rset.description
        eschema = self.schema.eschema
        labels = self.columns_labels(tr=False)
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
                    val = self.view('final', rset, row=rowindex,
                                    col=colindex, format='text/plain')
                w(simple_sgml_tag(tag, val, **attrs))
            w(u' </row>\n')
        w(u'</%s>\n' % self.xml_root)


# RSS stuff ###################################################################

class RSSFeedURL(Component):
    __regid__ = 'rss_feed_url'
    __select__ = non_final_entity()

    def feed_url(self):
        return self.build_url(rql=self.limited_rql(), vid='rss')


class RSSEntityFeedURL(Component):
    __regid__ = 'rss_feed_url'
    __select__ = non_final_entity() & one_line_rset()

    def feed_url(self):
        return self.rset.get_entity(0, 0).rss_feed_url()


class RSSIconBox(box.BoxTemplate):
    """just display the RSS icon on uniform result set"""
    __regid__ = 'rss'
    __select__ = (box.BoxTemplate.__select__
                  & appobject_selectable('components', 'rss_feed_url'))

    visible = False
    order = 999

    def call(self, **kwargs):
        try:
            rss = self.req.external_resource('RSS_LOGO')
        except KeyError:
            self.error('missing RSS_LOGO external resource')
            return
        urlgetter = self.vreg['components'].select('rss_feed_url', self.req,
                                                   rset=self.rset)
        url = urlgetter.feed_url()
        self.w(u'<a href="%s"><img src="%s" alt="rss"/></a>\n' % (xml_escape(url), rss))


class RSSView(XMLView):
    __regid__ = 'rss'
    title = _('rss')
    templatable = False
    content_type = 'text/xml'
    http_cache_manager = httpcache.MaxAgeHTTPCacheManager
    cache_max_age = 60*60*2 # stay in http cache for 2 hours by default

    def _open(self):
        req = self.req
        self.w(u'<?xml version="1.0" encoding="%s"?>\n' % req.encoding)
        self.w(u'<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/">\n')
        self.w(u'  <channel>\n')
        self.w(u'    <title>%s RSS Feed</title>\n'
               % xml_escape(self.page_title()))
        self.w(u'    <description>%s</description>\n'
               % xml_escape(req.form.get('vtitle', '')))
        params = req.form.copy()
        params.pop('vid', None)
        self.w(u'    <link>%s</link>\n' % xml_escape(self.build_url(**params)))

    def _close(self):
        self.w(u'  </channel>\n')
        self.w(u'</rss>')

    def call(self):
        """display a list of entities by calling their <item_vid> view"""
        self._open()
        for i in xrange(self.rset.rowcount):
            self.cell_call(i, 0)
        self._close()

    def cell_call(self, row, col):
        self.wview('rssitem', self.rset, row=row, col=col)


class RSSItemView(EntityView):
    __regid__ = 'rssitem'
    date_format = '%%Y-%%m-%%dT%%H:%%M%+03i:00' % (timezone / 3600)
    add_div_section = False

    def cell_call(self, row, col):
        entity = self.complete_entity(row, col)
        self.w(u'<item>\n')
        self.w(u'<guid isPermaLink="true">%s</guid>\n'
               % xml_escape(entity.absolute_url()))
        self.render_title_link(entity)
        self._marker('description', entity.dc_description(format='text/html'))
        self._marker('dc:date', entity.dc_date(self.date_format))
        self.render_entity_creator(entity)
        self.w(u'</item>\n')

    def render_title_link(self, entity):
        self._marker('title', entity.dc_long_title())
        self._marker('link', entity.absolute_url())

    def render_entity_creator(self, entity):
        if entity.creator:
            self._marker('dc:creator', entity.dc_creator())


    def _marker(self, marker, value):
        if value:
            self.w(u'  <%s>%s</%s>\n' % (marker, xml_escape(value), marker))
