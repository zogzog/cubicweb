"""Set of HTML generic base views:

* noresult, final
* primary, sidebox
* secondary, oneline, incontext, outofcontext, text
* list
* xml, rss


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
#from __future__ import with_statement

__docformat__ = "restructuredtext en"

from warnings import warn
from time import timezone

from rql import nodes

from logilab.common.decorators import cached
from logilab.mtconverter import TransformError, html_escape, xml_escape

from cubicweb import Unauthorized, NoSelectableObject, typed_eid
from cubicweb.common.selectors import (yes, nonempty_rset, accept,
                                       one_line_rset, match_search_state, 
                                       match_form_params, accept_rset)
from cubicweb.common.uilib import (cut, printable_value,  UnicodeCSVWriter,
                                   ajax_replace_url, rql_for_eid, simple_sgml_tag)
from cubicweb.common.view import EntityView, AnyRsetView, EmptyRsetView
from cubicweb.web.httpcache import MaxAgeHTTPCacheManager
from cubicweb.web.views import vid_from_rset, linksearch_select_url, linksearch_match

_ = unicode

class NullView(AnyRsetView):
    """default view when no result has been found"""
    id = 'null'
    __select__ = classmethod(yes)
    def call(self, **kwargs):
        pass
    cell_call = call


class NoResultView(EmptyRsetView):
    """default view when no result has been found"""
    id = 'noresult'
    
    def call(self, **kwargs):
        self.w(u'<div class="searchMessage"><strong>%s</strong></div>\n'
               % self.req._('No result matching query'))


class FinalView(AnyRsetView):
    """display values without any transformation (i.e. get a number for
    entities) 
    """
    id = 'final'
    # record generated i18n catalog messages
    _('%d&nbsp;years')
    _('%d&nbsp;months')
    _('%d&nbsp;weeks')
    _('%d&nbsp;days')
    _('%d&nbsp;hours')
    _('%d&nbsp;minutes')
    _('%d&nbsp;seconds')
    _('%d years')
    _('%d months')
    _('%d weeks')
    _('%d days')
    _('%d hours')
    _('%d minutes')
    _('%d seconds')
            
    def cell_call(self, row, col, props=None, displaytime=False, format='text/html'):
        etype = self.rset.description[row][col]
        value = self.rset.rows[row][col]
        if etype == 'String':
            entity, rtype = self.rset.related_entity(row, col)
            if entity is not None:
                # yes !
                self.w(entity.printable_value(rtype, value, format=format))
                return
        if etype in ('Time', 'Interval'):
            # value is DateTimeDelta but we have no idea about what is the 
            # reference date here, so we can only approximate years and months
            if format == 'text/html':
                space = '&nbsp;'
            else:
                space = ' '
            if value.days > 730: # 2 years
                self.w(self.req.__('%%d%syears' % space) % (value.days // 365))
            elif value.days > 60: # 2 months
                self.w(self.req.__('%%d%smonths' % space) % (value.days // 30))
            elif value.days > 14: # 2 weeks
                self.w(self.req.__('%%d%sweeks' % space) % (value.days // 7))
            elif value.days > 2:
                self.w(self.req.__('%%d%sdays' % space) % int(value.days))
            elif value.hours > 2:
                self.w(self.req.__('%%d%shours' % space) % int(value.hours))
            elif value.minutes >= 2:
                self.w(self.req.__('%%d%sminutes' % space) % int(value.minutes))
            else:
                self.w(self.req.__('%%d%sseconds' % space) % int(value.seconds))
            return
        self.wdata(printable_value(self.req, etype, value, props, displaytime=displaytime))


class EditableFinalView(FinalView):
    """same as FinalView but enables inplace-edition when possible"""
    id = 'editable-final'
                
    def cell_call(self, row, col, props=None, displaytime=False):
        etype = self.rset.description[row][col]
        value = self.rset.rows[row][col]
        entity, rtype = self.rset.related_entity(row, col)
        if entity is not None:
            self.w(entity.view('reledit', rtype=rtype))
        else:
            super(EditableFinalView, self).cell_call(row, col, props, displaytime)
        
PRIMARY_SKIP_RELS = set(['is', 'is_instance_of', 'identity',
                         'owned_by', 'created_by', 
                         'in_state', 'wf_info_for', 'require_permission',
                         'from_entity', 'to_entity',
                         'see_also'])

class PrimaryView(EntityView):
    """the full view of an non final entity"""
    id = 'primary'
    title = _('primary')
    show_attr_label = True
    show_rel_label = True
    skip_none = True
    skip_attrs = ('eid', 'creation_date', 'modification_date')
    skip_rels = ()
    main_related_section = True

    def html_headers(self):
        """return a list of html headers (eg something to be inserted between
        <head> and </head> of the returned page

        by default primary views are indexed
        """
        return []
    
    def cell_call(self, row, col):        
        self.row = row
        # XXX move render_entity implementation here
        self.render_entity(self.complete_entity(row, col))
    
    def render_entity(self, entity):
        """return html to display the given entity"""
        siderelations = []
        self.render_entity_title(entity)
        self.render_entity_metadata(entity)
        # entity's attributes and relations, excluding meta data
        # if the entity isn't meta itself
        #self.w(u'<table border="0" width="100%">')
        #self.w(u'<tr>')
        #self.w(u'<td valign="top">')
        self.w(u'<div>')
        self.w(u'<div class="mainInfo">')
        self.render_entity_attributes(entity, siderelations)
        self.w(u'</div>')
        self.content_navigation_components('navcontenttop')
        if self.main_related_section:
            self.render_entity_relations(entity, siderelations)
        self.w(u'</div>')
        #self.w(u'</td>')
        # side boxes
        #self.w(u'<td valign="top">')
        self.w(u'<div class="primaryRight">')
        self.render_side_related(entity, siderelations)
        self.w(u'</div>')
        self.w(u'<div class="clear"></div>')#verifier
        #self.w(u'</td>')
        #self.w(u'</tr>')
        #self.w(u'</table>')        
        self.content_navigation_components('navcontentbottom')

    def content_navigation_components(self, context):
        self.w(u'<div class="%s">' % context)
        for comp in self.vreg.possible_vobjects('contentnavigation',
                                                self.req, self.rset, row=self.row,
                                                view=self, context=context):
            try:
                comp.dispatch(w=self.w, row=self.row, view=self)
            except NotImplementedError:
                warn('component %s doesnt implement cell_call, please update'
                     % comp.__class__, DeprecationWarning)
                comp.dispatch(w=self.w, view=self)
        self.w(u'</div>')
        
    def iter_attributes(self, entity):
        for rschema, targetschema in entity.e_schema.attribute_definitions():
            attr = rschema.type
            if attr in self.skip_attrs:
               continue
            yield rschema, targetschema
            
    def iter_relations(self, entity):
        skip = set(self.skip_rels)
        skip.update(PRIMARY_SKIP_RELS)
        for rschema, targetschemas, x in entity.e_schema.relation_definitions():
            if rschema.type in skip:
                continue
            yield rschema, targetschemas, x

    def render_entity_title(self, entity):
        title = self.content_title(entity) # deprecate content_title?
        if title:
            self.w(u'<h1><span class="etype">%s</span> %s</h1>'
                   % (entity.dc_type().capitalize(), title))
    
    def content_title(self, entity):
        """default implementation return an empty string"""
        return u''
            
    def render_entity_metadata(self, entity):
        entity.view('metadata', w=self.w)
        summary = self.summary(entity) # deprecate summary?
        if summary:
            self.w(u'<div class="summary">%s</div>' % summary)
    
    def summary(self, entity):
        """default implementation return an empty string"""
        return u''    
               
    def render_entity_attributes(self, entity, siderelations):
        for rschema, targetschema in self.iter_attributes(entity):
            attr = rschema.type
            if targetschema.type in ('Password', 'Bytes'):
                continue
            try:
                wdg = entity.get_widget(attr)
            except Exception, ex:
                value = entity.printable_value(attr, entity[attr], targetschema.type)
            else:
                value = wdg.render(entity)
            if self.skip_none and (value is None or value == ''):
                continue
            if rschema.meta:
                continue
            self._render_related_entities(entity, rschema, value)

    def render_entity_relations(self, entity, siderelations):
        if hasattr(self, 'get_side_boxes_defs'):
            return
        eschema = entity.e_schema
        maxrelated = self.req.property_value('navigation.related-limit')
        for rschema, targetschemas, x in self.iter_relations(entity):
            try:
                related = entity.related(rschema.type, x, limit=maxrelated+1)
            except Unauthorized:
                continue
            if not related:
                continue
            if self.is_side_related(rschema, eschema):
                siderelations.append((rschema, related, x))
                continue
            self._render_related_entities(entity, rschema, related, x)

    def render_side_related(self, entity, siderelations):
        """display side related relations:
        non-meta in a first step, meta in a second step
        """
        if hasattr(self, 'get_side_boxes_defs'):
            sideboxes = [(label, rset) for label, rset in self.get_side_boxes_defs(entity)
                         if rset]
            if sideboxes:
                #self.w(u'<table width="100%">')
                for label, rset in sideboxes:
                    #self.w(u'<tr><td>')
                    self.w(u'<div class="sideRelated">')
                    self.wview('sidebox', rset, title=label)
                    self.w(u'</div>')
                    #self.w(u'</td></tr>')
                #self.w(u'</table>')
        elif siderelations:
            #self.w(u'<table width="100%">')
            #self.w(u'<tr><td>')
            self.w(u'<div class="sideRelated">')
            for relatedinfos in siderelations:
                # if not relatedinfos[0].meta:
                #    continue
                self._render_related_entities(entity, *relatedinfos)
            self.w(u'</div>')
            #self.w(u'</td></tr>')
            #self.w(u'</table>')
        boxes = list(self.vreg.possible_vobjects('boxes', self.req, self.rset,
                                                 row=self.row, view=self,
                                                 context='incontext'))
        if boxes:
            #self.w(u'<table width="100%">')
            for box in boxes:
                #self.w(u'<tr><td>')
                try:
                    box.dispatch(w=self.w, row=self.row)
                except NotImplementedError:
                    # much probably a context insensitive box, which only implements
                    # .call() and not cell_call()
                    box.dispatch(w=self.w)
                #self.w(u'</td></tr>')
            #self.w(u'</table>')
                
    def is_side_related(self, rschema, eschema):
        return rschema.meta and \
               not rschema.schema_relation() == eschema.schema_entity()

    def _render_related_entities(self, entity, rschema, related,
                                 role='subject'):
        if rschema.is_final():
            value = related
            show_label = self.show_attr_label
        else:
            if not related:
                return
            show_label = self.show_rel_label
            # if not too many entities, show them all in a list
            maxrelated = self.req.property_value('navigation.related-limit')
            if related.rowcount <= maxrelated:
                if related.rowcount == 1:
                    value = self.view('incontext', related, row=0)
                elif 1 < related.rowcount <= 5:
                    value = self.view('csv', related)
                else:
                    value = '<div>' + self.view('simplelist', related) + '</div>'
            # else show links to display related entities
            else:
                rql = related.printable_rql()
                related.limit(maxrelated)
                value = '<div>' + self.view('simplelist', related)
                value += '[<a href="%s">%s</a>]' % (self.build_url(rql=rql),
                                                    self.req._('see them all'))
                value +=  '</div>'
        label = display_name(self.req, rschema.type, role)
        self.field(label, value, show_label=show_label, w=self.w, tr=False)


class SideBoxView(EntityView):
    """side box usually displaying some related entities in a primary view"""
    id = 'sidebox'
    
    def call(self, boxclass='sideBox', title=u''):
        """display a list of entities by calling their <item_vid> view
        """
        if title:
            self.w(u'<div class="sideBoxTitle"><span>%s</span></div>' % title)
        self.w(u'<div class="%s"><div class="sideBoxBody">' % boxclass)
        # if not too much entities, show them all in a list
        maxrelated = self.req.property_value('navigation.related-limit')
        if self.rset.rowcount <= maxrelated:
            if len(self.rset) == 1:
                self.wview('incontext', self.rset, row=0)
            elif 1 < len(self.rset) < 5:
                self.wview('csv', self.rset)
            else:
                self.wview('simplelist', self.rset)
        # else show links to display related entities
        else:
            self.rset.limit(maxrelated)
            rql = self.rset.printable_rql(encoded=False)
            self.wview('simplelist', self.rset)
            self.w(u'[<a href="%s">%s</a>]' % (self.build_url(rql=rql),
                                               self.req._('see them all')))
        self.w(u'</div>\n</div>\n')


 
class SecondaryView(EntityView):
    id = 'secondary'
    title = _('secondary')
    
    def cell_call(self, row, col):
        """the secondary view for an entity
        secondary = icon + view(oneline)
        """
        entity = self.entity(row, col)
        self.w(u'&nbsp;')
        self.wview('oneline', self.rset, row=row, col=col)

class OneLineView(EntityView):
    id = 'oneline'
    title = _('oneline') 

    def cell_call(self, row, col):
        """the one line view for an entity: linked text view
        """
        entity = self.entity(row, col)
        self.w(u'<a href="%s">' % html_escape(entity.absolute_url()))
        self.w(html_escape(self.view('text', self.rset, row=row, col=col)))
        self.w(u'</a>')

class TextView(EntityView):
    """the simplest text view for an entity"""
    id = 'text'
    title = _('text')
    content_type = 'text/plain'
    accepts = 'Any',
    def call(self, **kwargs):
        """the view is called for an entire result set, by default loop
        other rows of the result set and call the same view on the
        particular row

        Views applicable on None result sets have to override this method
        """
        rset = self.rset
        if rset is None:
            raise NotImplementedError, self
        for i in xrange(len(rset)):
            self.wview(self.id, rset, row=i, **kwargs)
            if len(rset) > 1:
                self.w(u"\n")
    
    def cell_call(self, row, col=0, **kwargs):
        entity = self.entity(row, col)
        self.w(cut(entity.dc_title(),
                   self.req.property_value('navigation.short-line-size')))


class MetaDataView(EntityView):
    """paragraph view of some metadata"""
    id = 'metadata'
    accepts = 'Any',
    show_eid = True
    
    def cell_call(self, row, col):
        _ = self.req._
        entity = self.entity(row, col)
        self.w(u'<div class="metadata">')
        if self.show_eid:
            self.w(u'#%s - ' % entity.eid)
        if entity.modification_date != entity.creation_date:
            self.w(u'<span>%s</span> ' % _('latest update on'))
            self.w(u'<span class="value">%s</span>,&nbsp;'
                   % self.format_date(entity.modification_date))
        # entities from external source may not have a creation date (eg ldap)
        if entity.creation_date: 
            self.w(u'<span>%s</span> ' % _('created on'))
            self.w(u'<span class="value">%s</span>'
                   % self.format_date(entity.creation_date))
        if entity.creator:
            self.w(u'&nbsp;<span>%s</span> ' % _('by'))
            self.w(u'<span class="value">%s</span>' % entity.creator.name())
        self.w(u'</div>')


# new default views for finner control in general views , to use instead of
# oneline / secondary

class InContextTextView(TextView):
    id = 'textincontext'
    title = None # not listed as a possible view
    def cell_call(self, row, col):
        entity = self.entity(row, col)
        self.w(entity.dc_title())
        
class OutOfContextTextView(InContextTextView):
    id = 'textoutofcontext'

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        self.w(entity.dc_long_title())


class InContextView(EntityView):
    id = 'incontext'

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        desc = cut(entity.dc_description(), 50)
        self.w(u'<a href="%s" title="%s">' % (html_escape(entity.absolute_url()),
                                              html_escape(desc)))
        self.w(html_escape(self.view('textincontext', self.rset, row=row, col=col)))
        self.w(u'</a>')

        
class OutOfContextView(EntityView):
    id = 'outofcontext'

    def cell_call(self, row, col):
        self.w(u'<a href="%s">' % self.entity(row, col).absolute_url())
        self.w(html_escape(self.view('textoutofcontext', self.rset, row=row, col=col)))
        self.w(u'</a>')

class NotClickableInContextView(EntityView):
    id = 'incontext'
    accepts = ('State',)
    def cell_call(self, row, col):
        self.w(html_escape(self.view('textincontext', self.rset, row=row, col=col)))

## class NotClickableOutOfContextView(EntityView):
##     id = 'outofcontext'
##     accepts = ('State',)
##     def cell_call(self, row, col):
##         self.w(html_escape(self.view('textoutofcontext', self.rset, row=row)))

            
# list and table related views ################################################
    
class ListView(EntityView):
    id = 'list'
    title = _('list')
    item_vid = 'listitem'
        
    def call(self, klass=None, title=None, subvid=None, listid=None, **kwargs):
        """display a list of entities by calling their <item_vid> view
        
        :param listid: the DOM id to use for the root element
        """
        if subvid is None and 'subvid' in self.req.form:
            subvid = self.req.form.pop('subvid') # consume it
        if listid:
            listid = u' id="%s"' % listid
        else:
            listid = u''
        if title:
            self.w(u'<div%s class="%s"><h4>%s</h4>\n' % (listid, klass or 'section', title))
            self.w(u'<ul>\n')
        else:
            self.w(u'<ul%s class="%s">\n' % (listid, klass or 'section'))
        for i in xrange(self.rset.rowcount):
            self.cell_call(row=i, col=0, vid=subvid, **kwargs)
        self.w(u'</ul>\n')
        if title:
            self.w(u'</div>\n')

    def cell_call(self, row, col=0, vid=None, **kwargs):
        self.w(u'<li>')
        self.wview(self.item_vid, self.rset, row=row, col=col, vid=vid, **kwargs)
        self.w(u'</li>\n')

    def url(self):
        """overrides url method so that by default, the view list is called
        with sorted entities
        """
        coltypes = self.rset.column_types(0)
        # don't want to generate the rql if there is some restriction on
        # something else than the entity type
        if len(coltypes) == 1:
            # XXX norestriction is not correct here. For instance, in cases like
            # Any P,N WHERE P is Project, P name N
            # norestriction should equal True
            restr = self.rset.syntax_tree().children[0].where
            norestriction = (isinstance(restr, nodes.Relation) and
                             restr.is_types_restriction())
            if norestriction:
                etype = iter(coltypes).next()
                return self.build_url(etype.lower(), vid=self.id)
        if len(self.rset) == 1:
            entity = self.rset.get_entity(0, 0)
            return self.build_url(entity.rest_path(), vid=self.id)
        return self.build_url(rql=self.rset.printable_rql(), vid=self.id)

 
class ListItemView(EntityView):
    id = 'listitem'
    
    @property
    def redirect_vid(self):
        if self.req.search_state[0] == 'normal':
            return 'outofcontext'
        return 'outofcontext-search'
        
    def cell_call(self, row, col, vid=None, **kwargs):
        if not vid:
            vid = self.redirect_vid
        try:
            self.wview(vid, self.rset, row=row, col=col, **kwargs)
        except NoSelectableObject:
            if vid == self.redirect_vid:
                raise
            self.wview(self.redirect_vid, self.rset, row=row, col=col, **kwargs)


class SimpleListView(ListItemView):
    """list without bullets"""
    id = 'simplelist'
    redirect_vid = 'incontext'


class CSVView(SimpleListView):
    id = 'csv'
    redirect_vid = 'incontext'
        
    def call(self, **kwargs):
        rset = self.rset
        for i in xrange(len(rset)):
            self.cell_call(i, 0, vid=kwargs.get('vid'))
            if i < rset.rowcount-1:
                self.w(u", ")


class TreeItemView(ListItemView):
    accepts = ('Any',)
    id = 'treeitem'
    
    def cell_call(self, row, col):
        self.wview('incontext', self.rset, row=row, col=col)


# xml and xml/rss views #######################################################
    
class XmlView(EntityView):
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


    
class XMLRsetView(AnyRsetView):
    """dumps xml in CSV"""
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
        w(u'<%s query="%s">\n' % (self.xml_root, html_escape(rset.printable_rql())))
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
        self.w(u'  <channel rdf:about="%s">\n' % html_escape(req.url()))
        self.w(u'    <title>%s RSS Feed</title>\n' % html_escape(self.page_title()))
        self.w(u'    <description>%s</description>\n' % html_escape(req.form.get('vtitle', '')))
        params = req.form.copy()
        params.pop('vid', None)
        self.w(u'    <link>%s</link>\n' % html_escape(self.build_url(**params)))
        self.w(u'    <items>\n')
        self.w(u'      <rdf:Seq>\n')
        for entity in self.rset.entities():
            self.w(u'      <rdf:li resource="%s" />\n' % html_escape(entity.absolute_url()))
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
        self.w(u'<item rdf:about="%s">\n' % html_escape(entity.absolute_url()))
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
            self.w(u'  <%s>%s</%s>\n' % (marker, html_escape(value), marker))


class CSVMixIn(object):
    """mixin class for CSV views"""
    templatable = False
    content_type = "text/comma-separated-values"    
    binary = True # avoid unicode assertion
    csv_params = {'dialect': 'excel',
                  'quotechar': '"',
                  'delimiter': ';',
                  'lineterminator': '\n'}
    
    def set_request_content_type(self):
        """overriden to set a .csv filename"""
        self.req.set_content_type(self.content_type, filename='cubicwebexport.csv')
            
    def csvwriter(self, **kwargs):
        params = self.csv_params.copy()
        params.update(kwargs)
        return UnicodeCSVWriter(self.w, self.req.encoding, **params)

    
class CSVRsetView(CSVMixIn, AnyRsetView):
    """dumps rset in CSV"""
    id = 'csvexport'
    title = _('csv export')
        
    def call(self):
        writer = self.csvwriter()
        writer.writerow(self.columns_labels())
        rset, descr = self.rset, self.rset.description
        eschema = self.schema.eschema
        for rowindex, row in enumerate(rset):
            csvrow = []
            for colindex, val in enumerate(row):
                etype = descr[rowindex][colindex]
                if val is not None and not eschema(etype).is_final():
                    # csvrow.append(val) # val is eid in that case
                    content = self.view('textincontext', rset, 
                                        row=rowindex, col=colindex)
                else:
                    content = self.view('final', rset,
                                        displaytime=True, format='text/plain',
                                        row=rowindex, col=colindex)
                csvrow.append(content)                    
            writer.writerow(csvrow)
    
    
class CSVEntityView(CSVMixIn, EntityView):
    """dumps rset's entities (with full set of attributes) in CSV"""
    id = 'ecsvexport'
    title = _('csv entities export')

    def call(self):
        """
        the generated CSV file will have a table per entity type
        found in the resultset. ('table' here only means empty
        lines separation between table contents)
        """
        req = self.req
        rows_by_type = {}
        writer = self.csvwriter()
        rowdef_by_type = {}
        for index in xrange(len(self.rset)):
            entity = self.complete_entity(index)
            if entity.e_schema not in rows_by_type:
                rowdef_by_type[entity.e_schema] = [rs for rs, at in entity.e_schema.attribute_definitions()
                                                   if at != 'Bytes']
                rows_by_type[entity.e_schema] = [[display_name(req, rschema.type)
                                                  for rschema in rowdef_by_type[entity.e_schema]]]
            rows = rows_by_type[entity.e_schema]
            rows.append([entity.printable_value(rs.type, format='text/plain')
                         for rs in rowdef_by_type[entity.e_schema]])
        for etype, rows in rows_by_type.items():
            writer.writerows(rows)
            # use two empty lines as separator
            writer.writerows([[], []])        
    

## Work in progress ###########################################################

class SearchForAssociationView(EntityView):
    """view called by the edition view when the user asks
    to search for something to link to the edited eid
    """
    id = 'search-associate'
    title = _('search for association')
    __selectors__ = (one_line_rset, match_search_state, accept)
    accepts = ('Any',)
    search_states = ('linksearch',)

    def cell_call(self, row, col):
        rset, vid, divid, paginate = self.filter_box_context_info()
        self.w(u'<div id="%s">' % divid)
        self.pagination(self.req, rset, w=self.w)
        self.wview(vid, rset, 'noresult')
        self.w(u'</div>')

    @cached
    def filter_box_context_info(self):
        entity = self.entity(0, 0)
        role, eid, rtype, etype = self.req.search_state[1]
        assert entity.eid == typed_eid(eid)
        # the default behaviour is to fetch all unrelated entities and display
        # them. Use fetch_order and not fetch_unrelated_order as sort method
        # since the latter is mainly there to select relevant items in the combo
        # box, it doesn't give interesting result in this context
        rql = entity.unrelated_rql(rtype, etype, role,
                                   ordermethod='fetch_order',
                                   vocabconstraints=False)
        rset = self.req.execute(rql, {'x' : entity.eid}, 'x')
        #vid = vid_from_rset(self.req, rset, self.schema)
        return rset, 'list', "search-associate-content", True


class OutOfContextSearch(EntityView):
    id = 'outofcontext-search'
    def cell_call(self, row, col):
        entity = self.entity(row, col)
        erset = entity.as_rset()
        if linksearch_match(self.req, erset):
            self.w(u'<a href="%s" title="%s">%s</a>&nbsp;<a href="%s" title="%s">[...]</a>' % (
                html_escape(linksearch_select_url(self.req, erset)),
                self.req._('select this entity'),
                html_escape(entity.view('textoutofcontext')),
                html_escape(entity.absolute_url(vid='primary')),
                self.req._('view detail for this entity')))
        else:
            entity.view('outofcontext', w=self.w)
            
            
class EditRelationView(EntityView):
    """Note: This is work in progress

    This view is part of the edition view refactoring.
    It is still too big and cluttered with strange logic, but it's a start

    The main idea is to be able to call an edition view for a specific
    relation. For example :
       self.wview('editrelation', person_rset, rtype='firstname')
       self.wview('editrelation', person_rset, rtype='works_for')
    """
    id = 'editrelation'

    __selectors__ = (match_form_params,)
    form_params = ('rtype',)
    
    # TODO: inlineview, multiple edit, (widget view ?)
    def cell_call(self, row, col, rtype=None, role='subject', targettype=None,
                 showlabel=True):
        self.req.add_js( ('cubicweb.ajax.js', 'cubicweb.edition.js') )
        entity = self.entity(row, col)
        rtype = self.req.form.get('rtype', rtype)
        showlabel = self.req.form.get('showlabel', showlabel)
        assert rtype is not None, "rtype is mandatory for 'edirelation' view"
        targettype = self.req.form.get('targettype', targettype)
        role = self.req.form.get('role', role)
        category = entity.rtags.get_category(rtype, targettype, role)
        if category in ('primary', 'secondary') or self.schema.rschema(rtype).is_final():
            if hasattr(entity, '%s_format' % rtype):
                formatwdg = entity.get_widget('%s_format' % rtype, role)
                self.w(formatwdg.edit_render(entity))
                self.w(u'<br/>')
            wdg = entity.get_widget(rtype, role)
            if showlabel:
                self.w(u'%s' % wdg.render_label(entity))
            self.w(u'%s %s %s' %
                   (wdg.render_error(entity), wdg.edit_render(entity),
                    wdg.render_help(entity),))
        else:
            self._render_generic_relation(entity, rtype, role)

    def _render_generic_relation(self, entity, relname, role):
        text = self.req.__('add %s %s %s' % (entity.e_schema, relname, role))
        # pending operations
        operations = self.req.get_pending_operations(entity, relname, role)
        if operations['insert'] or operations['delete'] or 'unfold' in self.req.form:
            self.w(u'<h3>%s</h3>' % text)
            self._render_generic_relation_form(operations, entity, relname, role)
        else:
            divid = "%s%sreledit" % (relname, role)
            url = ajax_replace_url(divid, rql_for_eid(entity.eid), 'editrelation',
                                   {'unfold' : 1, 'relname' : relname, 'role' : role})
            self.w(u'<a href="%s">%s</a>' % (url, text))
            self.w(u'<div id="%s"></div>' % divid)
        

    def _build_opvalue(self, entity, relname, target, role):
        if role == 'subject':
            return '%s:%s:%s' % (entity.eid, relname, target)
        else:
            return '%s:%s:%s' % (target, relname, entity.eid)
        
    
    def _render_generic_relation_form(self, operations, entity, relname, role):
        rqlexec = self.req.execute
        for optype, targets in operations.items():
            for target in targets:
                self._render_pending(optype, entity, relname, target, role)
                opvalue = self._build_opvalue(entity, relname, target, role)
                self.w(u'<a href="javascript: addPendingDelete(\'%s\', %s);">-</a> '
                       % (opvalue, entity.eid))
                rset = rqlexec('Any X WHERE X eid %(x)s', {'x': target}, 'x')
                self.wview('oneline', rset)
        # now, unrelated ones
        self._render_unrelated_selection(entity, relname, role)

    def _render_pending(self, optype, entity, relname, target, role):
        opvalue = self._build_opvalue(entity, relname, target, role)
        self.w(u'<input type="hidden" name="__%s" value="%s" />'
               % (optype, opvalue))
        if optype == 'insert':
            checktext = '-'
        else:
            checktext = '+'
        rset = self.req.execute('Any X WHERE X eid %(x)s', {'x': target}, 'x')
        self.w(u"""[<a href="javascript: cancelPending%s('%s:%s:%s')">%s</a>"""
               % (optype.capitalize(), relname, target, role,
                  self.view('oneline', rset)))

    def _render_unrelated_selection(self, entity, relname, role):
        rschema = self.schema.rschema(relname)
        if role == 'subject':
            targettypes = rschema.objects(entity.e_schema)
        else:
            targettypes = rschema.subjects(entity.e_schema)
        self.w(u'<select onselect="addPendingInsert(this.selected.value);">')
        for targettype in targettypes:
            unrelated = entity.unrelated(relname, targettype, role) # XXX limit
            for rowindex, row in enumerate(unrelated):
                teid = row[0]
                opvalue = self._build_opvalue(entity, relname, teid, role)
                self.w(u'<option name="__insert" value="%s>%s</option>'
                       % (opvalue, self.view('text', unrelated, row=rowindex)))
        self.w(u'</select>')


class TextSearchResultView(EntityView):
    """this view is used to display full-text search

    It tries to highlight part of data where the search word appears.

    XXX: finish me (fixed line width, fixed number of lines, CSS, etc.)
    """
    id = 'tsearch'


    def cell_call(self, row, col, **kwargs):
        entity = self.complete_entity(row, col)
        self.w(entity.view('incontext'))
        searched = self.rset.searched_text()
        if searched is None:
            return
        searched = searched.lower()
        highlighted = '<b>%s</b>' % searched
        for attr in entity.e_schema.indexable_attributes():
            try:
                value = html_escape(entity.printable_value(attr, format='text/plain').lower())
            except TransformError, ex:
                continue
            except:
                continue
            if searched in value:
                contexts = []
                for ctx in value.split(searched):
                    if len(ctx) > 30:
                        contexts.append(u'...' + ctx[-30:])
                    else:
                        contexts.append(ctx)
                value = u'\n' + highlighted.join(contexts)
                self.w(value.replace('\n', '<br/>'))            


class EntityRelationView(EntityView):
    accepts = ()
    vid = 'list'
    
    def cell_call(self, row, col):
        if self.target == 'object':
            role = 'subject'
        else:
            role = 'object'
        rset = self.rset.get_entity(row, col).related(self.rtype, role)
        if self.title:
            self.w(u'<h1>%s</h1>' % self.req._(self.title).capitalize())
        self.w(u'<div class="mainInfo">')
        self.wview(self.vid, rset, 'noresult')
        self.w(u'</div>')


class TooltipView(OneLineView):
    """A entity view used in a tooltip"""
    id = 'tooltip'
    title = None # don't display in possible views
    def cell_call(self, row, col):
        self.wview('oneline', self.rset, row=row, col=col)

try:
    from cubicweb.web.views.tableview import TableView
    from logilab.common.deprecation import class_moved
    TableView = class_moved(TableView)
except ImportError:
    pass # gae has no tableview module (yet)
