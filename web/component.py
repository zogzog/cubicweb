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
"""abstract component class and base components definition for CubicWeb web
client
"""

__docformat__ = "restructuredtext en"
_ = unicode

from warnings import warn

from logilab.common.deprecation import class_deprecated, class_renamed
from logilab.mtconverter import xml_escape

from cubicweb import Unauthorized, role, tags
from cubicweb.uilib import js, domid
from cubicweb.utils import json_dumps
from cubicweb.view import ReloadableMixIn, Component
from cubicweb.selectors import (no_cnx, paginated_rset, one_line_rset,
                                non_final_entity, partial_relation_possible,
                                partial_has_related_entities)
from cubicweb.appobject import AppObject
from cubicweb.web import htmlwidgets, stdmsgs


# abstract base class for navigation components ################################

class NavigationComponent(Component):
    """abstract base class for navigation components"""
    __regid__ = 'navigation'
    __select__ = paginated_rset()

    cw_property_defs = {
        _('visible'):  dict(type='Boolean', default=True,
                            help=_('display the component or not')),
        }

    page_size_property = 'navigation.page-size'
    start_param = '__start'
    stop_param = '__stop'
    page_link_templ = u'<span class="slice"><a href="%s" title="%s">%s</a></span>'
    selected_page_link_templ = u'<span class="selectedSlice"><a href="%s" title="%s">%s</a></span>'
    previous_page_link_templ = next_page_link_templ = page_link_templ
    no_previous_page_link = u'&lt;&lt;'
    no_next_page_link = u'&gt;&gt;'

    def __init__(self, req, rset, **kwargs):
        super(NavigationComponent, self).__init__(req, rset=rset, **kwargs)
        self.starting_from = 0
        self.total = rset.rowcount

    def get_page_size(self):
        try:
            return self._page_size
        except AttributeError:
            page_size = self.cw_extra_kwargs.get('page_size')
            if page_size is None:
                if 'page_size' in self._cw.form:
                    page_size = int(self._cw.form['page_size'])
                else:
                    page_size = self._cw.property_value(self.page_size_property)
            self._page_size = page_size
            return page_size

    def set_page_size(self, page_size):
        self._page_size = page_size

    page_size = property(get_page_size, set_page_size)

    def page_boundaries(self):
        try:
            stop = int(self._cw.form[self.stop_param]) + 1
            start = int(self._cw.form[self.start_param])
        except KeyError:
            start, stop = 0, self.page_size
        if start >= len(self.cw_rset):
            start, stop = 0, self.page_size
        self.starting_from = start
        return start, stop

    def clean_params(self, params):
        if self.start_param in params:
            del params[self.start_param]
        if self.stop_param in params:
            del params[self.stop_param]

    def page_url(self, path, params, start=None, stop=None):
        params = dict(params)
        if start is not None:
            params[self.start_param] = start
        if stop is not None:
            params[self.stop_param] = stop
        view = self.cw_extra_kwargs.get('view')
        if view is not None and hasattr(view, 'page_navigation_url'):
            url = view.page_navigation_url(self, path, params)
        elif path == 'json':
            url = self.ajax_page_url(**params)
        else:
            url = self._cw.build_url(path, **params)
        # XXX hack to avoid opening a new page containing the evaluation of the
        # js expression on ajax call
        if url.startswith('javascript:'):
            url += '; noop();'
        return url

    def ajax_page_url(self, **params):
        divid = params.setdefault('divid', 'pageContent')
        params['rql'] = self.cw_rset.printable_rql()
        return "javascript: $(%s).loadxhtml('json', %s, 'get', 'swap')" % (
            json_dumps('#'+divid), js.ajaxFuncArgs('view', params))

    def page_link(self, path, params, start, stop, content):
        url = xml_escape(self.page_url(path, params, start, stop))
        if start == self.starting_from:
            return self.selected_page_link_templ % (url, content, content)
        return self.page_link_templ % (url, content, content)

    def previous_link(self, path, params, content='&lt;&lt;', title=_('previous_results')):
        start = self.starting_from
        if not start :
            return self.no_previous_page_link
        start = max(0, start - self.page_size)
        stop = start + self.page_size - 1
        url = xml_escape(self.page_url(path, params, start, stop))
        return self.previous_page_link_templ % (url, title, content)

    def next_link(self, path, params, content='&gt;&gt;', title=_('next_results')):
        start = self.starting_from + self.page_size
        if start >= self.total:
            return self.no_next_page_link
        stop = start + self.page_size - 1
        url = xml_escape(self.page_url(path, params, start, stop))
        return self.next_page_link_templ % (url, title, content)


