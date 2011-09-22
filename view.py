# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""abstract views and templates classes for CubicWeb web client"""

__docformat__ = "restructuredtext en"
_ = unicode

import types, new
from cStringIO import StringIO
from warnings import warn

from logilab.common.deprecation import deprecated
from logilab.mtconverter import xml_escape

from rql import nodes

from cubicweb import NotAnEntity
from cubicweb.selectors import yes, non_final_entity, nonempty_rset, none_rset
from cubicweb.appobject import AppObject
from cubicweb.utils import UStringIO, HTMLStream
from cubicweb.uilib import domid, js
from cubicweb.schema import display_name
from cubicweb.vregistry import classid

# robots control
NOINDEX = u'<meta name="ROBOTS" content="NOINDEX" />'
NOFOLLOW = u'<meta name="ROBOTS" content="NOFOLLOW" />'

CW_XHTML_EXTENSIONS = '''[
  <!ATTLIST html xmlns:cubicweb CDATA  #FIXED \'http://www.logilab.org/2008/cubicweb\'  >

<!ENTITY % coreattrs
 "id          ID            #IMPLIED
  class       CDATA         #IMPLIED
  style       CDATA         #IMPLIED
  title       CDATA         #IMPLIED

 cubicweb:accesskey         CDATA   #IMPLIED
 cubicweb:actualrql         CDATA   #IMPLIED
 cubicweb:dataurl           CDATA   #IMPLIED
 cubicweb:facetName         CDATA   #IMPLIED
 cubicweb:facetargs         CDATA   #IMPLIED
 cubicweb:fallbackvid       CDATA   #IMPLIED
 cubicweb:fname             CDATA   #IMPLIED
 cubicweb:initfunc          CDATA   #IMPLIED
 cubicweb:inputid           CDATA   #IMPLIED
 cubicweb:inputname         CDATA   #IMPLIED
 cubicweb:limit             CDATA   #IMPLIED
 cubicweb:loadtype          CDATA   #IMPLIED
 cubicweb:loadurl           CDATA   #IMPLIED
 cubicweb:maxlength         CDATA   #IMPLIED
 cubicweb:required          CDATA   #IMPLIED
 cubicweb:rooteid           CDATA   #IMPLIED
 cubicweb:rql               CDATA   #IMPLIED
 cubicweb:size              CDATA   #IMPLIED
 cubicweb:sortvalue         CDATA   #IMPLIED
 cubicweb:target            CDATA   #IMPLIED
 cubicweb:tindex            CDATA   #IMPLIED
 cubicweb:tlunit            CDATA   #IMPLIED
 cubicweb:type              CDATA   #IMPLIED
 cubicweb:unselimg          CDATA   #IMPLIED
 cubicweb:uselabel          CDATA   #IMPLIED
 cubicweb:value             CDATA   #IMPLIED
 cubicweb:variables         CDATA   #IMPLIED
 cubicweb:vid               CDATA   #IMPLIED
 cubicweb:wdgtype           CDATA   #IMPLIED
  "> ] '''

TRANSITIONAL_DOCTYPE = u'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd" %s>\n' % CW_XHTML_EXTENSIONS
TRANSITIONAL_DOCTYPE_NOEXT = u'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
STRICT_DOCTYPE = u'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd" %s>\n' % CW_XHTML_EXTENSIONS
STRICT_DOCTYPE_NOEXT = u'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">\n'

# base view object ############################################################

