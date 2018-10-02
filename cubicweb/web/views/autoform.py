# copyright 2003 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""
.. autoclass:: AutomaticEntityForm

Configuration through uicfg
```````````````````````````

It is possible to manage which and how an entity's attributes and relations
will be edited in the various contexts where the automatic entity form is used
by using proper uicfg tags.

The details of the uicfg syntax can be found in the :ref:`uicfg` chapter.

Possible relation tags that apply to entity forms are detailled below.
They are all in the :mod:`cubicweb.web.uicfg` module.

Attributes/relations display location
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``autoform_section`` specifies where to display a relation in form for a given
form type.  :meth:`tag_attribute`, :meth:`tag_subject_of` and
:meth:`tag_object_of` methods for this relation tag expect two arguments
additionally to the relation key: a `formtype` and a `section`.

`formtype` may be one of:

* 'main', the main entity form (e.g. the one you get when creating or editing an
  entity)

* 'inlined', the form for an entity inlined into another form

* 'muledit', the table form when editing multiple entities of the same type


section may be one of:

* 'hidden', don't display (not even in a hidden input)

* 'attributes', display in the attributes section

* 'relations', display in the relations section, using the generic relation
  selector combobox (available in main form only, and not usable for attributes)

* 'inlined', display target entity of the relation into an inlined form
  (available in main form only, and not for attributes)

By default, mandatory relations are displayed in the 'attributes' section,
others in 'relations' section.


Change default fields
^^^^^^^^^^^^^^^^^^^^^

Use ``autoform_field`` to replace the default field class to use for a relation
or attribute. You can put either a field class or instance as value (put a class
whenether it's possible).

.. Warning::

   `autoform_field_kwargs` should usually be used instead of
   `autoform_field`. If you put a field instance into `autoform_field`,
   `autoform_field_kwargs` values for this relation will be ignored.


Customize field options
^^^^^^^^^^^^^^^^^^^^^^^

In order to customize field options (see :class:`~cubicweb.web.formfields.Field`
for a detailed list of options), use `autoform_field_kwargs`. This rtag takes
a dictionary as arguments, that will be given to the field's contructor.

You can then put in that dictionary any arguments supported by the field
class. For instance:

.. sourcecode:: python

   # Change the content of the combobox. Here `ticket_done_in_choices` is a
   # function which returns a list of elements to populate the combobox
   autoform_field_kwargs.tag_subject_of(('Ticket', 'done_in', '*'),
                                        {'sort': False,
                                         'choices': ticket_done_in_choices})

   # Force usage of a TextInput widget for the expression attribute of
   # RQLExpression entities
   autoform_field_kwargs.tag_attribute(('RQLExpression', 'expression'),
                                       {'widget': fw.TextInput})

.. note::

   the widget argument can be either a class or an instance (the later
   case being convenient to pass the Widget specific initialisation
   options)

Overriding permissions
^^^^^^^^^^^^^^^^^^^^^^

The `autoform_permissions_overrides` rtag provides a way to by-pass security
checking for dark-corner case where it can't be verified properly.


.. More about inlined forms
.. Controlling the generic relation fields
"""

from six.moves import range

from logilab.mtconverter import xml_escape
from logilab.common.decorators import iclassmethod, cached
from logilab.common.registry import NoSelectableObject

from cubicweb import neg_role, uilib
from cubicweb.schema import display_name
from cubicweb.view import EntityView
from cubicweb.predicates import (
    match_kwargs, match_form_params, non_final_entity,
    specified_etype_implements)
from cubicweb.utils import json_dumps
from cubicweb.web import (stdmsgs, eid_param,
                          form as f, formwidgets as fw, formfields as ff)
from cubicweb.web.views import uicfg, forms
from cubicweb.web.views.ajaxcontroller import ajaxfunc


# inlined form handling ########################################################

class InlinedFormField(ff.Field):
    def __init__(self, view=None, **kwargs):
        kwargs.setdefault('label', None)
        # don't add eidparam=True since this field doesn't actually hold the
        # relation value (the subform does) hence should not be listed in
        # _cw_entity_fields
        super(InlinedFormField, self).__init__(name=view.rtype, role=view.role,
                                               **kwargs)
        self.view = view

    def render(self, form, renderer):
        """render this field, which is part of form, using the given form
        renderer
        """
        view = self.view
        i18nctx = 'inlined:%s.%s.%s' % (form.edited_entity.e_schema,
                                        view.rtype, view.role)
        return u'<div class="inline-%s-%s-slot">%s</div>' % (
            view.rtype, view.role,
            view.render(i18nctx=i18nctx, row=view.cw_row, col=view.cw_col))

    def form_init(self, form):
        """method called before by build_context to trigger potential field
        initialization requiring the form instance
        """
        if self.view.form:
            self.view.form.build_context(form.formvalues)

    @property
    def needs_multipart(self):
        if self.view.form:
            # take a look at inlined forms to check (recursively) if they need
            # multipart handling.
            return self.view.form.needs_multipart
        return False

    def has_been_modified(self, form):
        return False

    def process_posted(self, form):
        pass  # handled by the subform


class InlineEntityEditionFormView(f.FormViewMixIn, EntityView):
    """
    :attr peid: the parent entity's eid hosting the inline form
    :attr rtype: the relation bridging `etype` and `peid`
    :attr role: the role played by the `peid` in the relation
    :attr pform: the parent form where this inlined form is being displayed
    """
    __regid__ = 'inline-edition'
    __select__ = non_final_entity() & match_kwargs('peid', 'rtype')

    _select_attrs = ('peid', 'rtype', 'role', 'pform', 'etype')
    removejs = "removeInlinedEntity('%s', '%s', '%s')"
    form_renderer_id = 'inline'

    # make pylint happy
    peid = rtype = role = pform = etype = None

    def __init__(self, *args, **kwargs):
        for attr in self._select_attrs:
            # don't pop attributes from kwargs, so the end-up in
            # self.cw_extra_kwargs which is then passed to the edition form (see
            # the .form method)
            setattr(self, attr, kwargs.get(attr))
        super(InlineEntityEditionFormView, self).__init__(*args, **kwargs)

    def _entity(self):
        assert self.cw_row is not None, self
        return self.cw_rset.get_entity(self.cw_row, self.cw_col)

    @property
    def petype(self):
        assert isinstance(self.peid, int)
        pentity = self._cw.entity_from_eid(self.peid)
        return pentity.e_schema.type

    @property
    @cached
    def form(self):
        entity = self._entity()
        form = self._cw.vreg['forms'].select('edition', self._cw,
                                             entity=entity,
                                             formtype='inlined',
                                             form_renderer_id=self.form_renderer_id,
                                             copy_nav_params=False,
                                             mainform=False,
                                             parent_form=self.pform,
                                             **self.cw_extra_kwargs)
        if self.pform is None:
            form.restore_previous_post(form.session_key())
        # assert form.parent_form
        self.add_hiddens(form, entity)
        return form

    def cell_call(self, row, col, i18nctx, **kwargs):
        """
        :param peid: the parent entity's eid hosting the inline form
        :param rtype: the relation bridging `etype` and `peid`
        :param role: the role played by the `peid` in the relation
        """
        entity = self._entity()
        divonclick = "restoreInlinedEntity('%s', '%s', '%s')" % (
            self.peid, self.rtype, entity.eid)
        self.render_form(i18nctx, divonclick=divonclick, **kwargs)

    def _get_removejs(self):
        """
        Don't display the remove link in edition form if the
        cardinality is 1. Handled in InlineEntityCreationFormView for
        creation form.
        """
        entity = self._entity()
        rdef = entity.e_schema.rdef(self.rtype, neg_role(self.role), self.petype)
        card = rdef.role_cardinality(self.role)
        if card == '1':  # don't display remove link
            return None
        # if cardinality is 1..n (+), dont display link to remove an inlined form for the first form
        # allowing to edit the relation. To detect so:
        #
        # * if parent form (pform) is None, we're generated through an ajax call and so we know this
        #   is not the first form
        #
        # * if parent form is not None, look for previous InlinedFormField in the parent's form
        #   fields
        if card == '+' and self.pform is not None:
            # retrieve all field'views handling this relation and return None if we're the first of
            # them
            first_view = next(iter((f.view for f in self.pform.fields
                                    if isinstance(f, InlinedFormField)
                                    and f.view.rtype == self.rtype and f.view.role == self.role)))
            if self == first_view:
                return None
        return self.removejs and self.removejs % (
            self.peid, self.rtype, entity.eid)

    def render_form(self, i18nctx, **kwargs):
        """fetch and render the form"""
        entity = self._entity()
        divid = '%s-%s-%s' % (self.peid, self.rtype, entity.eid)
        title = self.form_title(entity, i18nctx)
        removejs = self._get_removejs()
        countkey = '%s_count' % self.rtype
        try:
            self._cw.data[countkey] += 1
        except KeyError:
            self._cw.data[countkey] = 1
        self.form.render(w=self.w, divid=divid, title=title, removejs=removejs,
                         i18nctx=i18nctx, counter=self._cw.data[countkey],
                         **kwargs)

    def form_title(self, entity, i18nctx):
        return self._cw.pgettext(i18nctx, entity.cw_etype)

    def add_hiddens(self, form, entity):
        """to ease overriding (see cubes.vcsfile.views.forms for instance)"""
        iid = 'rel-%s-%s-%s' % (self.peid, self.rtype, entity.eid)
        #  * str(self.rtype) in case it's a schema object
        #  * neged_role() since role is the for parent entity, we want the role
        #    of the inlined entity
        form.add_hidden(name=str(self.rtype), value=self.peid,
                        role=neg_role(self.role), eidparam=True, id=iid)

    def keep_entity(self, form, entity):
        if not entity.has_eid():
            return True
        # are we regenerating form because of a validation error?
        if form.form_previous_values:
            cdvalues = self._cw.list_form_param(eid_param(self.rtype, self.peid),
                                                form.form_previous_values)
            if unicode(entity.eid) not in cdvalues:
                return False
        return True


class InlineEntityCreationFormView(InlineEntityEditionFormView):
    """
    :attr etype: the entity type being created in the inline form
    """
    __regid__ = 'inline-creation'
    __select__ = (match_kwargs('peid', 'petype', 'rtype')
                  & specified_etype_implements('Any'))
    _select_attrs = InlineEntityEditionFormView._select_attrs + ('petype',)

    # make pylint happy
    petype = None

    @property
    def removejs(self):
        entity = self._entity()
        rdef = entity.e_schema.rdef(self.rtype, neg_role(self.role), self.petype)
        card = rdef.role_cardinality(self.role)
        # when one is adding an inline entity for a relation of a single card,
        # the 'add a new xxx' link disappears. If the user then cancel the addition,
        # we have to make this link appears back. This is done by giving add new link
        # id to removeInlineForm.
        if card == '?':
            divid = "addNew%s%s%s:%s" % (self.etype, self.rtype, self.role, self.peid)
            return "removeInlineForm('%%s', '%%s', '%s', '%%s', '%s')" % (
                self.role, divid)
        elif card in '+*':
            return "removeInlineForm('%%s', '%%s', '%s', '%%s')" % self.role
        # don't do anything for card == '1'

    @cached
    def _entity(self):
        try:
            cls = self._cw.vreg['etypes'].etype_class(self.etype)
        except Exception:
            self.w(self._cw._('no such entity type %s') % self.etype)
            return
        entity = cls(self._cw)
        entity.eid = next(self._cw.varmaker)
        return entity

    def call(self, i18nctx, **kwargs):
        self.render_form(i18nctx, **kwargs)


class InlineAddNewLinkView(InlineEntityCreationFormView):
    """
    :attr card: the cardinality of the relation according to role of `peid`
    """
    __regid__ = 'inline-addnew-link'
    __select__ = (match_kwargs('peid', 'petype', 'rtype')
                  & specified_etype_implements('Any'))

    _select_attrs = InlineEntityCreationFormView._select_attrs + ('card',)
    card = None  # make pylint happy
    form = None  # no actual form wrapped

    def call(self, i18nctx, **kwargs):
        self._cw.set_varmaker()
        divid = "addNew%s%s%s:%s" % (self.etype, self.rtype, self.role, self.peid)
        self.w(u'<div class="inlinedform" id="%s" cubicweb:limit="true">'
               % divid)
        js = "addInlineCreationForm('%s', '%s', '%s', '%s', '%s', '%s')" % (
            self.peid, self.petype, self.etype, self.rtype, self.role, i18nctx)
        if self.pform.should_hide_add_new_relation_link(self.rtype, self.card):
            js = "toggleVisibility('%s'); %s" % (divid, js)
        __ = self._cw.pgettext
        self.w(u'<a class="addEntity" id="add%s:%slink" href="javascript: %s" >+ %s.</a>'
               % (self.rtype, self.peid, js, __(i18nctx, 'add a %s' % self.etype)))
        self.w(u'</div>')


# generic relations handling ##################################################

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
        nodeid, xml_escape(json_dumps(eid)))
    return u'[<a class="handle" href="%s" id="handle%s">%s</a>]' % (
        js, nodeid, label)


def get_pending_inserts(req, eid=None):
    """shortcut to access req's pending_insert entry

    This is where are stored relations being added while editing
    an entity. This used to be stored in a temporary cookie.
    """
    pending = req.session.data.get('pending_insert', ())
    return ['%s:%s:%s' % (subj, rel, obj) for subj, rel, obj in pending
            if eid is None or eid in (subj, obj)]


def get_pending_deletes(req, eid=None):
    """shortcut to access req's pending_delete entry

    This is where are stored relations being removed while editing
    an entity. This used to be stored in a temporary cookie.
    """
    pending = req.session.data.get('pending_delete', ())
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
                yield int(subj), rtype, int(obj)


def delete_relations(req, rdefs):
    """delete relations from the repository"""
    # FIXME convert to using the syntax subject:relation:eids
    execute = req.execute
    for subj, rtype, obj in parse_relations_descr(rdefs):
        rql = 'DELETE X %s Y where X eid %%(x)s, Y eid %%(y)s' % rtype
        execute(rql, {'x': subj, 'y': obj})
    req.set_message(req._('relations deleted'))


def insert_relations(req, rdefs):
    """insert relations into the repository"""
    execute = req.execute
    for subj, rtype, obj in parse_relations_descr(rdefs):
        rql = 'SET X %s Y where X eid %%(x)s, Y eid %%(y)s' % rtype
        execute(rql, {'x': subj, 'y': obj})


# ajax edition helpers ########################################################
@ajaxfunc(output_type='xhtml', check_pageid=True)
def inline_creation_form(self, peid, petype, ttype, rtype, role, i18nctx):
    view = self._cw.vreg['views'].select('inline-creation', self._cw,
                                         etype=ttype, rtype=rtype, role=role,
                                         peid=peid, petype=petype)
    return self._call_view(view, i18nctx=i18nctx)


@ajaxfunc(output_type='json')
def validate_form(self, action, names, values):
    return self.validate_form(action, names, values)


@ajaxfunc
def cancel_edition(self, errorurl):
    """cancelling edition from javascript

    We need to clear associated req's data :
      - errorurl
      - pending insertions / deletions
    """
    self._cw.cancel_edition(errorurl)


def _add_pending(req, eidfrom, rel, eidto, kind):
    key = 'pending_%s' % kind
    pendings = req.session.data.get(key, [])
    value = (int(eidfrom), rel, int(eidto))
    if value not in pendings:
        pendings.append(value)
        req.session.data[key] = pendings


def _remove_pending(req, eidfrom, rel, eidto, kind):
    key = 'pending_%s' % kind
    pendings = req.session.data[key]
    value = (int(eidfrom), rel, int(eidto))
    if value in pendings:
        pendings.remove(value)
        req.session.data[key] = pendings


@ajaxfunc(output_type='json')
def remove_pending_insert(self, args):
    eidfrom, rel, eidto = args
    _remove_pending(self._cw, eidfrom, rel, eidto, 'insert')


@ajaxfunc(output_type='json')
def add_pending_inserts(self, tripletlist):
    for eidfrom, rel, eidto in tripletlist:
        _add_pending(self._cw, eidfrom, rel, eidto, 'insert')


@ajaxfunc(output_type='json')
def remove_pending_delete(self, args):
    eidfrom, rel, eidto = args
    _remove_pending(self._cw, eidfrom, rel, eidto, 'delete')


@ajaxfunc(output_type='json')
def add_pending_delete(self, args):
    eidfrom, rel, eidto = args
    _add_pending(self._cw, eidfrom, rel, eidto, 'delete')


class GenericRelationsWidget(fw.FieldWidget):

    def render(self, form, field, renderer):
        stream = []
        w = stream.append
        req = form._cw
        _ = req._
        eid = form.edited_entity.eid
        w(u'<table id="relatedEntities">')
        for rschema, role, related in field.relations_table(form):
            # already linked entities
            if related:
                label = rschema.display_name(req, role, context=form.edited_entity.cw_etype)
                w(u'<tr><th class="labelCol">%s</th>' % label)
                w(u'<td>')
                w(u'<ul class="list-unstyled">')
                for viewparams in related:
                    w(u'<li>%s<span id="span%s" class="%s">%s</span></li>'
                      % (viewparams[1], viewparams[0], viewparams[2], viewparams[3]))
                if not form.force_display and form.maxrelitems < len(related):
                    link = (u'<span>[<a '
                            'href="javascript: window.location.href+=\'&amp;__force_display=1\'"'
                            '>%s</a>]</span>' % _('view all'))
                    w(u'<li>%s</li>' % link)
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
        w(u'<select id="relationSelector_%s" '
          'onchange="javascript:showMatchingSelect(this.options[this.selectedIndex].value,%s);">'
          % (eid, xml_escape(json_dumps(eid))))
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
                if role == 'subject':
                    haspermkwargs = {'fromeid': entity.eid}
                else:
                    haspermkwargs = {'toeid': entity.eid}
                if rschema.has_perm(form._cw, 'delete', **haspermkwargs):
                    toggleable_rel_link_func = toggleable_relation_link
                else:
                    def toggleable_rel_link_func(x, y, z):
                        return u''
                for row in range(rset.rowcount):
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
            pendingid = 'id' + pendingid
            if int(eidfrom) == entity.eid:  # subject
                label = display_name(form._cw, rtype, 'subject',
                                     entity.cw_etype)
                reid = eidto
            else:
                label = display_name(form._cw, rtype, 'object',
                                     entity.cw_etype)
                reid = eidfrom
            jscall = "javascript: cancelPendingInsert('%s', 'tr', null, %s);" \
                     % (pendingid, entity.eid)
            rset = form._cw.eid_rset(reid)
            eview = form._cw.view('text', rset, row=0)
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
        if rschema.symmetric or role == 'subject':
            targettypes = rschema.objects(entity.e_schema)
            etypes = '/'.join(sorted(etype.display_name(self._cw) for etype in targettypes))
        else:
            targettypes = rschema.subjects(entity.e_schema)
            etypes = '/'.join(sorted(etype.display_name(self._cw) for etype in targettypes))
        etypes = uilib.cut(etypes, self._cw.property_value('navigation.short-line-size'))
        options.append('<option>%s %s</option>' % (self._cw._('select a'), etypes))
        options += self._get_select_options(entity, rschema, role)
        options += self._get_search_options(entity, rschema, role, targettypes)
        relname, role = self._cw.form.get('relation').rsplit('_', 1)
        return u"""\
<div class="%s" id="%s">
  <select id="%s"
          onchange="javascript: addPendingInsert(this.options[this.selectedIndex], %s, %s, '%s');">
    %s
  </select>
</div>
""" % (hidden and 'hidden' or '', divid, selectid,
       xml_escape(json_dumps(entity.eid)), is_cell and 'true' or 'null',
       relname, '\n'.join(options))

    def _get_select_options(self, entity, rschema, role):
        """add options to search among all entities of each possible type"""
        options = []
        pending_inserts = get_pending_inserts(self._cw, entity.eid)
        rtype = rschema.type
        form = self._cw.vreg['forms'].select('edition', self._cw, entity=entity)
        field = form.field_by_name(rschema, role, entity.e_schema)
        limit = self._cw.property_value('navigation.combobox-limit')
        # NOTE: expect 'limit' arg on choices method of relation field
        for eview, reid in field.vocabulary(form, limit=limit):
            if reid is None:
                if eview:  # skip blank value
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


# The automatic entity form ####################################################

class AutomaticEntityForm(forms.EntityFieldsForm):
    """AutomaticEntityForm is an automagic form to edit any entity. It
    is designed to be fully generated from schema but highly
    configurable through uicfg.

    Of course, as for other forms, you can also customise it by specifying
    various standard form parameters on selection, overriding, or
    adding/removing fields in selected instances.
    """
    __regid__ = 'edition'

    cwtarget = 'eformframe'
    cssclass = 'entityForm'
    copy_nav_params = True
    form_buttons = [fw.SubmitButton(),
                    fw.Button(stdmsgs.BUTTON_APPLY, cwaction='apply'),
                    fw.Button(stdmsgs.BUTTON_CANCEL,
                              {'class': fw.Button.css_class + ' cwjs-edition-cancel'})]
    # for attributes selection when searching in uicfg.autoform_section
    formtype = 'main'
    # set this to a list of [(relation, role)] if you want to explictily tell
    # which relations should be edited
    display_fields = None
    # action on the form tag
    _default_form_action_path = 'validateform'

    @iclassmethod
    def field_by_name(cls_or_self, name, role=None, eschema=None):
        """return field with the given name and role. If field is not explicitly
        defined for the form but `eclass` is specified, guess_field will be
        called.
        """
        try:
            return super(AutomaticEntityForm, cls_or_self).field_by_name(name, role, eschema)
        except f.FieldNotFound:
            if name == '_cw_generic_field' and not isinstance(cls_or_self, type):
                return cls_or_self._generic_relations_field()
            raise

    # base automatic entity form methods #######################################

    def __init__(self, *args, **kwargs):
        super(AutomaticEntityForm, self).__init__(*args, **kwargs)
        self.uicfg_afs = self._cw.vreg['uicfg'].select(
            'autoform_section', self._cw, entity=self.edited_entity)
        entity = self.edited_entity
        if entity.has_eid():
            entity.complete()
        for rtype, role in self.editable_attributes():
            try:
                self.field_by_name(str(rtype), role)
                continue  # explicitly specified
            except f.FieldNotFound:
                # has to be guessed
                try:
                    field = self.field_by_name(str(rtype), role,
                                               eschema=entity.e_schema)
                    self.fields.append(field)
                except f.FieldNotFound:
                    # meta attribute such as <attr>_format
                    continue
        if self.fieldsets_in_order:
            fsio = list(self.fieldsets_in_order)
        else:
            fsio = [None]
        self.fieldsets_in_order = fsio
        # add fields for relation whose target should have an inline form
        for formview in self.inlined_form_views():
            field = self._inlined_form_view_field(formview)
            self.fields.append(field)
            if field.fieldset not in fsio:
                fsio.append(field.fieldset)
        if self.formtype == 'main':
            # add the generic relation field if necessary
            if entity.has_eid() and (
                self.display_fields is None or
                '_cw_generic_field' in self.display_fields):
                try:
                    field = self.field_by_name('_cw_generic_field')
                except f.FieldNotFound:
                    # no editable relation
                    pass
                else:
                    self.fields.append(field)
                    if field.fieldset not in fsio:
                        fsio.append(field.fieldset)
        self.maxrelitems = self._cw.property_value('navigation.related-limit')
        self.force_display = bool(self._cw.form.get('__force_display'))
        fnum = len(self.fields)
        self.fields.sort(key=lambda f: f.order is None and fnum or f.order)

    @property
    def related_limit(self):
        if self.force_display:
            return None
        return self.maxrelitems + 1

    # autoform specific fields #################################################

    def _generic_relations_field(self):
        srels_by_cat = self.editable_relations()
        if not srels_by_cat:
            raise f.FieldNotFound('_cw_generic_field')
        fieldset = 'This %s:' % self.edited_entity.e_schema
        return GenericRelationsField(self.editable_relations(),
                                     fieldset=fieldset, label=None)

    def _inlined_form_view_field(self, view):
        # XXX allow more customization
        kwargs = self.uicfg_affk.etype_get(self.edited_entity.e_schema,
                                           view.rtype, view.role, view.etype)
        if kwargs is None:
            kwargs = {}
        return InlinedFormField(view=view, **kwargs)

    # methods mapping edited entity relations to fields in the form ############

    def _relations_by_section(self, section, permission='add', strict=False):
        """return a list of (relation schema, target schemas, role) matching
        given category(ies) and permission
        """
        return self.uicfg_afs.relations_by_section(
            self.edited_entity, self.formtype, section, permission, strict)

    def editable_attributes(self, strict=False):
        """return a list of (relation schema, role) to edit for the entity"""
        if self.display_fields is not None:
            schema = self._cw.vreg.schema
            for rtype, role in self.display_fields:
                yield (schema[rtype], role)
        if self.edited_entity.has_eid() and not self.edited_entity.cw_has_perm('update'):
            return
        action = 'update' if self.edited_entity.has_eid() else 'add'
        for rtype, _, role in self._relations_by_section('attributes', action, strict):
            yield (rtype, role)

    def editable_relations(self):
        """return a sorted list of (relation's label, relation'schema, role) for
        relations in the 'relations' section
        """
        return sorted(self.iter_editable_relations())

    def iter_editable_relations(self):
        for rschema, _, role in self._relations_by_section('relations', strict=True):
            yield (rschema.display_name(self.edited_entity._cw, role,
                                        self.edited_entity.cw_etype),
                   rschema, role)

    def inlined_relations(self):
        """return a list of (relation schema, target schemas, role) matching
        given category(ies) and permission
        """
        return self._relations_by_section('inlined')

    # inlined forms control ####################################################

    def inlined_form_views(self):
        """Yield inlined form views (hosting the inlined form object)
        """
        entity = self.edited_entity
        for rschema, ttypes, role in self.inlined_relations():
            # show inline forms only if there's one possible target type
            # for rschema
            if len(ttypes) != 1:
                self.warning('entity related by the %s relation should have '
                             'inlined form but there is multiple target types, '
                             'dunno what to do', rschema)
                continue
            tschema = ttypes[0]
            ttype = tschema.type
            existing = bool(entity.related(rschema, role)) if entity.has_eid() else False
            for formview in self.inline_edition_form_view(rschema, ttype, role):
                yield formview
                existing = True
            card = rschema.role_rdef(entity.e_schema, ttype, role).role_cardinality(role)
            if self.should_display_inline_creation_form(rschema, existing, card):
                for formview in self.inline_creation_form_view(rschema, ttype, role):
                    yield formview
                    existing = True
            # we can create more than one related entity, we thus display a link
            # to add new related entities
            if self.must_display_add_new_relation_link(rschema, role, tschema,
                                                       ttype, existing, card):
                addnewlink = self._cw.vreg['views'].select(
                    'inline-addnew-link', self._cw,
                    etype=ttype, rtype=rschema, role=role, card=card,
                    peid=self.edited_entity.eid,
                    petype=self.edited_entity.e_schema, pform=self)
                yield addnewlink

    def should_display_inline_creation_form(self, rschema, existing, card):
        """return true if a creation form should be inlined

        by default true if there is no related entity and we need at least one
        """
        return not existing and card in '1+'

    def should_display_add_new_relation_link(self, rschema, existing, card):
        """return true if we should add a link to add a new creation form
        (through ajax call)

        by default true if there is no related entity or if the relation has
        multiple cardinality
        """
        return not existing or card in '+*'

    def must_display_add_new_relation_link(self, rschema, role, tschema,
                                           ttype, existing, card):
        """return true if we must add a link to add a new creation form
        (through ajax call)

        by default true if there is no related entity or if the relation has
        multiple cardinality and it is permitted to add the inlined object and
        relation.
        """
        return (self.should_display_add_new_relation_link(
            rschema, existing, card) and
                self.check_inlined_rdef_permissions(
                    rschema, role, tschema, ttype))

    def check_inlined_rdef_permissions(self, rschema, role, tschema, ttype):
        """return true if permissions are granted on the inlined object and
        relation"""
        if not tschema.has_perm(self._cw, 'add'):
            return False
        entity = self.edited_entity
        rdef = entity.e_schema.rdef(rschema, role, ttype)
        if entity.has_eid():
            if role == 'subject':
                rdefkwargs = {'fromeid': entity.eid}
            else:
                rdefkwargs = {'toeid': entity.eid}
            return rdef.has_perm(self._cw, 'add', **rdefkwargs)
        return rdef.may_have_permission('add', self._cw)

    def should_hide_add_new_relation_link(self, rschema, card):
        """return true if once an inlined creation form is added, the 'add new'
        link should be hidden

        by default true if the relation has single cardinality
        """
        return card in '1?'

    def inline_edition_form_view(self, rschema, ttype, role):
        """yield inline form views for already related entities through the
        given relation
        """
        entity = self.edited_entity
        related = entity.has_eid() and entity.related(rschema, role)
        if related:
            vvreg = self._cw.vreg['views']
            # display inline-edition view for all existing related entities
            for i, relentity in enumerate(related.entities()):
                if relentity.cw_has_perm('update'):
                    yield vvreg.select('inline-edition', self._cw,
                                       rset=related, row=i, col=0,
                                       etype=ttype, rtype=rschema, role=role,
                                       peid=entity.eid, pform=self)

    def inline_creation_form_view(self, rschema, ttype, role):
        """yield inline form views to a newly related (hence created) entity
        through the given relation
        """
        try:
            yield self._cw.vreg['views'].select('inline-creation', self._cw,
                                                etype=ttype, rtype=rschema, role=role,
                                                peid=self.edited_entity.eid,
                                                petype=self.edited_entity.e_schema,
                                                pform=self)
        except NoSelectableObject:
            # may be raised if user doesn't have the permission to add ttype entities (no checked
            # earlier) or if there is some custom selector on the view
            pass


# default form ui configuration ##############################################

_AFS = uicfg.autoform_section
# use primary and not generated for eid since it has to be an hidden
_AFS.tag_attribute(('*', 'eid'), 'main', 'hidden')
_AFS.tag_attribute(('*', 'eid'), 'muledit', 'attributes')
_AFS.tag_attribute(('*', 'description'), 'main', 'attributes')
_AFS.tag_attribute(('*', 'has_text'), 'main', 'hidden')
_AFS.tag_subject_of(('*', 'in_state', '*'), 'main', 'hidden')
for rtype in ('creation_date', 'modification_date', 'cwuri',
              'owned_by', 'created_by', 'cw_source'):
    _AFS.tag_subject_of(('*', rtype, '*'), 'main', 'metadata')

_AFS.tag_subject_of(('*', 'by_transition', '*'), 'main', 'attributes')
_AFS.tag_subject_of(('*', 'by_transition', '*'), 'muledit', 'attributes')
_AFS.tag_object_of(('*', 'by_transition', '*'), 'main', 'hidden')
_AFS.tag_object_of(('*', 'from_state', '*'), 'main', 'hidden')
_AFS.tag_object_of(('*', 'to_state', '*'), 'main', 'hidden')
_AFS.tag_subject_of(('*', 'wf_info_for', '*'), 'main', 'attributes')
_AFS.tag_subject_of(('*', 'wf_info_for', '*'), 'muledit', 'attributes')
_AFS.tag_object_of(('*', 'wf_info_for', '*'), 'main', 'hidden')
_AFS.tag_attribute(('CWEType', 'final'), 'main', 'hidden')
_AFS.tag_attribute(('CWRType', 'final'), 'main', 'hidden')
_AFS.tag_attribute(('CWUser', 'firstname'), 'main', 'attributes')
_AFS.tag_attribute(('CWUser', 'surname'), 'main', 'attributes')
_AFS.tag_attribute(('CWUser', 'last_login_time'), 'main', 'metadata')
_AFS.tag_subject_of(('CWUser', 'in_group', '*'), 'main', 'attributes')
_AFS.tag_subject_of(('CWUser', 'in_group', '*'), 'muledit', 'attributes')
_AFS.tag_subject_of(('*', 'primary_email', '*'), 'main', 'relations')
_AFS.tag_subject_of(('*', 'use_email', '*'), 'main', 'inlined')
_AFS.tag_subject_of(('CWRelation', 'relation_type', '*'), 'main', 'inlined')
_AFS.tag_subject_of(('CWRelation', 'from_entity', '*'), 'main', 'inlined')
_AFS.tag_subject_of(('CWRelation', 'to_entity', '*'), 'main', 'inlined')

_AFFK = uicfg.autoform_field_kwargs
_AFFK.tag_attribute(('RQLExpression', 'expression'),
                    {'widget': fw.TextInput})
_AFFK.tag_subject_of(('TrInfo', 'wf_info_for', '*'),
                     {'widget': fw.HiddenInput})


def registration_callback(vreg):
    global etype_relation_field

    def etype_relation_field(etype, rtype, role='subject'):
        try:
            eschema = vreg.schema.eschema(etype)
            return AutomaticEntityForm.field_by_name(rtype, role, eschema)
        except (KeyError, f.FieldNotFound):
            # catch KeyError raised when etype/rtype not found in schema
            AutomaticEntityForm.error('field for %s %s may not be found in schema' % (rtype, role))
            return None

    vreg.register_all(globals().values(), __name__)
