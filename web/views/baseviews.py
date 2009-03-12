"""Set of HTML generic base views:

* noresult, final
* primary, sidebox
* secondary, oneline, incontext, outofcontext, text
* list


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
#from __future__ import with_statement

__docformat__ = "restructuredtext en"

from warnings import warn

from rql import nodes

from logilab.mtconverter import TransformError, html_escape

from cubicweb import Unauthorized, NoSelectableObject
from cubicweb.selectors import yes, empty_rset
from cubicweb.view import EntityView, AnyRsetView, View
from cubicweb.common.uilib import cut, printable_value

_ = unicode

class NullView(AnyRsetView):
    """default view when no result has been found"""
    id = 'null'
    __select__ = yes()
    def call(self, **kwargs):
        pass
    cell_call = call


class NoResultView(View):
    """default view when no result has been found"""
    __select__ = empty_rset()
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
        self.w(u'<div>')
        self.w(u'<div class="mainInfo">')
        self.render_entity_attributes(entity, siderelations)
        self.w(u'</div>')
        self.content_navigation_components('navcontenttop')
        if self.main_related_section:
            self.render_entity_relations(entity, siderelations)
        self.w(u'</div>')
        # side boxes
        self.w(u'<div class="primaryRight">')
        self.render_side_related(entity, siderelations)
        self.w(u'</div>')
        self.w(u'<div class="clear"></div>')          
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
            if rschema.type in self.skip_attrs:
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
                for label, rset in sideboxes:
                    self.w(u'<div class="sideRelated">')
                    self.wview('sidebox', rset, title=label)
                    self.w(u'</div>')
        elif siderelations:
            self.w(u'<div class="sideRelated">')
            for relatedinfos in siderelations:
                # if not relatedinfos[0].meta:
                #    continue
                self._render_related_entities(entity, *relatedinfos)
            self.w(u'</div>')
        boxes = list(self.vreg.possible_vobjects('boxes', self.req, self.rset,
                                                 row=self.row, view=self,
                                                 context='incontext'))
        if boxes:
            for box in boxes:
                try:
                    box.dispatch(w=self.w, row=self.row)
                except NotImplementedError:
                    # much probably a context insensitive box, which only implements
                    # .call() and not cell_call()
                    box.dispatch(w=self.w)               
                
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

            
# list views ##################################################################
    
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
    id = 'treeitem'
    
    def cell_call(self, row, col):
        self.wview('incontext', self.rset, row=row, col=col)

# context specific views ######################################################

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


class TooltipView(EntityView):
    """A entity view used in a tooltip"""
    id = 'tooltip'
    def cell_call(self, row, col):
        self.wview('oneline', self.rset, row=row, col=col)


# XXX bw compat

from logilab.common.deprecation import class_moved

try:
    from cubicweb.web.views.tableview import TableView
    TableView = class_moved(TableView)
except ImportError:
    pass # gae has no tableview module (yet)

from cubicweb.web.views import boxes, xmlrss
SideBoxView = class_moved(boxes.SideBoxView)
XmlView = class_moved(xmlrss.XmlView)
XmlItemView = class_moved(xmlrss.XmlItemView)
XmlRsetView = class_moved(xmlrss.XmlRsetView)
RssView = class_moved(xmlrss.RssView)
RssItemView = class_moved(xmlrss.RssItemView)
            
