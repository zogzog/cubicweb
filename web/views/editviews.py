"""Some views used to help to the edition process

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

from simplejson import dumps

from logilab.common.decorators import cached
from logilab.mtconverter import html_escape

from cubicweb import typed_eid
from cubicweb.view import EntityView
from cubicweb.selectors import (one_line_rset, non_final_entity,
                                match_search_state, match_form_params)
from cubicweb.common.uilib import cut
from cubicweb.web.views import linksearch_select_url
from cubicweb.web.form import relation_id
from cubicweb.web.views.baseviews import FinalView

_ = unicode

class SearchForAssociationView(EntityView):
    """view called by the edition view when the user asks to search for
    something to link to the edited eid
    """
    id = 'search-associate'
    __select__ = (one_line_rset() & match_search_state('linksearch')
                  & non_final_entity())
    
    title = _('search for association')

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
        return rset, 'list', "search-associate-content", True


class OutOfContextSearch(EntityView):
    id = 'outofcontext-search'
    def cell_call(self, row, col):
        entity = self.entity(row, col)
        erset = entity.as_rset()
        if self.req.match_search_state(erset):
            self.w(u'<a href="%s" title="%s">%s</a>&nbsp;<a href="%s" title="%s">[...]</a>' % (
                html_escape(linksearch_select_url(self.req, erset)),
                self.req._('select this entity'),
                html_escape(entity.view('textoutofcontext')),
                html_escape(entity.absolute_url(vid='primary')),
                self.req._('view detail for this entity')))
        else:
            entity.view('outofcontext', w=self.w)

        
class UnrelatedDivs(EntityView):
    id = 'unrelateddivs'
    __select__ = match_form_params('relation')

    @property
    def limit(self):
        if self.req.form.get('__force_display'):
            return None
        return self.req.property_value('navigation.related-limit') + 1

    def cell_call(self, row, col):
        entity = self.entity(row, col)
        relname, target = self.req.form.get('relation').rsplit('_', 1)
        rschema = self.schema.rschema(relname)
        hidden = 'hidden' in self.req.form
        is_cell = 'is_cell' in self.req.form
        self.w(self.build_unrelated_select_div(entity, rschema, target,
                                               is_cell=is_cell, hidden=hidden))

    def build_unrelated_select_div(self, entity, rschema, target,
                                   is_cell=False, hidden=True):
        options = []
        divid = 'div%s_%s_%s' % (rschema.type, target, entity.eid)
        selectid = 'select%s_%s_%s' % (rschema.type, target, entity.eid)
        if rschema.symetric or target == 'subject':
            targettypes = rschema.objects(entity.e_schema)
            etypes = '/'.join(sorted(etype.display_name(self.req) for etype in targettypes))
        else:
            targettypes = rschema.subjects(entity.e_schema)
            etypes = '/'.join(sorted(etype.display_name(self.req) for etype in targettypes))
        etypes = cut(etypes, self.req.property_value('navigation.short-line-size'))
        options.append('<option>%s %s</option>' % (self.req._('select a'), etypes))
        options += self._get_select_options(entity, rschema, target)
        options += self._get_search_options(entity, rschema, target, targettypes)
        if 'Basket' in self.schema: # XXX
            options += self._get_basket_options(entity, rschema, target, targettypes)
        relname, target = self.req.form.get('relation').rsplit('_', 1)
        return u"""\
<div class="%s" id="%s">
  <select id="%s" onchange="javascript: addPendingInsert(this.options[this.selectedIndex], %s, %s, '%s');">
    %s
  </select>
</div>
""" % (hidden and 'hidden' or '', divid, selectid, html_escape(dumps(entity.eid)),
       is_cell and 'true' or 'null', relname, '\n'.join(options))

    def _get_select_options(self, entity, rschema, target):
        """add options to search among all entities of each possible type"""
        options = []
        eid = entity.eid
        pending_inserts = self.req.get_pending_inserts(eid)
        rtype = rschema.type
        for eview, reid in entity.vocabulary(rschema, target, self.limit):
            if reid is None:
                options.append('<option class="separator">-- %s --</option>' % html_escape(eview))
            else:
                optionid = relation_id(eid, rtype, target, reid)
                if optionid not in pending_inserts:
                    # prefix option's id with letters to make valid XHTML wise
                    options.append('<option id="id%s" value="%s">%s</option>' %
                                   (optionid, reid, html_escape(eview)))
        return options

    def _get_search_options(self, entity, rschema, target, targettypes):
        """add options to search among all entities of each possible type"""
        options = []
        _ = self.req._
        for eschema in targettypes:
            mode = '%s:%s:%s:%s' % (target, entity.eid, rschema.type, eschema)
            url = self.build_url(entity.rest_path(), vid='search-associate',
                                 __mode=mode)
            options.append((eschema.display_name(self.req),
                            '<option value="%s">%s %s</option>' % (
                html_escape(url), _('Search for'), eschema.display_name(self.req))))
        return [o for l, o in sorted(options)]

    def _get_basket_options(self, entity, rschema, target, targettypes):
        options = []
        rtype = rschema.type
        _ = self.req._
        for basketeid, basketname in self._get_basket_links(self.req.user.eid,
                                                            target, targettypes):
            optionid = relation_id(entity.eid, rtype, target, basketeid)
            options.append('<option id="%s" value="%s">%s %s</option>' % (
                optionid, basketeid, _('link to each item in'), html_escape(basketname)))
        return options

    def _get_basket_links(self, ueid, target, targettypes):
        targettypes = set(targettypes)
        for basketeid, basketname, elements in self._get_basket_info(ueid):
            baskettypes = elements.column_types(0)
            # if every elements in the basket can be attached to the
            # edited entity
            if baskettypes & targettypes:
                yield basketeid, basketname
            
    def _get_basket_info(self, ueid):
        basketref = []
        basketrql = 'Any B,N WHERE B is Basket, B owned_by U, U eid %(x)s, B name N'
        basketresultset = self.req.execute(basketrql, {'x': ueid}, 'x')
        for result in basketresultset:
            basketitemsrql = 'Any X WHERE X in_basket B, B eid %(x)s'
            rset = self.req.execute(basketitemsrql, {'x': result[0]}, 'x')
            basketref.append((result[0], result[1], rset))
        return basketref


class ComboboxView(EntityView):
    """the view used in combobox (unrelated entities)

    THIS IS A TEXT VIEW. DO NOT HTML_ESCAPE
    """
    id = 'combobox'
    title = None
    
    def cell_call(self, row, col):
        """the combo-box view for an entity: same as text out of context view
        by default
        """
        self.wview('textoutofcontext', self.rset, row=row, col=col)
        

class EditableFinalView(FinalView):
    """same as FinalView but enables inplace-edition when possible"""
    id = 'editable-final'
                
    def cell_call(self, row, col, props=None, displaytime=False):
        entity, rtype = self.rset.related_entity(row, col)
        if entity is not None:
            self.w(entity.view('reledit', rtype=rtype))
        else:
            super(EditableFinalView, self).cell_call(row, col, props, displaytime)