# new contextual components system #############################################

def override_ctx(cls, **kwargs):
    cwpdefs = cls.cw_property_defs.copy()
    cwpdefs['context']  = cwpdefs['context'].copy()
    cwpdefs['context'].update(kwargs)
    return cwpdefs


class EmptyComponent(Exception):
    """some selectable component has actually no content and should not be
    rendered
    """

class Layout(Component):
    __regid__ = 'layout'
    __abstract__ = True

    def init_rendering(self):
        """init view for rendering. Return true if we should go on, false
        if we should stop now.
        """
        view = self.cw_extra_kwargs['view']
        try:
            view.init_rendering()
        except Unauthorized, ex:
            self.warning("can't render %s: %s", view, ex)
            return False
        except EmptyComponent:
            return False
        return True


class CtxComponent(AppObject):
    """base class for contextual compontents. The following contexts are
    predefined:

    * boxes: 'left', 'incontext', 'right'
    * section: 'navcontenttop', 'navcontentbottom', 'navtop', 'navbottom'
    * other: 'ctxtoolbar'

    The 'incontext', 'navcontenttop', 'navcontentbottom' and 'ctxtoolbar'
    context are handled by the default primary view, others by the default main
    template.

    All subclasses may not support all those contexts (for instance if it can't
    be displayed as box, or as a toolbar icon). You may restrict allowed context
    as followed:

    .. sourcecode:: python

      class MyComponent(CtxComponent):
          cw_property_defs = override_ctx(CtxComponent,
                                          vocabulary=[list of contexts])
          context = 'my default context'

    You can configure default component's context by simply giving appropriate
    value to the `context` class attribute, as seen above.
    """
    __registry__ = 'ctxcomponents'
    __select__ = ~no_cnx()

    categories_in_order = ()
    cw_property_defs = {
        _('visible'): dict(type='Boolean', default=True,
                           help=_('display the box or not')),
        _('order'):   dict(type='Int', default=99,
                           help=_('display order of the box')),
        _('context'): dict(type='String', default='left',
                           vocabulary=(_('left'), _('incontext'), _('right'),
                                       _('navtop'), _('navbottom'),
                                       _('navcontenttop'), _('navcontentbottom'),
                                       _('ctxtoolbar')),
                           help=_('context where this component should be displayed')),
        }
    visible = True
    order = 0
    context = 'left'
    contextual = False
    title = None

    # XXX support kwargs for compat with old boxes which gets the view as
    # argument
    def render(self, w, **kwargs):
        if hasattr(self, 'call'):
            warn('[3.10] should not anymore implements call on %s, see new CtxComponent api'
                 % self.__class__, DeprecationWarning)
            self.w = w
            def wview(__vid, rset=None, __fallback_vid=None, **kwargs):
                self._cw.view(__vid, rset, __fallback_vid, w=self.w, **kwargs)
            self.wview = wview
            self.call(**kwargs)
            return
        getlayout = self._cw.vreg['components'].select
        try:
            # XXX ensure context is given when the component is reloaded through
            # ajax
            context = self.cw_extra_kwargs['context']
        except KeyError:
            context = self.cw_propval('context')
        layout = getlayout('layout', self._cw, rset=self.cw_rset,
                           row=self.cw_row, col=self.cw_col,
                           view=self, context=context)
        layout.render(w)

    def init_rendering(self):
        """init rendering callback: that's the good time to check your component
        has some content to display. If not, you can still raise
        :exc:`EmptyComponent` to inform it should be skipped.

        Also, :exc:`Unauthorized` will be catched, logged, then the component
        will be skipped.
        """
        self.items = []

    @property
    def domid(self):
        """return the HTML DOM identifier for this component"""
        return domid(self.__regid__)

    @property
    def cssclass(self):
        """return the CSS class name for this component"""
        return domid(self.__regid__)

    def render_title(self, w):
        """return the title for this component"""
        if self.title:
            w(self._cw._(self.title))

    def render_body(self, w):
        """return the body (content) for this component"""
        raise NotImplementedError()

    def render_items(self, w, items=None, klass=u'boxListing'):
        if items is None:
            items = self.items
        assert items
        w(u'<ul class="%s">' % klass)
        for item in items:
            if hasattr(item, 'render'):
                item.render(w) # XXX display <li> by itself
            else:
                w(u'<li>')
                w(item)
                w(u'</li>')
        w(u'</ul>')

    def append(self, item):
        self.items.append(item)

    def box_action(self, action): # XXX action_link
        return self.build_link(self._cw._(action.title), action.url())

    def build_link(self, title, url, **kwargs):
        if self._cw.selected(url):
            try:
                kwargs['klass'] += ' selected'
            except KeyError:
                kwargs['klass'] = 'selected'
        return tags.a(title, href=url, **kwargs)