class View(AppObject):
    """abstract view class, used as base for every renderable object such
    as views, templates, some components...web

    A view is instantiated to render a [part of a] result set. View
    subclasses may be parametred using the following class attributes:

    * `templatable` indicates if the view may be embeded in a main
      template or if it has to be rendered standalone (i.e. XML for
      instance)
    * if the view is not templatable, it should set the `content_type` class
      attribute to the correct MIME type (text/xhtml by default)
    * the `category` attribute may be used in the interface to regroup related
      objects together

    At instantiation time, the standard `_cw`, and `cw_rset` attributes are
    added and the `w` attribute will be set at rendering time to a write
    function to use.
    """
    __registry__ = 'views'

    templatable = True
    # content_type = 'application/xhtml+xml' # text/xhtml'
    binary = False
    add_to_breadcrumbs = True
    category = 'view'

    @property
    @deprecated('[3.6] need_navigation is deprecated, use .paginable')
    def need_navigation(self):
        return True

    @property
    def paginable(self):
        if not isinstance(self.__class__.need_navigation, property):
            warn('[3.6] %s.need_navigation is deprecated, use .paginable'
                 % self.__class__, DeprecationWarning)
            return self.need_navigation
        return True

    def __init__(self, req=None, rset=None, **kwargs):
        super(View, self).__init__(req, rset=rset, **kwargs)
        self.w = None

    @property
    def content_type(self):
        return self._cw.html_content_type()

    def set_stream(self, w=None):
        if self.w is not None:
            return
        if w is None:
            if self.binary:
                self._stream = stream = StringIO()
            else:
                self._stream = stream = UStringIO()
            w = stream.write
        else:
            stream = None
        self.w = w
        return stream

    # main view interface #####################################################

    def render(self, w=None, **context):
        """called to render a view object for a result set.

        This method is a dispatched to an actual method selected
        according to optional row and col parameters, which are locating
        a particular row or cell in the result set:

        * if row is specified, `cell_call` is called
        * if none of them is supplied, the view is considered to apply on
          the whole result set (which may be None in this case), `call` is
          called
        """
        # XXX use .cw_row/.cw_col
        row = context.get('row')
        if row is not None:
            context.setdefault('col', 0)
            view_func = self.cell_call
        else:
            view_func = self.call
        stream = self.set_stream(w)
        try:
            view_func(**context)
        except Exception:
            self.debug('view call %s failed (context=%s)', view_func, context)
            raise
        # return stream content if we have created it
        if stream is not None:
            return self._stream.getvalue()

    def tal_render(self, template, variables):
        """render a precompiled page template with variables in the given
        dictionary as context
        """
        from cubicweb.ext.tal import CubicWebContext
        context = CubicWebContext()
        context.update({'self': self, 'rset': self.cw_rset, '_' : self._cw._,
                        'req': self._cw, 'user': self._cw.user})
        context.update(variables)
        output = UStringIO()
        template.expand(context, output)
        return output.getvalue()

    dispatch = deprecated('[3.4] .dispatch is deprecated, use .render')(render)

    # should default .call() method add a <div classs="section"> around each
    # rset item
    add_div_section = True

    def call(self, **kwargs):
        """the view is called for an entire result set, by default loop
        other rows of the result set and call the same view on the
        particular row

        Views applicable on None result sets have to override this method
        """
        rset = self.cw_rset
        if rset is None:
            raise NotImplementedError, (self, "an rset is required")
        wrap = self.templatable and len(rset) > 1 and self.add_div_section
        # avoid re-selection if rset of size 1, we already have the most
        # specific view
        if rset.rowcount != 1:
            kwargs.setdefault('initargs', self.cw_extra_kwargs)
            for i in xrange(len(rset)):
                if wrap:
                    self.w(u'<div class="section">')
                self.wview(self.__regid__, rset, row=i, **kwargs)
                if wrap:
                    self.w(u"</div>")
        else:
            if wrap:
                self.w(u'<div class="section">')
            kwargs.setdefault('col', 0)
            self.cell_call(row=0, **kwargs)
            if wrap:
                self.w(u"</div>")

    def cell_call(self, row, col, **kwargs):
        """the view is called for a particular result set cell"""
        raise NotImplementedError, self

    def linkable(self):
        """return True if the view may be linked in a menu

        by default views without title are not meant to be displayed
        """
        if not getattr(self, 'title', None):
            return False
        return True

    def is_primary(self):
        return self.cw_extra_kwargs.get('is_primary', self.__regid__ == 'primary')

    def url(self):
        """return the url associated with this view. Should not be
        necessary for non linkable views, but a default implementation
        is provided anyway.
        """
        rset = self.cw_rset
        if rset is None:
            return self._cw.build_url('view', vid=self.__regid__)
        coltypes = rset.column_types(0)
        if len(coltypes) == 1:
            etype = iter(coltypes).next()
            if not self._cw.vreg.schema.eschema(etype).final:
                if len(rset) == 1:
                    entity = rset.get_entity(0, 0)
                    return entity.absolute_url(vid=self.__regid__)
            # don't want to generate /<etype> url if there is some restriction
            # on something else than the entity type
            restr = rset.syntax_tree().children[0].where
            # XXX norestriction is not correct here. For instance, in cases like
            # "Any P,N WHERE P is Project, P name N" norestriction should equal
            # True
            norestriction = (isinstance(restr, nodes.Relation) and
                             restr.is_types_restriction())
            if norestriction:
                return self._cw.build_url(etype.lower(), vid=self.__regid__)
        return self._cw.build_url('view', rql=rset.printable_rql(), vid=self.__regid__)

    def set_request_content_type(self):
        """set the content type returned by this view"""
        self._cw.set_content_type(self.content_type)

    # view utilities ##########################################################

    def wview(self, __vid, rset=None, __fallback_vid=None, **kwargs):
        """shortcut to self.view method automatically passing self.w as argument
        """
        self._cw.view(__vid, rset, __fallback_vid, w=self.w, **kwargs)

    # XXX Template bw compat
    template = deprecated('[3.4] .template is deprecated, use .view')(wview)

    def whead(self, data):
        self._cw.html_headers.write(data)

    def wdata(self, data):
        """simple helper that escapes `data` and writes into `self.w`"""
        self.w(xml_escape(data))

    def html_headers(self):
        """return a list of html headers (eg something to be inserted between
        <head> and </head> of the returned page

        by default return a meta tag to disable robot indexation of the page
        """
        return [NOINDEX]

    def page_title(self):
        """returns a title according to the result set - used for the
        title in the HTML header
        """
        vtitle = self._cw.form.get('vtitle')
        if vtitle:
            return self._cw._(vtitle)
        # class defined title will only be used if the resulting title doesn't
        # seem clear enough
        vtitle = getattr(self, 'title', None) or u''
        if vtitle:
            vtitle = self._cw._(vtitle)
        rset = self.cw_rset
        if rset and rset.rowcount:
            if rset.rowcount == 1:
                try:
                    entity = rset.complete_entity(0, 0)
                    # use long_title to get context information if any
                    clabel = entity.dc_long_title()
                except NotAnEntity:
                    clabel = display_name(self._cw, rset.description[0][0])
                    clabel = u'%s (%s)' % (clabel, vtitle)
            else :
                etypes = rset.column_types(0)
                if len(etypes) == 1:
                    etype = iter(etypes).next()
                    clabel = display_name(self._cw, etype, 'plural')
                else :
                    clabel = u'#[*] (%s)' % vtitle
        else:
            clabel = vtitle
        return u'%s (%s)' % (clabel, self._cw.property_value('ui.site-title'))

    @deprecated('[3.10] use vreg["etypes"].etype_class(etype).cw_create_url(req)')
    def create_url(self, etype, **kwargs):
        """ return the url of the entity creation form for a given entity type"""
        return self._cw.vreg["etypes"].etype_class(etype).cw_create_url(
            self._cw, **kwargs)

    def field(self, label, value, row=True, show_label=True, w=None, tr=True,
              table=False):
        """read-only field"""
        if w is None:
            w = self.w
        if table:
            w(u'<tr class="entityfield">')
        else:
            w(u'<div class="entityfield">')
        if show_label and label:
            if tr:
                label = display_name(self._cw, label)
            if table:
                w(u'<th>%s</th>' % label)
            else:
                w(u'<span class="label">%s</span> ' % label)
        if table:
            if not (show_label and label):
                w(u'<td colspan="2">%s</td></tr>' % value)
            else:
                w(u'<td>%s</td></tr>' % value)
        else:
            w(u'<span>%s</span></div>' % value)



