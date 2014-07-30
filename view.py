# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

from cStringIO import StringIO
from warnings import warn
from functools import partial

from logilab.common.deprecation import deprecated
from logilab.common.registry import yes
from logilab.mtconverter import xml_escape

from rql import nodes

from cubicweb import NotAnEntity
from cubicweb.predicates import non_final_entity, nonempty_rset, none_rset
from cubicweb.appobject import AppObject
from cubicweb.utils import UStringIO, HTMLStream
from cubicweb.uilib import domid, js
from cubicweb.schema import display_name

# robots control
NOINDEX = u'<meta name="ROBOTS" content="NOINDEX" />'
NOFOLLOW = u'<meta name="ROBOTS" content="NOFOLLOW" />'

TRANSITIONAL_DOCTYPE_NOEXT = u'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
TRANSITIONAL_DOCTYPE = TRANSITIONAL_DOCTYPE_NOEXT # bw compat

STRICT_DOCTYPE_NOEXT = u'<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">\n'
STRICT_DOCTYPE = STRICT_DOCTYPE_NOEXT # bw compat

# base view object ############################################################

class View(AppObject):
    """This class is an abstraction of a view class, used as a base class for
    every renderable object such as views, templates and other user interface
    components.

    A `View` is instantiated to render a result set or part of a result
    set. `View` subclasses may be parametrized using the following class
    attributes:

    :py:attr:`templatable` indicates if the view may be embedded in a main
      template or if it has to be rendered standalone (i.e. pure XML views must
      not be embedded in the main template of HTML pages)
    :py:attr:`content_type` if the view is not templatable, it should set the
      `content_type` class attribute to the correct MIME type (text/xhtml being
      the default)
    :py:attr:`category` this attribute may be used in the interface to regroup
      related objects (view kinds) together

    :py:attr:`paginable`

    :py:attr:`binary`


    A view writes to its output stream thanks to its attribute `w` (the
    append method of an `UStreamIO`, except for binary views).

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
    paginable = True

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
            raise NotImplementedError("%r an rset is required" % self)
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
        raise NotImplementedError(repr(self))

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
        raise NotImplementedError('%r %r' % (self.__regid__, self.__class__))


class StartupView(View):
    """base class for views which doesn't need a particular result set to be
    displayed (so they can always be displayed!)
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

    def no_entities(self, **kwargs):
        """override to display something when no entities were found"""
        pass

    def call(self, **kwargs):
        """override call to execute rql returned by the .startup_rql method if
        necessary
        """
        rset = self.cw_rset
        if rset is None:
            rset = self.cw_rset = self._cw.execute(self.startup_rql())
        if rset:
            for i in xrange(len(rset)):
                self.wview(self.__regid__, rset, row=i, **kwargs)
        else:
            self.no_entities(**kwargs)


class AnyRsetView(View):
    """base class for views applying on any non empty result sets"""
    __select__ = nonempty_rset()

    category = _('anyrsetview')

    def columns_labels(self, mainindex=0, tr=True):
        """compute the label of the rset colums

        The logic is based on :meth:`~rql.stmts.Union.get_description`.

        :param mainindex: The index of the main variable. This is an hint to get
                          more accurate label for various situation
        :type mainindex:  int

        :param tr: Should the label be translated ?
        :type tr: boolean
        """
        if tr:
            translate = partial(display_name, self._cw)
        else:
            translate = lambda val, *args,**kwargs: val
        # XXX [0] because of missing Union support
        rql_syntax_tree = self.cw_rset.syntax_tree()
        rqlstdescr = rql_syntax_tree.get_description(mainindex, translate)[0]
        labels = []
        for colidx, label in enumerate(rqlstdescr):
            labels.append(self.column_label(colidx, label, translate))
        return labels

    def column_label(self, colidx, default, translate_func=None):
        """return the label of a specified columns index

        Overwrite me if you need to compute specific label.

        :param colidx: The index of the column the call computes a label for.
        :type colidx:  int

        :param default: Default value. If ``"Any"`` the default value will be
                        recomputed as coma separated list for all possible
                        etypes name.
        :type colidx:  string

        :param translate_func: A function used to translate name.
        :type colidx:  function
        """
        label = default
        if label == 'Any':
            etypes = self.cw_rset.column_types(colidx)
            if translate_func is not None:
                etypes = map(translate_func, etypes)
            label = u','.join(etypes)
        return label



# concrete template base classes ##############################################

class MainTemplate(View):
    """main template are primary access point to render a full HTML page.
    There is usually at least a regular main template and a simple fallback
    one to display error if the first one failed
    """

    doctype = '<!DOCTYPE html>'

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

    @property
    def domid(self):
        return domid(self.__regid__)


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


class Adapter(AppObject):
    """base class for adapters"""
    __registry__ = 'adapters'


class EntityAdapter(Adapter):
    """base class for entity adapters (eg adapt an entity to an interface)"""
    def __init__(self, _cw, **kwargs):
        try:
            self.entity = kwargs.pop('entity')
        except KeyError:
            self.entity = kwargs['rset'].get_entity(kwargs.get('row') or 0,
                                                    kwargs.get('col') or 0)
        Adapter.__init__(self, _cw, **kwargs)