class EntityCtxComponent(CtxComponent):
    """base class for boxes related to a single entity"""
    __select__ = CtxComponent.__select__ & non_final_entity() & one_line_rset()
    context = 'incontext'
    contextual = True

    def __init__(self, *args, **kwargs):
        super(EntityCtxComponent, self).__init__(*args, **kwargs)
        try:
            entity = kwargs['entity']
        except KeyError:
            entity = self.cw_rset.get_entity(self.cw_row or 0, self.cw_col or 0)
        self.entity = entity

    @property
    def domid(self):
        return domid(self.__regid__) + unicode(self.entity.eid)


# high level abstract classes ##################################################

class RQLCtxComponent(CtxComponent):
    """abstract box for boxes displaying the content of a rql query not
    related to the current result set.
    """
    rql  = None

    def to_display_rql(self):
        assert self.rql is not None, self.__regid__
        return (self.rql,)

    def init_rendering(self):
        rset = self._cw.execute(*self.to_display_rql())
        if not rset:
            raise EmptyComponent()
        if len(rset[0]) == 2:
            self.items = []
            for i, (eid, label) in enumerate(rset):
                entity = rset.get_entity(i, 0)
                self.items.append(self.build_link(label, entity.absolute_url()))
        else:
            self.items = [self.build_link(e.dc_title(), e.absolute_url())
                          for e in rset.entities()]

    def render_body(self, w):
        self.render_items(w)


class EditRelationMixIn(ReloadableMixIn):
    def box_item(self, entity, etarget, rql, label):
        """builds HTML link to edit relation between `entity` and `etarget`"""
        role, target = role(self), get_target(self)
        args = {role[0] : entity.eid, target[0] : etarget.eid}
        url = self._cw.user_rql_callback((rql, args))
        # for each target, provide a link to edit the relation
        return u'[<a href="%s">%s</a>] %s' % (xml_escape(url), label,
                                              etarget.view('incontext'))

    def related_boxitems(self, entity):
        rql = 'DELETE S %s O WHERE S eid %%(s)s, O eid %%(o)s' % self.rtype
        return [self.box_item(entity, etarget, rql, u'-')
                for etarget in self.related_entities(entity)]

    def related_entities(self, entity):
        return entity.related(self.rtype, role(self), entities=True)

    def unrelated_boxitems(self, entity):
        rql = 'SET S %s O WHERE S eid %%(s)s, O eid %%(o)s' % self.rtype
        return [self.box_item(entity, etarget, rql, u'+')
                for etarget in self.unrelated_entities(entity)]

    def unrelated_entities(self, entity):
        """returns the list of unrelated entities, using the entity's
        appropriate vocabulary function
        """
        skip = set(unicode(e.eid) for e in entity.related(self.rtype, role(self),
                                                          entities=True))
        skip.add(None)
        skip.add(INTERNAL_FIELD_VALUE)
        filteretype = getattr(self, 'etype', None)
        entities = []
        form = self._cw.vreg['forms'].select('edition', self._cw,
                                             rset=self.cw_rset,
                                             row=self.cw_row or 0)
        field = form.field_by_name(self.rtype, role(self), entity.e_schema)
        for _, eid in field.vocabulary(form):
            if eid not in skip:
                entity = self._cw.entity_from_eid(eid)
                if filteretype is None or entity.__regid__ == filteretype:
                    entities.append(entity)
        return entities