# concrete views base classes #################################################

class EntityView(View):
    """base class for views applying on an entity (i.e. uniform result set)"""
    __select__ = non_final_entity()
    category = _('entityview')

    def call(self, **kwargs):
        if self.cw_rset is None:
            # * cw_extra_kwargs is the place where extra selection arguments are
            #   stored
            # * when calling req.view('somevid', entity=entity), 'entity' ends
            #   up in cw_extra_kwargs and kwargs
            #
            # handle that to avoid a TypeError with a sanity check
            #
            # Notice that could probably be avoided by handling entity_call in
            # .render
            entity = self.cw_extra_kwargs.pop('entity')
            if 'entity' in kwargs:
                assert kwargs.pop('entity') is entity
            self.entity_call(entity, **kwargs)
        else:
            super(EntityView, self).call(**kwargs)

    def cell_call(self, row, col, **kwargs):
        self.entity_call(self.cw_rset.get_entity(row, col), **kwargs)

    def entity_call(self, entity, **kwargs):
        raise NotImplementedError()


class StartupView(View):
    """base class for views which doesn't need a particular result set to be
    displayed (so they can always be displayed !)
    """
    __select__ = none_rset()

    category = _('startupview')

    def html_headers(self):
        """return a list of html headers (eg something to be inserted between
        <head> and </head> of the returned page

        by default startup views are indexed
        """
        return []


