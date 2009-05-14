"""navigation components definition for CubicWeb web client

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from logilab.mtconverter import html_escape

# don't use AnyEntity since this may cause bug with isinstance() due to reloading
from cubicweb.interfaces import IBreadCrumbs
from cubicweb.selectors import match_context_prop, one_line_rset, implements
from cubicweb.entity import Entity
from cubicweb.view import EntityView
from cubicweb.common.uilib import cut
from cubicweb.web.component import EntityVComponent

_ = unicode

def bc_title(entity):
    textsize = entity.req.property_value('navigation.short-line-size')
    return html_escape(cut(entity.dc_title(), textsize))


class BreadCrumbEntityVComponent(EntityVComponent):
    id = 'breadcrumbs'
    # register msg not generated since no entity implements IPrevNext in cubicweb itself
    title = _('contentnavigation_breadcrumbs')
    help = _('contentnavigation_breadcrumbs_description')
    __select__ = (one_line_rset() & match_context_prop() & implements(IBreadCrumbs))
    context = 'navtop'
    order = 5
    visible = False
    separator = u'&nbsp;&gt;&nbsp;'

    def call(self, view=None, first_separator=True):
        entity = self.entity(0)
        path = entity.breadcrumbs(view)
        if path:
            self.w(u'<span class="pathbar">')
            if first_separator:
                self.w(self.separator)
            root = path.pop(0)
            if isinstance(root, Entity):
                self.w(u'<a href="%s">%s</a>' % (self.req.build_url(root.id),
                                                 root.dc_type('plural')))
                self.w(self.separator)
            self.wpath_part(root, entity, not path)
            for i, parent in enumerate(path):
                self.w(self.separator)
                self.w(u"\n")
                self.wpath_part(parent, entity, i == len(path) - 1)
            self.w(u'</span>')

    def wpath_part(self, part, contextentity, last=False):
        if isinstance(part, Entity):
            if last and part.eid == contextentity.eid:
                self.w(bc_title(part))
            else:
                part.view('breadcrumbs', w=self.w)
        elif isinstance(part, tuple):
            url, title = part
            textsize = self.req.property_value('navigation.short-line-size')
            self.w(u'<a href="%s">%s</a>' % (
                html_escape(url), html_escape(cut(title, textsize))))
        else:
            textsize = self.req.property_value('navigation.short-line-size')
            self.w(cut(unicode(part), textsize))


class BreadCrumbComponent(BreadCrumbEntityVComponent):
    __registry__ = 'components'
    __select__ = (one_line_rset() & implements(IBreadCrumbs))
    visible = True


class BreadCrumbView(EntityView):
    id = 'breadcrumbs'

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        desc = cut(entity.dc_description(), 50)
        self.w(u'<a href="%s" title="%s">%s</a>' % (html_escape(entity.absolute_url()),
                                                    html_escape(desc),
                                                    bc_title(entity)))