class EditRelationCtxComponent(EditRelationMixIn, EntityCtxComponent):
    """base class for boxes which let add or remove entities linked by a given
    relation

    subclasses should define at least id, rtype and target class attributes.
    """
    def render_title(self, w):
        return display_name(self._cw, self.rtype, role(self),
                            context=self.entity.__regid__)

    def render_body(self, w):
        self._cw.add_js('cubicweb.ajax.js')
        related = self.related_boxitems(self.entity)
        unrelated = self.unrelated_boxitems(self.entity)
        self.items.extend(related)
        if related and unrelated:
            self.items.append(htmlwidgets.BoxSeparator())
        self.items.extend(unrelated)
        self.render_items(w)


class AjaxEditRelationCtxComponent(EntityCtxComponent):
    __select__ = EntityCtxComponent.__select__ & (
        partial_relation_possible(action='add') | partial_has_related_entities())

    # view used to display related entties
    item_vid = 'incontext'
    # values separator when multiple values are allowed
    separator = ','
    # msgid of the message to display when some new relation has been added/removed
    added_msg = None
    removed_msg = None

    # class attributes below *must* be set in concret classes (additionaly to
    # rtype / role [/ target_etype]. They should correspond to js_* methods on
    # the json controller

    # function(eid)
    # -> expected to return a list of values to display as input selector
    #    vocabulary
    fname_vocabulary = None

    # function(eid, value)
    # -> handle the selector's input (eg create necessary entities and/or
    # relations). If the relation is multiple, you'll get a list of value, else
    # a single string value.
    fname_validate = None

    # function(eid, linked entity eid)
    # -> remove the relation
    fname_remove = None

    def __init__(self, *args, **kwargs):
        super(AjaxEditRelationCtxComponent, self).__init__(*args, **kwargs)
        self.rdef = self.entity.e_schema.rdef(self.rtype, self.role, self.target_etype)

    def render_title(self, w):
        w(self.rdef.rtype.display_name(self._cw, self.role,
                                       context=self.entity.__regid__))

    def render_body(self, w):
        req = self._cw
        entity = self.entity
        related = entity.related(self.rtype, self.role)
        if self.role == 'subject':
            mayadd = self.rdef.has_perm(req, 'add', fromeid=entity.eid)
            maydel = self.rdef.has_perm(req, 'delete', fromeid=entity.eid)
        else:
            mayadd = self.rdef.has_perm(req, 'add', toeid=entity.eid)
            maydel = self.rdef.has_perm(req, 'delete', toeid=entity.eid)
        if mayadd or maydel:
            req.add_js(('jquery.ui.js', 'cubicweb.widgets.js'))
            req.add_js(('cubicweb.ajax.js', 'cubicweb.ajax.box.js'))
        _ = req._
        if related:
            w(u'<table class="ajaxEditRelationTable">')
            for rentity in related.entities():
                # for each related entity, provide a link to remove the relation
                subview = rentity.view(self.item_vid)
                if maydel:
                    jscall = unicode(js.ajaxBoxRemoveLinkedEntity(
                        self.__regid__, entity.eid, rentity.eid,
                        self.fname_remove,
                        self.removed_msg and _(self.removed_msg)))
                    w(u'<tr><td class="dellink">[<a href="javascript: %s">-</a>]</td>'
                      '<td class="entity"> %s</td></tr>' % (xml_escape(jscall),
                                                            subview))
                else:
                    w(u'<tr><td class="entity">%s</td></tr>' % (subview))
            w(u'</table>')
        else:
            w(_('no related entity'))
        if mayadd:
            req.add_js(('jquery.ui.js', 'cubicweb.widgets.js'))
            req.add_css('jquery.ui.css')
            multiple = self.rdef.role_cardinality(self.role) in '*+'
            w(u'<table><tr><td>')
            jscall = unicode(js.ajaxBoxShowSelector(
                self.__regid__, entity.eid, self.fname_vocabulary,
                self.fname_validate, self.added_msg and _(self.added_msg),
                _(stdmsgs.BUTTON_OK[0]), _(stdmsgs.BUTTON_CANCEL[0]),
                multiple and self.separator))
            w('<a class="button sglink" href="javascript: %s">%s</a>' % (
                xml_escape(jscall),
                multiple and _('add_relation') or _('update_relation')))
            w(u'</td><td>')
            w(u'<div id="%sHolder"></div>' % self.domid)
            w(u'</td></tr></table>')