class EntityStartupView(EntityView):
    """base class for entity views which may also be applied to None
    result set (usually a default rql is provided by the view class)
    """
    __select__ = none_rset() | non_final_entity()

    default_rql = None

    def __init__(self, req, rset=None, **kwargs):
        super(EntityStartupView, self).__init__(req, rset=rset, **kwargs)
        if rset is None:
            # this instance is not in the "entityview" category
            self.category = 'startupview'

    def startup_rql(self):
        """return some rql to be executed if the result set is None"""
        return self.default_rql

    def call(self, **kwargs):
        """override call to execute rql returned by the .startup_rql method if
        necessary
        """
        rset = self.cw_rset
        if rset is None:
            rset = self.cw_rset = self._cw.execute(self.startup_rql())
        for i in xrange(len(rset)):
            self.wview(self.__regid__, rset, row=i, **kwargs)


class AnyRsetView(View):
    """base class for views applying on any non empty result sets"""
    __select__ = nonempty_rset()

    category = _('anyrsetview')

    def columns_labels(self, mainindex=0, tr=True):
        if tr:
            translate = lambda val, req=self._cw: display_name(req, val)
        else:
            translate = lambda val: val
        # XXX [0] because of missing Union support
        rqlstdescr = self.cw_rset.syntax_tree().get_description(mainindex,
                                                                translate)[0]
        labels = []
        for colidx, label in enumerate(rqlstdescr):
            try:
                label = getattr(self, 'label_column_%s' % colidx)()
            except AttributeError:
                # compute column header
                if label == 'Any': # find a better label
                    label = ','.join(translate(et)
                                     for et in self.cw_rset.column_types(colidx))
            labels.append(label)
        return labels


# concrete template base classes ##############################################

class MainTemplate(View):
    """main template are primary access point to render a full HTML page.
    There is usually at least a regular main template and a simple fallback
    one to display error if the first one failed
    """

    @property
    def doctype(self):
        if self._cw.xhtml_browser():
            return STRICT_DOCTYPE
        return STRICT_DOCTYPE_NOEXT

    def set_stream(self, w=None):
        if self.w is not None:
            return
        if w is None:
            if self.binary:
                self._stream = stream = StringIO()
            else:
                self._stream = stream = HTMLStream(self._cw)
            w = stream.write
        else:
            stream = None
        self.w = w
        return stream

    def write_doctype(self, xmldecl=True):
        assert isinstance(self._stream, HTMLStream)
        self._stream.doctype = self.doctype
        if not xmldecl:
            self._stream.xmldecl = u''

    def linkable(self):
        return False

