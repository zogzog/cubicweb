"""abstract views and templates classes for CubicWeb web client


:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from cStringIO import StringIO

from logilab.mtconverter import html_escape

from cubicweb import NotAnEntity, NoSelectableObject
from cubicweb.selectors import (yes, match_user_groups, implements,
                                nonempty_rset, none_rset)
from cubicweb.selectors import require_group_compat, accepts_compat
from cubicweb.appobject import AppRsetObject
from cubicweb.utils import UStringIO, HTMLStream
from cubicweb.vregistry import yes_registerer
from cubicweb.common.registerers import accepts_registerer, priority_registerer, yes_registerer

_ = unicode


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

 cubicweb:sortvalue         CDATA   #IMPLIED
 cubicweb:target            CDATA   #IMPLIED
 cubicweb:limit             CDATA   #IMPLIED
 cubicweb:type              CDATA   #IMPLIED
 cubicweb:loadtype          CDATA   #IMPLIED
 cubicweb:wdgtype           CDATA   #IMPLIED
 cubicweb:initfunc          CDATA   #IMPLIED
 cubicweb:inputid           CDATA   #IMPLIED
 cubicweb:tindex            CDATA   #IMPLIED
 cubicweb:inputname         CDATA   #IMPLIED
 cubicweb:value             CDATA   #IMPLIED
 cubicweb:required          CDATA   #IMPLIED
 cubicweb:accesskey         CDATA   #IMPLIED
 cubicweb:maxlength         CDATA   #IMPLIED
 cubicweb:variables         CDATA   #IMPLIED
 cubicweb:displayactions    CDATA   #IMPLIED
 cubicweb:fallbackvid       CDATA   #IMPLIED
 cubicweb:vid               CDATA   #IMPLIED
 cubicweb:rql               CDATA   #IMPLIED
 cubicweb:actualrql         CDATA   #IMPLIED
 cubicweb:rooteid           CDATA   #IMPLIED
 cubicweb:dataurl           CDATA   #IMPLIED
 cubicweb:size              CDATA   #IMPLIED
 cubicweb:tlunit            CDATA   #IMPLIED
 cubicweb:loadurl           CDATA   #IMPLIED
 cubicweb:uselabel          CDATA   #IMPLIED
 cubicweb:facetargs         CDATA   #IMPLIED
 cubicweb:facetName         CDATA   #IMPLIED
  "> ] '''

TRANSITIONAL_DOCTYPE = u'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd" %s>\n'

STRICT_DOCTYPE = u'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd" %s>\n'

# base view object ############################################################

class View(AppRsetObject):
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

    At instantiation time, the standard `req`, `rset`, and `cursor`
    attributes are added and the `w` attribute will be set at rendering
    time to a write function to use.
    """
    __registerer__ = priority_registerer
    __registry__ = 'views'

    templatable = True
    need_navigation = True
    # content_type = 'application/xhtml+xml' # text/xhtml'
    binary = False
    add_to_breadcrumbs = True
    category = 'view'

    def __init__(self, req=None, rset=None):
        super(View, self).__init__(req, rset)
        self.w = None

    @property
    def content_type(self):
        if self.req.xhtml_browser():
            return 'application/xhtml+xml'
        return 'text/html'

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

    def dispatch(self, w=None, **context):
        """called to render a view object for a result set.

        This method is a dispatched to an actual method selected
        according to optional row and col parameters, which are locating
        a particular row or cell in the result set:

        * if row [and col] are specified, `cell_call` is called
        * if none of them is supplied, the view is considered to apply on
          the whole result set (which may be None in this case), `call` is
          called
        """
        row, col = context.get('row'), context.get('col')
        if row is not None:
            context.setdefault('col', 0)
            view_func = self.cell_call
        else:
            view_func = self.call
        stream = self.set_stream(w)
        # stream = self.set_stream(context)
        view_func(**context)
        # return stream content if we have created it
        if stream is not None:
            return self._stream.getvalue()

    # should default .call() method add a <div classs="section"> around each
    # rset item
    add_div_section = True

    def call(self, **kwargs):
        """the view is called for an entire result set, by default loop
        other rows of the result set and call the same view on the
        particular row

        Views applicable on None result sets have to override this method
        """
        rset = self.rset
        if rset is None:
            raise NotImplementedError, self
        wrap = self.templatable and len(rset) > 1 and self.add_div_section
        for i in xrange(len(rset)):
            if wrap:
                self.w(u'<div class="section">')
            self.wview(self.id, rset, row=i, **kwargs)
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
        return self.id == 'primary'

    def url(self):
        """return the url associated with this view. Should not be
        necessary for non linkable views, but a default implementation
        is provided anyway.
        """
        try:
            return self.build_url(vid=self.id, rql=self.req.form['rql'])
        except KeyError:
            return self.build_url(vid=self.id)

    def set_request_content_type(self):
        """set the content type returned by this view"""
        self.req.set_content_type(self.content_type)

    # view utilities ##########################################################

    def view(self, __vid, rset, __fallback_vid=None, **kwargs):
        """shortcut to self.vreg.render method avoiding to pass self.req"""
        try:
            view = self.vreg.select_view(__vid, self.req, rset, **kwargs)
        except NoSelectableObject:
            if __fallback_vid is None:
                raise
            view = self.vreg.select_view(__fallback_vid, self.req, rset, **kwargs)
        return view.dispatch(**kwargs)

    def wview(self, __vid, rset, __fallback_vid=None, **kwargs):
        """shortcut to self.view method automatically passing self.w as argument
        """
        self.view(__vid, rset, __fallback_vid, w=self.w, **kwargs)

    def whead(self, data):
        self.req.html_headers.write(data)

    def wdata(self, data):
        """simple helper that escapes `data` and writes into `self.w`"""
        self.w(html_escape(data))

    def action(self, actionid, row=0):
        """shortcut to get action object with id `actionid`"""
        return self.vreg.select_action(actionid, self.req, self.rset,
                                       row=row)

    def action_url(self, actionid, label=None, row=0):
        """simple method to be able to display `actionid` as a link anywhere
        """
        action = self.vreg.select_action(actionid, self.req, self.rset,
                                         row=row)
        if action:
            label = label or self.req._(action.title)
            return u'<a href="%s">%s</a>' % (html_escape(action.url()), label)
        return u''

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
        vtitle = self.req.form.get('vtitle')
        if vtitle:
            return self.req._(vtitle)
        # class defined title will only be used if the resulting title doesn't
        # seem clear enough
        vtitle = getattr(self, 'title', None) or u''
        if vtitle:
            vtitle = self.req._(vtitle)
        rset = self.rset
        if rset and rset.rowcount:
            if rset.rowcount == 1:
                try:
                    entity = self.complete_entity(0)
                    # use long_title to get context information if any
                    clabel = entity.dc_long_title()
                except NotAnEntity:
                    clabel = display_name(self.req, rset.description[0][0])
                    clabel = u'%s (%s)' % (clabel, vtitle)
            else :
                etypes = rset.column_types(0)
                if len(etypes) == 1:
                    etype = iter(etypes).next()
                    clabel = display_name(self.req, etype, 'plural')
                else :
                    clabel = u'#[*] (%s)' % vtitle
        else:
            clabel = vtitle
        return u'%s (%s)' % (clabel, self.req.property_value('ui.site-title'))

    def output_url_builder( self, name, url, args ):
        self.w(u'<script language="JavaScript"><!--\n' \
               u'function %s( %s ) {\n' % (name, ','.join(args) ) )
        url_parts = url.split("%s")
        self.w(u' url="%s"' % url_parts[0] )
        for arg, part in zip(args, url_parts[1:]):
            self.w(u'+str(%s)' % arg )
            if part:
                self.w(u'+"%s"' % part)
        self.w('\n document.window.href=url;\n')
        self.w('}\n-->\n</script>\n')

    def create_url(self, etype, **kwargs):
        """ return the url of the entity creation form for a given entity type"""
        return self.req.build_url('add/%s'%etype, **kwargs)
    
    def field(self, label, value, row=True, show_label=True, w=None, tr=True):
        """ read-only field """
        if w is None:
            w = self.w
        if row:
            w(u'<div class="row">')
        if show_label:
            if tr:
                label = display_name(self.req, label)
            w(u'<span class="label">%s</span>' % label)
        w(u'<div class="field">%s</div>' % value)
        if row:
            w(u'</div>')