class RelatedObjectsCtxComponent(EntityCtxComponent):
    """a contextual component to display entities related to another"""
    __select__ = EntityCtxComponent.__select__ & partial_has_related_entities()
    context = 'navcontentbottom'
    rtype = None
    role = 'subject'

    vid = 'list'

    def render_body(self, w):
        rset = self.entity.related(self.rtype, role(self))
        self._cw.view(self.vid, rset, w=w)


# old contextual components, deprecated ########################################

class EntityVComponent(Component):
    """abstract base class for additinal components displayed in content
    headers and footer according to:

    * the displayed entity's type
    * a context (currently 'header' or 'footer')

    it should be configured using .accepts, .etype, .rtype, .target and
    .context class attributes
    """
    __metaclass__ = class_deprecated
    __deprecation_warning__ = '[3.10] *VComponent classes are deprecated, use *CtxComponent instead (%(cls)s)'

    __registry__ = 'ctxcomponents'
    __select__ = one_line_rset()

    cw_property_defs = {
        _('visible'):  dict(type='Boolean', default=True,
                            help=_('display the component or not')),
        _('order'):    dict(type='Int', default=99,
                            help=_('display order of the component')),
        _('context'):  dict(type='String', default='navtop',
                            vocabulary=(_('navtop'), _('navbottom'),
                                        _('navcontenttop'), _('navcontentbottom'),
                                        _('ctxtoolbar')),
                            help=_('context where this component should be displayed')),
    }

    context = 'navcontentbottom'

    def call(self, view=None):
        if self.cw_rset is None:
            self.entity_call(self.cw_extra_kwargs.pop('entity'))
        else:
            self.cell_call(0, 0, view=view)

    def cell_call(self, row, col, view=None):
        self.entity_call(self.cw_rset.get_entity(row, col), view=view)

    def entity_call(self, entity, view=None):
        raise NotImplementedError()


class RelatedObjectsVComponent(EntityVComponent):
    """a section to display some related entities"""
    __select__ = EntityVComponent.__select__ & partial_has_related_entities()

    vid = 'list'

    def rql(self):
        """override this method if you want to use a custom rql query"""
        return None

    def cell_call(self, row, col, view=None):
        rql = self.rql()
        if rql is None:
            entity = self.cw_rset.get_entity(row, col)
            rset = entity.related(self.rtype, role(self))
        else:
            eid = self.cw_rset[row][col]
            rset = self._cw.execute(self.rql(), {'x': eid})
        if not rset.rowcount:
            return
        self.w(u'<div class="%s">' % self.cssclass)
        self.w(u'<h4>%s</h4>\n' % self._cw._(self.title).capitalize())
        self.wview(self.vid, rset)
        self.w(u'</div>')



VComponent = class_renamed('VComponent', Component,
                           '[3.2] VComponent is deprecated, use Component')
SingletonVComponent = class_renamed('SingletonVComponent', Component,
                                    '[3.2] SingletonVComponent is deprecated, use '
                                    'Component and explicit registration control')
