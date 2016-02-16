# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""The edit controller, automatically handling entity form submitting"""

__docformat__ = "restructuredtext en"

from warnings import warn
from collections import defaultdict

from datetime import datetime

from logilab.common.deprecation import deprecated
from logilab.common.graph import ordered_nodes

from rql.utils import rqlvar_maker

from cubicweb import Binary, ValidationError, UnknownEid
from cubicweb.view import EntityAdapter
from cubicweb.predicates import is_instance
from cubicweb.web import (INTERNAL_FIELD_VALUE, RequestError, NothingToEdit,
                          ProcessFormError)
from cubicweb.web.views import basecontrollers, autoform


class IEditControlAdapter(EntityAdapter):
    __regid__ = 'IEditControl'
    __select__ = is_instance('Any')

    def __init__(self, _cw, **kwargs):
        if self.__class__ is not IEditControlAdapter:
            warn('[3.14] IEditControlAdapter is deprecated, override EditController'
                 ' using match_edited_type or match_form_id selectors for example.',
                 DeprecationWarning)
        super(IEditControlAdapter, self).__init__(_cw, **kwargs)

    def after_deletion_path(self):
        """return (path, parameters) which should be used as redirect
        information when this entity is being deleted
        """
        parent = self.entity.cw_adapt_to('IBreadCrumbs').parent_entity()
        if parent is not None:
            return parent.rest_path(), {}
        return str(self.entity.e_schema).lower(), {}

    def pre_web_edit(self):
        """callback called by the web editcontroller when an entity will be
        created/modified, to let a chance to do some entity specific stuff.

        Do nothing by default.
        """
        pass


def valerror_eid(eid):
    try:
        return int(eid)
    except (ValueError, TypeError):
        return eid

class RqlQuery(object):
    def __init__(self):
        self.edited = []
        self.restrictions = []
        self.kwargs = {}
        self.canceled = False

    def __repr__(self):
        return ('Query <edited=%r restrictions=%r kwargs=%r>' % (
            self.edited, self.restrictions, self.kwargs))

    def insert_query(self, etype):
        assert not self.canceled
        if self.edited:
            rql = 'INSERT %s X: %s' % (etype, ','.join(self.edited))
        else:
            rql = 'INSERT %s X' % etype
        if self.restrictions:
            rql += ' WHERE %s' % ','.join(self.restrictions)
        return rql

    def update_query(self, eid):
        assert not self.canceled
        varmaker = rqlvar_maker()
        var = varmaker.next()
        while var in self.kwargs:
            var = varmaker.next()
        rql = 'SET %s WHERE X eid %%(%s)s' % (','.join(self.edited), var)
        if self.restrictions:
            rql += ', %s' % ','.join(self.restrictions)
        self.kwargs[var] = eid
        return rql

    def set_attribute(self, attr, value):
        self.kwargs[attr] = value
        self.edited.append('X %s %%(%s)s' % (attr, attr))

    def set_inlined(self, relation, value):
        self.kwargs[relation] = value
        self.edited.append('X %s %s' % (relation, relation.upper()))
        self.restrictions.append('%s eid %%(%s)s' % (relation.upper(), relation))