# concrete component base classes #############################################

class ReloadableMixIn(object):
    """simple mixin for reloadable parts of UI"""

    def user_callback(self, cb, args, msg=None, nonify=False):
        """register the given user callback and return an url to call it ready to be
        inserted in html
        """
        self._cw.add_js('cubicweb.ajax.js')
        if nonify:
            _cb = cb
            def cb(*args):
                _cb(*args)
        cbname = self._cw.register_onetime_callback(cb, *args)
        return self.build_js(cbname, xml_escape(msg or ''))

    def build_update_js_call(self, cbname, msg):
        rql = self.cw_rset.printable_rql()
        return "javascript: %s" % js.userCallbackThenUpdateUI(
            cbname, self.__regid__, rql, msg, self.__registry__, self.domid)

    def build_reload_js_call(self, cbname, msg):
        return "javascript: %s" % js.userCallbackThenReloadPage(cbname, msg)

    build_js = build_update_js_call # expect updatable component by default

    @property
    def domid(self):
        return domid(self.__regid__)

    @deprecated('[3.10] use .domid property')
    def div_id(self):
        return self.domid


class Component(ReloadableMixIn, View):
    """base class for components"""
    __registry__ = 'components'
    __select__ = yes()

    # XXX huummm, much probably useless (should be...)
    htmlclass = 'mainRelated'
    @property
    def cssclass(self):
        return '%s %s' % (self.htmlclass, domid(self.__regid__))

    # XXX should rely on ReloadableMixIn.domid
    @property
    def domid(self):
        return '%sComponent' % domid(self.__regid__)

    @deprecated('[3.10] use .cssclass property')
    def div_class(self):
        return self.cssclass


class Adapter(AppObject):
    """base class for adapters"""
    __registry__ = 'adapters'


def implements_adapter_compat(iface):
    def _pre39_compat(func):
        def decorated(self, *args, **kwargs):
            entity = self.entity
            if hasattr(entity, func.__name__):
                warn('[3.9] %s method is deprecated, define it on a custom '
                     '%s for %s instead' % (func.__name__, iface,
                                            classid(entity.__class__)),
                     DeprecationWarning)
                member = getattr(entity, func.__name__)
                if callable(member):
                    return member(*args, **kwargs)
                return member
            return func(self, *args, **kwargs)
        decorated.decorated = func
        return decorated
    return _pre39_compat


def unwrap_adapter_compat(cls):
    parent = cls.__bases__[0]
    for member_name in dir(parent):
        member = getattr(parent, member_name)
        if isinstance(member, types.MethodType) and hasattr(member.im_func, 'decorated') and not member_name in cls.__dict__:
            method = new.instancemethod(member.im_func.decorated, None, cls)
            setattr(cls, member_name, method)


class auto_unwrap_bw_compat(type):
    def __new__(mcs, name, bases, classdict):
        cls = type.__new__(mcs, name, bases, classdict)
        if not classdict.get('__needs_bw_compat__'):
            unwrap_adapter_compat(cls)
        return cls


class EntityAdapter(Adapter):
    """base class for entity adapters (eg adapt an entity to an interface)"""
    __metaclass__ = auto_unwrap_bw_compat
    def __init__(self, _cw, **kwargs):
        try:
            self.entity = kwargs.pop('entity')
        except KeyError:
            self.entity = kwargs['rset'].get_entity(kwargs.get('row') or 0,
                                                    kwargs.get('col') or 0)
        Adapter.__init__(self, _cw, **kwargs)
