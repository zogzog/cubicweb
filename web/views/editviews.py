"""Some views used to help to the edition process

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"
_ = unicode

from simplejson import dumps

from logilab.common.decorators import cached
from logilab.mtconverter import xml_escape

from cubicweb import typed_eid, uilib
from cubicweb.schema import display_name
from cubicweb.view import EntityView
from cubicweb.selectors import (one_line_rset, non_final_entity,
                                match_search_state, match_form_params)
from cubicweb.web import formwidgets as fw, formfields as ff
from cubicweb.web.views import baseviews, linksearch_select_url


def relation_id(eid, rtype, role, reid):
    """return an identifier for a relation between two entities"""
    if role == 'subject':
        return u'%s:%s:%s' % (eid, rtype, reid)
    return u'%s:%s:%s' % (reid, rtype, eid)

def toggleable_relation_link(eid, nodeid, label='x'):
    """return javascript snippet to delete/undelete a relation between two
    entities
    """
    js = u"javascript: togglePendingDelete('%s', %s);" % (
        nodeid, xml_escape(dumps(eid)))
    return u'[<a class="handle" href="%s" id="handle%s">%s</a>]' % (
        js, nodeid, label)


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


def get_pending_inserts(req, eid=None):
    """shortcut to access req's pending_insert entry

    This is where are stored relations being added while editing
    an entity. This used to be stored in a temporary cookie.
    """
    pending = req.get_session_data('pending_insert') or ()
    return ['%s:%s:%s' % (subj, rel, obj) for subj, rel, obj in pending
            if eid is None or eid in (subj, obj)]

def get_pending_deletes(req, eid=None):
    """shortcut to access req's pending_delete entry

    This is where are stored relations being removed while editing
    an entity. This used to be stored in a temporary cookie.
    """
    pending = req.get_session_data('pending_delete') or ()
    return ['%s:%s:%s' % (subj, rel, obj) for subj, rel, obj in pending
            if eid is None or eid in (subj, obj)]

def parse_relations_descr(rdescr):
    """parse a string describing some relations, in the form
    subjeids:rtype:objeids
    where subjeids and objeids are eids separeted by a underscore

    return an iterator on (subject eid, relation type, object eid) found
    """
    for rstr in rdescr:
        subjs, rtype, objs = rstr.split(':')
        for subj in subjs.split('_'):
            for obj in objs.split('_'):
                yield typed_eid(subj), rtype, typed_eid(obj)

def delete_relations(req, rdefs):
    """delete relations from the repository"""
    # FIXME convert to using the syntax subject:relation:eids
    execute = req.execute
    for subj, rtype, obj in parse_relations_descr(rdefs):
        rql = 'DELETE X %s Y where X eid %%(x)s, Y eid %%(y)s' % rtype
        execute(rql, {'x': subj, 'y': obj}, ('x', 'y'))
    req.set_message(req._('relations deleted'))

def insert_relations(req, rdefs):
    """insert relations into the repository"""
    execute = req.execute
    for subj, rtype, obj in parse_relations_descr(rdefs):
        rql = 'SET X %s Y where X eid %%(x)s, Y eid %%(y)s' % rtype
        execute(rql, {'x': subj, 'y': obj}, ('x', 'y'))



class GenericRelationsWidget(fw.FieldWidget):

    def render(self, form, field, renderer):
        stream = []
        w = stream.append
        req = form._cw
        _ = req._
        __ = _
        eid = form.edited_entity.eid
        w(u'<table id="relatedEntities">')
        for rschema, role, related in field.relations_table(form):
            # already linked entities
            if related:
                w(u'<tr><th class="labelCol">%s</th>' % rschema.display_name(req, role))
                w(u'<td>')
                w(u'<ul>')
                for viewparams in related:
                    w(u'<li class="invisible">%s<div id="span%s" class="%s">%s</div></li>'
                      % (viewparams[1], viewparams[0], viewparams[2], viewparams[3]))
                if not form.force_display and form.maxrelitems < len(related):
                    link = (u'<span class="invisible">'
                            '[<a href="javascript: window.location.href+=\'&amp;__force_display=1\'">%s</a>]'
                            '</span>' % _('view all'))
                    w(u'<li class="invisible">%s</li>' % link)
                w(u'</ul>')
                w(u'</td>')
                w(u'</tr>')
        pendings = list(field.restore_pending_inserts(form))
        if not pendings:
            w(u'<tr><th>&#160;</th><td>&#160;</td></tr>')
        else:
            for row in pendings:
                # soon to be linked to entities
                w(u'<tr id="tr%s">' % row[1])
                w(u'<th>%s</th>' % row[3])
                w(u'<td>')
                w(u'<a class="handle" title="%s" href="%s">[x]</a>' %
                  (_('cancel this insert'), row[2]))
                w(u'<a id="a%s" class="editionPending" href="%s">%s</a>'
                  % (row[1], row[4], xml_escape(row[5])))
                w(u'</td>')
                w(u'</tr>')
        w(u'<tr id="relationSelectorRow_%s" class="separator">' % eid)
        w(u'<th class="labelCol">')
        w(u'<select id="relationSelector_%s" tabindex="%s" '
          'onchange="javascript:showMatchingSelect(this.options[this.selectedIndex].value,%s);">'
          % (eid, req.next_tabindex(), xml_escape(dumps(eid))))
        w(u'<option value="">%s</option>' % _('select a relation'))
        for i18nrtype, rschema, role in field.relations:
            # more entities to link to
            w(u'<option value="%s_%s">%s</option>' % (rschema, role, i18nrtype))
        w(u'</select>')
        w(u'</th>')
        w(u'<td id="unrelatedDivs_%s"></td>' % eid)
        w(u'</tr>')
        w(u'</table>')
        return '\n'.join(stream)


class GenericRelationsField(ff.Field):
    widget = GenericRelationsWidget

    def __init__(self, relations, name='_cw_generic_field', **kwargs):
        assert relations
        kwargs['eidparam'] = True
        super(GenericRelationsField, self).__init__(name, **kwargs)
        self.relations = relations

    def process_posted(self, form):
        todelete = get_pending_deletes(form._cw)
        if todelete:
            delete_relations(form._cw, todelete)
        toinsert = get_pending_inserts(form._cw)
        if toinsert:
            insert_relations(form._cw, toinsert)
        return ()

    def relations_table(self, form):
        """yiels 3-tuples (rtype, role, related_list)
        where <related_list> itself a list of :
          - node_id (will be the entity element's DOM id)
          - appropriate javascript's togglePendingDelete() function call
          - status 'pendingdelete' or ''
          - oneline view of related entity
        """
        entity = form.edited_entity
        pending_deletes = get_pending_deletes(form._cw, entity.eid)
        for label, rschema, role in self.relations:
            related = []
            if entity.has_eid():
                rset = entity.related(rschema, role, limit=form.related_limit)
                if rschema.has_perm(form._cw, 'delete'):
                    toggleable_rel_link_func = toggleable_relation_link
                else:
                    toggleable_rel_link_func = lambda x, y, z: u''
                for row in xrange(rset.rowcount):
                    nodeid = relation_id(entity.eid, rschema, role,
                                         rset[row][0])
                    if nodeid in pending_deletes:
                        status, label = u'pendingDelete', '+'
                    else:
                        status, label = u'', 'x'
                    dellink = toggleable_rel_link_func(entity.eid, nodeid, label)
                    eview = form._cw.view('oneline', rset, row=row)
                    related.append((nodeid, dellink, status, eview))
            yield (rschema, role, related)

    def restore_pending_inserts(self, form):
        """used to restore edition page as it was before clicking on
        'search for <some entity type>'
        """
        entity = form.edited_entity
        pending_inserts = set(get_pending_inserts(form._cw, form.edited_entity.eid))
        for pendingid in pending_inserts:
            eidfrom, rtype, eidto = pendingid.split(':')
            if typed_eid(eidfrom) == entity.eid: # subject
                label = display_name(form._cw, rtype, 'subject',
                                     entity.__regid__)
                reid = eidto
            else:
                label = display_name(form._cw, rtype, 'object',
                                     entity.__regid__)
                reid = eidfrom
            jscall = "javascript: cancelPendingInsert('%s', 'tr', null, %s);" \
                     % (pendingid, entity.eid)
            rset = form._cw.eid_rset(reid)
            eview = form._cw.view('text', rset, row=0)
            # XXX find a clean way to handle baskets
            if rset.description[0][0] == 'Basket':
                eview = '%s (%s)' % (eview, display_name(form._cw, 'Basket'))
            yield rtype, pendingid, jscall, label, reid, eview


class UnrelatedDivs(EntityView):
    __regid__ = 'unrelateddivs'
    __select__ = match_form_params('relation')

    def cell_call(self, row, col):
        entity = self.cw_rset.get_entity(row, col)
        relname, role = self._cw.form.get('relation').rsplit('_', 1)
        rschema = self._cw.vreg.schema.rschema(relname)
        hidden = 'hidden' in self._cw.form
        is_cell = 'is_cell' in self._cw.form
        self.w(self.build_unrelated_select_div(entity, rschema, role,
                                               is_cell=is_cell, hidden=hidden))

    def build_unrelated_select_div(self, entity, rschema, role,
                                   is_cell=False, hidden=True):
        options = []
        divid = 'div%s_%s_%s' % (rschema.type, role, entity.eid)
        selectid = 'select%s_%s_%s' % (rschema.type, role, entity.eid)
        if rschema.symetric or role == 'subject':
            targettypes = rschema.objects(entity.e_schema)
            etypes = '/'.join(sorted(etype.display_name(self._cw) for etype in targettypes))
        else:
            targettypes = rschema.subjects(entity.e_schema)
            etypes = '/'.join(sorted(etype.display_name(self._cw) for etype in targettypes))
        etypes = uilib.cut(etypes, self._cw.property_value('navigation.short-line-size'))
        options.append('<option>%s %s</option>' % (self._cw._('select a'), etypes))
        options += self._get_select_options(entity, rschema, role)
        options += self._get_search_options(entity, rschema, role, targettypes)
        if 'Basket' in self._cw.vreg.schema: # XXX
            options += self._get_basket_options(entity, rschema, role, targettypes)
        relname, role = self._cw.form.get('relation').rsplit('_', 1)
        return u"""\
<div class="%s" id="%s">
  <select id="%s" onchange="javascript: addPendingInsert(this.options[this.selectedIndex], %s, %s, '%s');">
    %s
  </select>
</div>
""" % (hidden and 'hidden' or '', divid, selectid,
       xml_escape(dumps(entity.eid)), is_cell and 'true' or 'null', relname,
       '\n'.join(options))

    def _get_select_options(self, entity, rschema, role):
        """add options to search among all entities of each possible type"""
        options = []
        pending_inserts = get_pending_inserts(self._cw, entity.eid)
        rtype = rschema.type
        form = self._cw.vreg['forms'].select('edition', self._cw, entity=entity)
        field = form.field_by_name(rschema, role, entity.e_schema)
        limit = self._cw.property_value('navigation.combobox-limit')
        for eview, reid in field.choices(form, limit): # XXX expect 'limit' arg on choices
            if reid is None:
                if eview: # skip blank value
                    options.append('<option class="separator">-- %s --</option>'
                                   % xml_escape(eview))
            elif reid != ff.INTERNAL_FIELD_VALUE:
                optionid = relation_id(entity.eid, rtype, role, reid)
                if optionid not in pending_inserts:
                    # prefix option's id with letters to make valid XHTML wise
                    options.append('<option id="id%s" value="%s">%s</option>' %
                                   (optionid, reid, xml_escape(eview)))
        return options

    def _get_search_options(self, entity, rschema, role, targettypes):
        """add options to search among all entities of each possible type"""
        options = []
        _ = self._cw._
        for eschema in targettypes:
            mode = '%s:%s:%s:%s' % (role, entity.eid, rschema.type, eschema)
            url = self._cw.build_url(entity.rest_path(), vid='search-associate',
                                 __mode=mode)
            options.append((eschema.display_name(self._cw),
                            '<option value="%s">%s %s</option>' % (
                xml_escape(url), _('Search for'), eschema.display_name(self._cw))))
        return [o for l, o in sorted(options)]

    def _get_basket_options(self, entity, rschema, role, targettypes):
        options = []
        rtype = rschema.type
        _ = self._cw._
        for basketeid, basketname in self._get_basket_links(self._cw.user.eid,
                                                            role, targettypes):
            optionid = relation_id(entity.eid, rtype, role, basketeid)
            options.append('<option id="%s" value="%s">%s %s</option>' % (
                optionid, basketeid, _('link to each item in'), xml_escape(basketname)))
        return options

    def _get_basket_links(self, ueid, role, targettypes):
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
        basketresultset = self._cw.execute(basketrql, {'x': ueid}, 'x')
        for result in basketresultset:
            basketitemsrql = 'Any X WHERE X in_basket B, B eid %(x)s'
            rset = self._cw.execute(basketitemsrql, {'x': result[0]}, 'x')
            basketref.append((result[0], result[1], rset))
        return basketref


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