class EditController(basecontrollers.ViewController):
    __regid__ = 'edit'

    def publish(self, rset=None):
        """edit / create / copy / delete entity / relations"""
        for key in self._cw.form:
            # There should be 0 or 1 action
            if key.startswith('__action_'):
                cbname = key[1:]
                try:
                    callback = getattr(self, cbname)
                except AttributeError:
                    raise RequestError(self._cw._('invalid action %r' % key))
                else:
                    return callback()
        self._default_publish()
        self.reset()

    def _ordered_formparams(self):
        """ Return form parameters dictionaries for each edited entity.

        We ensure that entities can be created in this order accounting for
        mandatory inlined relations.
        """
        req = self._cw
        graph = {}
        get_rschema = self._cw.vreg.schema.rschema
        # minparams = 2, because at least __type and eid are needed
        values_by_eid = dict((eid, req.extract_entity_params(eid, minparams=2))
                             for eid in req.edited_eids())
        # iterate over all the edited entities
        for eid, values in values_by_eid.iteritems():
            # add eid to the dependency graph
            graph.setdefault(eid, set())
            # search entity's edited fields for mandatory inlined relation
            for param in values['_cw_entity_fields'].split(','):
                try:
                    rtype, role = param.split('-')
                except ValueError:
                    # e.g. param='__type'
                    continue
                rschema = get_rschema(rtype)
                if rschema.inlined:
                    for target in rschema.targets(values['__type'], role):
                        rdef = rschema.role_rdef(values['__type'], target, role)
                        # if cardinality is 1 and if the target entity is being
                        # simultaneously edited, the current entity must be
                        # created before the target one
                        if rdef.cardinality[0 if role == 'subject' else 1] == '1':
                            # use .get since param may be unspecified (though it will usually lead
                            # to a validation error later)
                            target_eid = values.get(param)
                            if target_eid in values_by_eid:
                                # add dependency from the target entity to the
                                # current one
                                if role == 'object':
                                    graph.setdefault(target_eid, set()).add(eid)
                                else:
                                    graph.setdefault(eid, set()).add(target_eid)
                                break
        for eid in reversed(ordered_nodes(graph)):
            yield values_by_eid[eid]

    def _default_publish(self):
        req = self._cw
        self.errors = []
        self.relations_rql = []
        form = req.form
        # so we're able to know the main entity from the repository side
        if '__maineid' in form:
            req.transaction_data['__maineid'] = form['__maineid']
        # no specific action, generic edition
        self._to_create = req.data['eidmap'] = {}
        # those two data variables are used to handle relation from/to entities
        # which doesn't exist at time where the entity is edited and that
        # deserves special treatment
        req.data['pending_inlined'] = defaultdict(set)
        req.data['pending_others'] = set()
        req.data['pending_composite_delete'] = set()
        try:
            for formparams in self._ordered_formparams():
                eid = self.edit_entity(formparams)
        except (RequestError, NothingToEdit) as ex:
            if '__linkto' in req.form and 'eid' in req.form:
                self.execute_linkto()
            elif not ('__delete' in req.form or '__insert' in req.form):
                raise ValidationError(None, {None: unicode(ex)})
        # all pending inlined relations to newly created entities have been
        # treated now (pop to ensure there are no attempt to add new ones)
        pending_inlined = req.data.pop('pending_inlined')
        assert not pending_inlined, pending_inlined
        # handle all other remaining relations now
        for form_, field in req.data.pop('pending_others'):
            self.handle_formfield(form_, field)
        # then execute rql to set all relations
        for querydef in self.relations_rql:
            self._cw.execute(*querydef)
        # delete pending composite
        for entity in req.data['pending_composite_delete']:
            entity.cw_delete()
        # XXX this processes *all* pending operations of *all* entities
        if '__delete' in req.form:
            todelete = req.list_form_param('__delete', req.form, pop=True)
            if todelete:
                autoform.delete_relations(self._cw, todelete)
        self._cw.remove_pending_operations()
        if self.errors:
            errors = dict((f.name, unicode(ex)) for f, ex in self.errors)
            raise ValidationError(valerror_eid(form.get('__maineid')), errors)

    def _insert_entity(self, etype, eid, rqlquery):
        rql = rqlquery.insert_query(etype)
        try:
            entity = self._cw.execute(rql, rqlquery.kwargs).get_entity(0, 0)
            neweid = entity.eid
        except ValidationError as ex:
            self._to_create[eid] = ex.entity
            if self._cw.ajax_request: # XXX (syt) why?
                ex.entity = eid
            raise
        self._to_create[eid] = neweid
        return neweid

    def _update_entity(self, eid, rqlquery):
        self._cw.execute(rqlquery.update_query(eid), rqlquery.kwargs)

    def edit_entity(self, formparams, multiple=False):
        """edit / create / copy an entity and return its eid"""
        req = self._cw
        etype = formparams['__type']
        entity = req.vreg['etypes'].etype_class(etype)(req)
        entity.eid = valerror_eid(formparams['eid'])
        is_main_entity = req.form.get('__maineid') == formparams['eid']
        # let a chance to do some entity specific stuff
        entity.cw_adapt_to('IEditControl').pre_web_edit()
        # create a rql query from parameters
        rqlquery = RqlQuery()
        # process inlined relations at the same time as attributes
        # this will generate less rql queries and might be useful in
        # a few dark corners
        if is_main_entity:
            formid = req.form.get('__form_id', 'edition')
        else:
            # XXX inlined forms formid should be saved in a different formparams entry
            # inbetween, use cubicweb standard formid for inlined forms
            formid = 'edition'
        form = req.vreg['forms'].select(formid, req, entity=entity)
        eid = form.actual_eid(entity.eid)
        editedfields = formparams['_cw_entity_fields']
        form.formvalues = {} # init fields value cache
        for field in form.iter_modified_fields(editedfields, entity):
            self.handle_formfield(form, field, rqlquery)
        # if there are some inlined field which were waiting for this entity's
        # creation, add relevant data to the rqlquery
        for form_, field in req.data['pending_inlined'].pop(entity.eid, ()):
            rqlquery.set_inlined(field.name, form_.edited_entity.eid)
        if not rqlquery.canceled:
            if self.errors:
                errors = dict((f.role_name(), unicode(ex)) for f, ex in self.errors)
                raise ValidationError(valerror_eid(entity.eid), errors)
            if eid is None: # creation or copy
                entity.eid = eid = self._insert_entity(etype, formparams['eid'], rqlquery)
            elif rqlquery.edited: # edition of an existant entity
                self.check_concurrent_edition(formparams, eid)
                self._update_entity(eid, rqlquery)
        else:
            self.errors = []
        if is_main_entity:
            self.notify_edited(entity)
        if '__delete' in formparams:
            # XXX deprecate?
            todelete = req.list_form_param('__delete', formparams, pop=True)
            autoform.delete_relations(req, todelete)
        if '__cloned_eid' in formparams:
            entity.copy_relations(int(formparams['__cloned_eid']))
        if is_main_entity: # only execute linkto for the main entity
            self.execute_linkto(entity.eid)
        return eid

    def handle_formfield(self, form, field, rqlquery=None):
        entity = form.edited_entity
        eschema = entity.e_schema
        try:
            for field, value in field.process_posted(form):
                if not (
                    (field.role == 'subject' and field.name in eschema.subjrels)
                    or
                    (field.role == 'object' and field.name in eschema.objrels)):
                    continue

                rschema = self._cw.vreg.schema.rschema(field.name)
                if rschema.final:
                    rqlquery.set_attribute(field.name, value)
                    continue

                if entity.has_eid():
                    origvalues = set(data[0] for data in entity.related(field.name, field.role).rows)
                else:
                    origvalues = set()
                if value is None or value == origvalues:
                    continue # not edited / not modified / to do later

                unlinked_eids = origvalues - value

                if unlinked_eids:
                    # Special handling of composite relation removal
                    self.handle_composite_removal(
                        form, field, unlinked_eids, value, rqlquery)

                if rschema.inlined and rqlquery is not None and field.role == 'subject':
                    self.handle_inlined_relation(form, field, value, origvalues, rqlquery)
                elif form.edited_entity.has_eid():
                    self.handle_relation(form, field, value, origvalues)
                else:
                    form._cw.data['pending_others'].add( (form, field) )

        except ProcessFormError as exc:
            self.errors.append((field, exc))

    def handle_composite_removal(self, form, field,
                                 removed_values, new_values, rqlquery):
        """
        In EditController-handled forms, when the user removes a composite
        relation, it triggers the removal of the related entity in the
        composite. This is where this happens.

        See for instance test_subject_subentity_removal in
        web/test/unittest_application.py.
        """
        rschema = self._cw.vreg.schema.rschema(field.name)
        new_value_etypes = set()
        # the user could have included nonexisting eids in the POST; don't crash.
        for eid in new_values:
            try:
                new_value_etypes.add(self._cw.entity_from_eid(eid).cw_etype)
            except UnknownEid:
                continue
        for unlinked_eid in removed_values:
            unlinked_entity = self._cw.entity_from_eid(unlinked_eid)
            rdef = rschema.role_rdef(form.edited_entity.cw_etype,
                                     unlinked_entity.cw_etype,
                                     field.role)
            if rdef.composite is not None:
                if rdef.composite == field.role:
                    to_be_removed = unlinked_entity
                else:
                    if unlinked_entity.cw_etype in new_value_etypes:
                        # This is a same-rdef re-parenting: do not remove the entity
                        continue
                    to_be_removed = form.edited_entity
                    self.info('Edition of %s is cancelled (deletion requested)',
                              to_be_removed)
                    rqlquery.canceled = True
                self.info('Scheduling removal of %s as composite relation '
                          '%s was removed', to_be_removed, rdef)
                form._cw.data['pending_composite_delete'].add(to_be_removed)

    def handle_inlined_relation(self, form, field, values, origvalues, rqlquery):
        """handle edition for the (rschema, x) relation of the given entity
        """
        if values:
            rqlquery.set_inlined(field.name, iter(values).next())
        elif form.edited_entity.has_eid():
            self.handle_relation(form, field, values, origvalues)

    def handle_relation(self, form, field, values, origvalues):
        """handle edition for the (rschema, x) relation of the given entity
        """
        etype = form.edited_entity.e_schema
        rschema = self._cw.vreg.schema.rschema(field.name)
        if field.role == 'subject':
            desttype = rschema.objects(etype)[0]
            card = rschema.rdef(etype, desttype).cardinality[0]
            subjvar, objvar = 'X', 'Y'
        else:
            desttype = rschema.subjects(etype)[0]
            card = rschema.rdef(desttype, etype).cardinality[1]
            subjvar, objvar = 'Y', 'X'
        eid = form.edited_entity.eid
        if field.role == 'object' or not rschema.inlined or not values:
            # this is not an inlined relation or no values specified,
            # explicty remove relations
            rql = 'DELETE %s %s %s WHERE X eid %%(x)s, Y eid %%(y)s' % (
                subjvar, rschema, objvar)
            for reid in origvalues.difference(values):
                self.relations_rql.append((rql, {'x': eid, 'y': reid}))
        seteids = values.difference(origvalues)
        if seteids:
            rql = 'SET %s %s %s WHERE X eid %%(x)s, Y eid %%(y)s' % (
                subjvar, rschema, objvar)
            for reid in seteids:
                self.relations_rql.append((rql, {'x': eid, 'y': reid}))

    def delete_entities(self, eidtypes):
        """delete entities from the repository"""
        redirect_info = set()
        eidtypes = tuple(eidtypes)
        for eid, etype in eidtypes:
            entity = self._cw.entity_from_eid(eid, etype)
            path, params = entity.cw_adapt_to('IEditControl').after_deletion_path()
            redirect_info.add( (path, tuple(params.iteritems())) )
            entity.cw_delete()
        if len(redirect_info) > 1:
            # In the face of ambiguity, refuse the temptation to guess.
            self._after_deletion_path = 'view', ()
        else:
            self._after_deletion_path = iter(redirect_info).next()
        if len(eidtypes) > 1:
            self._cw.set_message(self._cw._('entities deleted'))
        else:
            self._cw.set_message(self._cw._('entity deleted'))


    def check_concurrent_edition(self, formparams, eid):
        req = self._cw
        try:
            form_ts = datetime.fromtimestamp(float(formparams['__form_generation_time']))
        except KeyError:
            # Backward and tests compatibility : if no timestamp consider edition OK
            return
        if req.execute("Any X WHERE X modification_date > %(fts)s, X eid %(eid)s",
                       {'eid': eid, 'fts': form_ts}):
            # We only mark the message for translation but the actual
            # translation will be handled by the Validation mechanism...
            msg = _("Entity %(eid)s has changed since you started to edit it."
                    " Reload the page and reapply your changes.")
            # ... this is why we pass the formats' dict as a third argument.
            raise ValidationError(eid, {None: msg}, {'eid' : eid})

    def _action_apply(self):
        self._default_publish()
        self.reset()

    def _action_cancel(self):
        errorurl = self._cw.form.get('__errorurl')
        if errorurl:
            self._cw.cancel_edition(errorurl)
        self._cw.set_message(self._cw._('edit canceled'))
        return self.reset()

    def _action_delete(self):
        self.delete_entities(self._cw.edited_eids(withtype=True))
        return self.reset()