# concrete views base classes #################################################

class EntityView(View):
    """base class for views applying on an entity (i.e. uniform result set)
    """
    # XXX deprecate
    __registerer__ = accepts_registerer
    __select__ = implements('Any')
    registered = accepts_compat(View.registered.im_func)

    category = 'entityview'


class StartupView(View):
    """base class for views which doesn't need a particular result set
    to be displayed (so they can always be displayed !)
    """
    __registerer__ = priority_registerer
    __select__ = none_rset()
    registered = require_group_compat(View.registered.im_func)
    
    category = 'startupview'
    
    def url(self):
        """return the url associated with this view. We can omit rql here"""
        return self.build_url('view', vid=self.id)

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
    __select__ = none_rset() | implements('Any')

    default_rql = None

    def __init__(self, req, rset):
        super(EntityStartupView, self).__init__(req, rset)
        if rset is None:
            # this instance is not in the "entityview" category
            self.category = 'startupview'

    def startup_rql(self):
        """return some rql to be executedif the result set is None"""
        return self.default_rql

    def call(self, **kwargs):
        """override call to execute rql returned by the .startup_rql
        method if necessary
        """
        if self.rset is None:
            self.rset = self.req.execute(self.startup_rql())
        rset = self.rset
        for i in xrange(len(rset)):
            self.wview(self.id, rset, row=i, **kwargs)

    def url(self):
        """return the url associated with this view. We can omit rql if we
        are on a result set on which we do not apply.
        """
        if not self.__select__(self.req, self.rset):
            return self.build_url(vid=self.id)
        return super(EntityStartupView, self).url()


