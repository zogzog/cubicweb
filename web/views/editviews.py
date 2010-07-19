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
"""Some views used to help to the edition process

"""
__docformat__ = "restructuredtext en"
_ = unicode

from logilab.common.decorators import cached
from logilab.mtconverter import xml_escape

from cubicweb import typed_eid
from cubicweb.view import EntityView, StartupView
from cubicweb.selectors import (one_line_rset, non_final_entity,
                                match_search_state)
from cubicweb.web import httpcache
from cubicweb.web.views import baseviews, linksearch_select_url


class SearchForAssociationView(EntityView):
    """view called by the edition view when the user asks to search for
    something to link to the edited eid
    """
    __regid__ = 'search-associate'
    __select__ = (one_line_rset() & match_search_state('linksearch')
                  & non_final_entity())

    title = _('search for association')

    def cell_call(self, row, col):
        rset, vid, divid, paginate = self.filter_box_context_info()
        self.cw_rset = rset
        self.w(u'<div id="%s">' % divid)
        self.paginate()
        self.wview(vid, rset, 'noresult')
        self.w(u'</div>')

    @cached
    def filter_box_context_info(self):
        entity = self.cw_rset.get_entity(0, 0)
        role, eid, rtype, etype = self._cw.search_state[1]
        assert entity.eid == typed_eid(eid)
        # the default behaviour is to fetch all unrelated entities and display
        # them. Use fetch_order and not fetch_unrelated_order as sort method
        # since the latter is mainly there to select relevant items in the combo
        # box, it doesn't give interesting result in this context
        rql, args = entity.unrelated_rql(rtype, etype, role,
                                         ordermethod='fetch_order',
                                         vocabconstraints=False)
        rset = self._cw.execute(rql, args, tuple(args))
        return rset, 'list', "search-associate-content", True


class OutOfContextSearch(EntityView):
    __regid__ = 'outofcontext-search'
    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        erset = entity.as_rset()
        if self._cw.match_search_state(erset):
            self.w(u'<a href="%s" title="%s">%s</a>&#160;<a href="%s" title="%s">[...]</a>' % (
                xml_escape(linksearch_select_url(self._cw, erset)),
                self._cw._('select this entity'),
                xml_escape(entity.view('textoutofcontext')),
                xml_escape(entity.absolute_url(vid='primary')),
                self._cw._('view detail for this entity')))
        else:
            entity.view('outofcontext', w=self.w)


class ComboboxView(EntityView):
    """the view used in combobox (unrelated entities)

    THIS IS A TEXT VIEW. DO NOT HTML_ESCAPE
    """
    __regid__ = 'combobox'
    title = None

    def cell_call(self, row, col):
        """the combo-box view for an entity: same as text out of context view
        by default
        """
        self.wview('textoutofcontext', self.cw_rset, row=row, col=col)


class EditableFinalView(baseviews.FinalView):
    """same as FinalView but enables inplace-edition when possible"""
    __regid__ = 'editable-final'

    def cell_call(self, row, col, props=None):
        entity, rtype = self.cw_rset.related_entity(row, col)
        if entity is not None:
            self.w(entity.view('reledit', rtype=rtype))
        else:
            super(EditableFinalView, self).cell_call(row, col, props)

try:
    from cubicweb.web import captcha
except ImportError:
    # PIL not installed
    pass
else:
    class CaptchaView(StartupView):
        __regid__ = 'captcha'

        http_cache_manager = httpcache.NoHTTPCacheManager
        binary = True
        templatable = False
        content_type = 'image/jpg'

        def call(self):
            text, data = captcha.captcha(self._cw.vreg.config['captcha-font-file'],
                                         self._cw.vreg.config['captcha-font-size'])
            key = self._cw.form.get('captchakey', 'captcha')
            self._cw.session.data[key] = text
            self.w(data.read())