class AnyRsetView(View):
    """base class for views applying on any non empty result sets"""
    __select__ = nonempty_rset()

    category = 'anyrsetview'

    def columns_labels(self, tr=True):
        if tr:
            translate = display_name
        else:
            translate = lambda req, val: val
        rqlstdescr = self.rset.syntax_tree().get_description()[0] # XXX missing Union support
        labels = []
        for colindex, attr in enumerate(rqlstdescr):
            # compute column header
            if colindex == 0 or attr == 'Any': # find a better label
                label = ','.join(translate(self.req, et)
                                 for et in self.rset.column_types(colindex))
            else:
                label = translate(self.req, attr)
            labels.append(label)
        return labels

    
# concrete template base classes ##############################################

class Template(View):
    """a template is almost like a view, except that by default a template
    is only used globally (i.e. no result set adaptation)
    """
    __registry__ = 'templates'
    __select__ = yes()

    registered = require_group_compat(View.registered.im_func)

    def template(self, oid, **kwargs):
        """shortcut to self.registry.render method on the templates registry"""
        w = kwargs.pop('w', self.w)
        self.vreg.render('templates', oid, self.req, w=w, **kwargs)


class MainTemplate(Template):
    """main template are primary access point to render a full HTML page.
    There is usually at least a regular main template and a simple fallback
    one to display error if the first one failed
    """
    base_doctype = STRICT_DOCTYPE

    @property
    def doctype(self):
        if self.req.xhtml_browser():
            return self.base_doctype % CW_XHTML_EXTENSIONS
        return self.base_doctype % ''

    def set_stream(self, w=None, templatable=True):
        if templatable and self.w is not None:
            return

        if w is None:
            if self.binary:
                self._stream = stream = StringIO()
            elif not templatable:
                # not templatable means we're using a non-html view, we don't
                # want the HTMLStream stuff to interfere during data generation
                self._stream = stream = UStringIO()
            else:
                self._stream = stream = HTMLStream(self.req)
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

# concrete component base classes #############################################

class ReloadableMixIn(object):
    """simple mixin for reloadable parts of UI"""
    
    def user_callback(self, cb, args, msg=None, nonify=False):
        """register the given user callback and return an url to call it ready to be
        inserted in html
        """
        self.req.add_js('cubicweb.ajax.js')
        if nonify:
            _cb = cb
            def cb(*args):
                _cb(*args)
        cbname = self.req.register_onetime_callback(cb, *args)
        return self.build_js(cbname, html_escape(msg or ''))
        
    def build_update_js_call(self, cbname, msg):
        rql = html_escape(self.rset.printable_rql())
        return "javascript:userCallbackThenUpdateUI('%s', '%s', '%s', '%s', '%s', '%s')" % (
            cbname, self.id, rql, msg, self.__registry__, self.div_id())
    
    def build_reload_js_call(self, cbname, msg):
        return "javascript:userCallbackThenReloadPage('%s', '%s')" % (cbname, msg)

    build_js = build_update_js_call # expect updatable component by default
    
    def div_id(self):
        return ''


class Component(ReloadableMixIn, View):
    """base class for components"""
    __registry__ = 'components'
    __registerer__ = yes_registerer
    __select__ = yes()
    property_defs = {
        _('visible'):  dict(type='Boolean', default=True,
                            help=_('display the box or not')),
        }    

    def div_class(self):
        return '%s %s' % (self.propval('htmlclass'), self.id)

    def div_id(self):
        return '%sComponent' % self.id
