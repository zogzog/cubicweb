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
"""
The :mod:`cubicweb.web.facet` module contains a set of abstract classes to use
as bases to build your own facets

All facet classes inherits from the :class:`AbstractFacet` class, though you'll
usually find some more handy class that do what you want.

Let's see available classes.

Classes you'll want to use
--------------------------
.. autoclass:: cubicweb.web.facet.RelationFacet
.. autoclass:: cubicweb.web.facet.RelationAttributeFacet
.. autoclass:: cubicweb.web.facet.HasRelationFacet
.. autoclass:: cubicweb.web.facet.AttributeFacet
.. autoclass:: cubicweb.web.facet.RangeFacet
.. autoclass:: cubicweb.web.facet.DateRangeFacet

Classes for facets implementor
------------------------------
Unless you didn't find the class that does the job you want above, you may want
to skip those classes...

.. autoclass:: cubicweb.web.facet.AbstractFacet
.. autoclass:: cubicweb.web.facet.VocabularyFacet

.. comment: XXX widgets
"""

__docformat__ = "restructuredtext en"
_ = unicode

from copy import deepcopy
from datetime import date, datetime, timedelta

from logilab.mtconverter import xml_escape
from logilab.common.graph import has_path
from logilab.common.decorators import cached
from logilab.common.date import datetime2ticks
from logilab.common.compat import all

from rql import parse, nodes, utils

from cubicweb import Unauthorized, typed_eid
from cubicweb.schema import display_name
from cubicweb.utils import make_uid
from cubicweb.selectors import match_context_prop, partial_relation_possible
from cubicweb.appobject import AppObject
from cubicweb.web.htmlwidgets import HTMLWidget


def rtype_facet_title(facet):
    ptypes = facet.cw_rset.column_types(0)
    if len(ptypes) == 1:
        return display_name(facet._cw, facet.rtype, form=facet.role,
                            context=iter(ptypes).next())
    return display_name(facet._cw, facet.rtype, form=facet.role)

## rqlst manipulation functions used by facets ################################

def prepare_facets_rqlst(rqlst, args=None):
    """prepare a syntax tree to generate facet filters

    * remove ORDERBY clause
    * cleanup selection (remove everything)
    * undefine unnecessary variables
    * set DISTINCT
    * unset LIMIT/OFFSET
    """
    if len(rqlst.children) > 1:
        raise NotImplementedError('FIXME: union not yet supported')
    select = rqlst.children[0]
    mainvar = filtered_variable(select)
    select.set_limit(None)
    select.set_offset(None)
    baserql = select.as_string(kwargs=args)
    # cleanup sort terms
    select.remove_sort_terms()
    # selection: only vocabulary entity
    for term in select.selection[:]:
        select.remove_selected(term)
    # remove unbound variables which only have some type restriction
    for dvar in select.defined_vars.values():
        if not (dvar is mainvar or dvar.stinfo['relations']):
            select.undefine_variable(dvar)
    # global tree config: DISTINCT, LIMIT, OFFSET
    select.set_distinct(True)
    return mainvar, baserql

def filtered_variable(rqlst):
    vref = rqlst.selection[0].iget_nodes(nodes.VariableRef).next()
    return vref.variable


def get_facet(req, facetid, rqlst, mainvar):
    return req.vreg['facets'].object_by_id(facetid, req, rqlst=rqlst,
                                           filtered_variable=mainvar)


def filter_hiddens(w, **kwargs):
    for key, val in kwargs.items():
        w(u'<input type="hidden" name="%s" value="%s" />' % (
            key, xml_escape(val)))


def _may_be_removed(rel, schema, mainvar):
    """if the given relation may be removed from the tree, return the variable
    on the other side of `mainvar`, else return None
    Conditions:
    * the relation is an attribute selection of the main variable
    * the relation is optional relation linked to the main variable
    * the relation is a mandatory relation linked to the main variable
      without any restriction on the other variable
    """
    lhs, rhs = rel.get_variable_parts()
    rschema = schema.rschema(rel.r_type)
    if lhs.variable is mainvar:
        try:
            ovar = rhs.variable
        except AttributeError:
            # constant restriction
            # XXX: X title LOWER(T) if it makes sense?
            return None
        if rschema.final:
            if len(ovar.stinfo['relations']) == 1:
                # attribute selection
                return ovar
            return None
        opt = 'right'
        cardidx = 0
    elif getattr(rhs, 'variable', None) is mainvar:
        ovar = lhs.variable
        opt = 'left'
        cardidx = 1
    else:
        # not directly linked to the main variable
        return None
    if rel.optional in (opt, 'both'):
        # optional relation
        return ovar
    if all(rdef.cardinality[cardidx] in '1+'
           for rdef in rschema.rdefs.values()):
        # mandatory relation without any restriction on the other variable
        for orel in ovar.stinfo['relations']:
            if rel is orel:
                continue
            if _may_be_removed(orel, schema, ovar) is None:
                return None
        return ovar
    return None

def _make_relation(rqlst, mainvar, rtype, role):
    newvar = rqlst.make_variable()
    if role == 'object':
        rel = nodes.make_relation(newvar, rtype, (mainvar,), nodes.VariableRef)
    else:
        rel = nodes.make_relation(mainvar, rtype, (newvar,), nodes.VariableRef)
    return newvar, rel

def _add_rtype_relation(rqlst, mainvar, rtype, role):
    """add a relation relying `mainvar` to entities linked by the `rtype`
    relation (where `mainvar` has `role`)

    return the inserted variable for linked entities.
    """
    newvar, newrel = _make_relation(rqlst, mainvar, rtype, role)
    rqlst.add_restriction(newrel)
    return newvar, newrel

def _add_eid_restr(rel, restrvar, value):
    rrel = nodes.make_constant_restriction(restrvar, 'eid', value, 'Int')
    rel.parent.replace(rel, nodes.And(rel, rrel))

def _prepare_vocabulary_rqlst(rqlst, mainvar, rtype, role,
                              select_target_entity=True):
    """prepare a syntax tree to generate a filter vocabulary rql using the given
    relation:
    * create a variable to filter on this relation
    * add the relation
    * add the new variable to GROUPBY clause if necessary
    * add the new variable to the selection
    """
    newvar = _add_rtype_relation(rqlst, mainvar, rtype, role)[0]
    if select_target_entity:
        if rqlst.groupby:
            rqlst.add_group_var(newvar)
        rqlst.add_selected(newvar)
    # add is restriction if necessary
    if mainvar.stinfo['typerel'] is None:
        etypes = frozenset(sol[mainvar.name] for sol in rqlst.solutions)
        rqlst.add_type_restriction(mainvar, etypes)
    return newvar

def _remove_relation(rqlst, rel, var):
    """remove a constraint relation from the syntax tree"""
    # remove the relation
    rqlst.remove_node(rel)
    # remove relations where the filtered variable appears on the
    # lhs and rhs is a constant restriction
    extra = []
    for vrel in var.stinfo['relations']:
        if vrel is rel:
            continue
        if vrel.children[0].variable is var:
            if not vrel.children[1].get_nodes(nodes.Constant):
                extra.append(vrel)
            rqlst.remove_node(vrel)
    return extra

def _set_orderby(rqlst, newvar, sortasc, sortfuncname):
    if sortfuncname is None:
        rqlst.add_sort_var(newvar, sortasc)
    else:
        vref = nodes.variable_ref(newvar)
        vref.register_reference()
        sortfunc = nodes.Function(sortfuncname)
        sortfunc.append(vref)
        term = nodes.SortTerm(sortfunc, sortasc)
        rqlst.add_sort_term(term)

def insert_attr_select_relation(rqlst, mainvar, rtype, role, attrname,
                                sortfuncname=None, sortasc=True,
                                select_target_entity=True):
    """modify a syntax tree to :
    * link a new variable to `mainvar` through `rtype` (where mainvar has `role`)
    * retrieve only the newly inserted variable and its `attrname`

    Sorting:
    * on `attrname` ascendant (`sortasc`=True) or descendant (`sortasc`=False)
    * on `sortfuncname`(`attrname`) if `sortfuncname` is specified
    * no sort if `sortasc` is None
    """
    _cleanup_rqlst(rqlst, mainvar)
    var = _prepare_vocabulary_rqlst(rqlst, mainvar, rtype, role,
                                    select_target_entity)
    attrvar = rqlst.make_variable()
    rqlst.add_relation(var, attrname, attrvar)
    # if query is grouped, we have to add the attribute variable
    if rqlst.groupby:
        if not attrvar in rqlst.groupby:
            rqlst.add_group_var(attrvar)
    if sortasc is not None:
        _set_orderby(rqlst, attrvar, sortasc, sortfuncname)
    # add attribute variable to selection
    rqlst.add_selected(attrvar)
    return var

def _cleanup_rqlst(rqlst, mainvar):
    """cleanup tree from unnecessary restriction:
    * attribute selection
    * optional relations linked to the main variable
    * mandatory relations linked to the main variable
    """
    if rqlst.where is None:
        return
    schema = rqlst.root.schema
    toremove = set()
    vargraph = deepcopy(rqlst.vargraph) # graph representing links between variable
    for rel in rqlst.where.get_nodes(nodes.Relation):
        ovar = _may_be_removed(rel, schema, mainvar)
        if ovar is not None:
            toremove.add(ovar)
    removed = set()
    while toremove:
        trvar = toremove.pop()
        trvarname = trvar.name
        # remove paths using this variable from the graph
        linkedvars = vargraph.pop(trvarname)
        for ovarname in linkedvars:
            vargraph[ovarname].remove(trvarname)
        # remove relation using this variable
        for rel in trvar.stinfo['relations']:
            if rel in removed:
                # already removed
                continue
            rqlst.remove_node(rel)
            removed.add(rel)
        rel = trvar.stinfo['typerel']
        if rel is not None and not rel in removed:
            rqlst.remove_node(rel)
            removed.add(rel)
        # cleanup groupby clause
        if rqlst.groupby:
            for vref in rqlst.groupby[:]:
                if vref.name == trvarname:
                    rqlst.remove_group_var(vref)
        # we can also remove all variables which are linked to this variable
        # and have no path to the main variable
        for ovarname in linkedvars:
            if ovarname == mainvar.name:
                continue
            if not has_path(vargraph, ovarname, mainvar.name):
                toremove.add(rqlst.defined_vars[ovarname])


## base facet classes ##########################################################

class AbstractFacet(AppObject):
    """Abstract base class for all facets. Facets are stored in their own
    'facets' registry. They are similar to contextual components since the use
    the following configurable properties:

    * `visible`, boolean flag telling if a facet should be displayed or not

    * `order`, integer to control facets display order

    * `context`, telling if a facet should be displayed in the table form filter
      (context = 'tablefilter') or in the facet box (context = 'facetbox') or in
      both (context = '')

    The following methods define the facet API:

    .. automethod:: cubicweb.web.facet.AbstractFacet.get_widget
    .. automethod:: cubicweb.web.facet.AbstractFacet.add_rql_restrictions

    Facets will have the following attributes set (beside the standard
    :class:`~cubicweb.appobject.AppObject` ones):

    * `rqlst`, the rql syntax tree being facetted

    * `filtered_variable`, the variable node in this rql syntax tree that we're
      interested in filtering

    Facets implementors may also be interested in the following properties /
    methods:

    .. automethod:: cubicweb.web.facet.AbstractFacet.operator
    .. automethod:: cubicweb.web.facet.AbstractFacet.rqlexec
    """
    __abstract__ = True
    __registry__ = 'facets'
    cw_property_defs = {
        _('visible'): dict(type='Boolean', default=True,
                           help=_('display the facet or not')),
        _('order'):   dict(type='Int', default=99,
                           help=_('display order of the facet')),
        _('context'): dict(type='String', default='',
                           # None <-> both
                           vocabulary=(_('tablefilter'), _('facetbox'), ''),
                           help=_('context where this facet should be displayed, '
                                  'leave empty for both')),
        }
    visible = True
    context = ''
    needs_update = False
    start_unfolded = True
    cw_rset = None # ensure facets have a cw_rset attribute

    def __init__(self, req, rqlst=None, filtered_variable=None,
                 **kwargs):
        super(AbstractFacet, self).__init__(req, **kwargs)
        assert rqlst is not None
        assert filtered_variable
        # take care: facet may be retreived using `object_by_id` from an ajax call
        # or from `select` using the result set to filter
        self.rqlst = rqlst
        self.filtered_variable = filtered_variable

    @property
    def operator(self):
        """Return the operator (AND or OR) to use for this facet when multiple
        values are selected.
        """
        # OR between selected values by default
        return self._cw.form.get(self.__regid__ + '_andor', 'OR')

    def rqlexec(self, rql, args=None):
        """Utility method to execute some rql queries, and simply returning an
        empty list if :exc:`Unauthorized` is raised.
        """
        try:
            return self._cw.execute(rql, args)
        except Unauthorized:
            return []

    def get_widget(self):
        """Return the widget instance to use to display this facet, or None if
        the facet can't do anything valuable (only one value in the vocabulary
        for instance).
        """
        raise NotImplementedError

    def add_rql_restrictions(self):
        """When some facet criteria has been updated, this method is called to
        add restriction for this facet into the rql syntax tree. It should get
        back its value in form parameters, and modify the syntax tree
        (`self.rqlst`) accordingly.
        """
        raise NotImplementedError


class VocabularyFacet(AbstractFacet):
    """This abstract class extend :class:`AbstractFacet` to use the
    :class:`FacetVocabularyWidget` as widget, suitable for facets that may
    restrict values according to a (usually computed) vocabulary.

    A class which inherits from VocabularyFacet must define at least these methods:

    .. automethod:: cubicweb.web.facet.VocabularyFacet.vocabulary
    .. automethod:: cubicweb.web.facet.VocabularyFacet.possible_values
    """
    needs_update = True

    def get_widget(self):
        """Return the widget instance to use to display this facet.

        This implementation expects a .vocabulary method on the facet and
        return a combobox displaying this vocabulary.
        """
        vocab = self.vocabulary()
        if len(vocab) <= 1:
            return None
        wdg = FacetVocabularyWidget(self)
        selected = frozenset(typed_eid(eid) for eid in self._cw.list_form_param(self.__regid__))
        for label, value in vocab:
            if value is None:
                wdg.append(FacetSeparator(label))
            else:
                wdg.append(FacetItem(self._cw, label, value, value in selected))
        return wdg

    def vocabulary(self):
        """Return vocabulary for this facet, eg a list of 2-uple (label, value).
        """
        raise NotImplementedError

    def possible_values(self):
        """Return a list of possible values (as string since it's used to
        compare to a form value in javascript) for this facet.
        """
        raise NotImplementedError

    def support_and(self):
        return False


class RelationFacet(VocabularyFacet):
    """Base facet to filter some entities according to other entities to which
    they are related. Create concret facet by inheriting from this class an then
    configuring it by setting class attribute described below.

    The relation is defined by the `rtype` and `role` attributes.

    The `no_relation` boolean flag tells if a special 'no relation' value should be
    added (allowing to filter on entities which *do not* have the relation set).
    Default is computed according the relation's cardinality.

    The values displayed for related entities will be:

    * result of calling their `label_vid` view if specified
    * else their `target_attr` attribute value if specified
    * else their eid (you usually want something nicer...)

    When no `label_vid` is set, you will get translated value if `i18nable` is
    set. By default, `i18nable` will be set according to the schema, but you can
    force its value by setting it has a class attribute.

    You can filter out target entity types by specifying `target_type`

    By default, vocabulary will be displayed sorted on `target_attr` value in an
    ascending way. You can control sorting with:

    * `sortfunc`: set this to a stored procedure name if you want to sort on the
      result of this function's result instead of direct value

    * `sortasc`: boolean flag to control ascendant/descendant sorting

    To illustrate this facet, let's take for example an *excerpt* of the schema
    of an office location search application:

    .. sourcecode:: python

      class Office(WorkflowableEntityType):
          price = Int(description='euros / m2 / HC / HT')
          surface = Int(description='m2')
          has_address = SubjectRelation('PostalAddress',
                                        cardinality='1?',
                                        composite='subject')
          proposed_by = SubjectRelation('Agency')


    We can simply define a facet to filter offices according to the agency
    proposing it:

    .. sourcecode:: python

      class AgencyFacet(RelationFacet):
          __regid__ = 'agency'
          # this facet should only be selected when visualizing offices
          __select__ = RelationFacet.__select__ & is_instance('Office')
          # this facet is a filter on the 'Agency' entities linked to the office
          # through the 'proposed_by' relation, where the office is the subject
          # of the relation
          rtype = 'has_address'
          # 'subject' is the default but setting it explicitly doesn't hurt...
          role = 'subject'
          # we want to display the agency's name
          target_attr = 'name'
    """
    __select__ = partial_relation_possible() & match_context_prop()
    # class attributes to configure the relation facet
    rtype = None
    role = 'subject'
    target_attr = 'eid'
    target_type = None
    # set this to a stored procedure name if you want to sort on the result of
    # this function's result instead of direct value
    sortfunc = None
    # ascendant/descendant sorting
    sortasc = True
    # if you want to call a view on the entity instead of using `target_attr`
    label_vid = None

    # internal purpose
    _select_target_entity = True

    title = property(rtype_facet_title)
    no_relation_label = '<no relation>'

    @property
    def i18nable(self):
        """should label be internationalized"""
        if self.target_type:
            eschema = self._cw.vreg.schema.eschema(self.target_type)
        elif self.role == 'subject':
            eschema = self._cw.vreg.schema.rschema(self.rtype).objects()[0]
        else:
            eschema = self._cw.vreg.schema.rschema(self.rtype).subjects()[0]
        return getattr(eschema.rdef(self.target_attr), 'internationalizable', False)

    @property
    def no_relation(self):
        return (not self._cw.vreg.schema.rschema(self.rtype).final
                and self._search_card('?*'))

    @property
    def rql_sort(self):
        """return true if we can handle sorting in the rql query. E.g.  if
        sortfunc is set or if we have not to transform the returned value (eg no
        label_vid and not i18nable)
        """
        return self.sortfunc is not None or (self.label_vid is None
                                             and not self.i18nable)

    def vocabulary(self):
        """return vocabulary for this facet, eg a list of 2-uple (label, value)
        """
        rqlst = self.rqlst
        rqlst.save_state()
        if self.rql_sort:
            sort = self.sortasc
        else:
            sort = None # will be sorted on label
        try:
            mainvar = self.filtered_variable
            var = insert_attr_select_relation(
                rqlst, mainvar, self.rtype, self.role, self.target_attr,
                self.sortfunc, sort, self._select_target_entity)
            if self.target_type is not None:
                rqlst.add_type_restriction(var, self.target_type)
            try:
                rset = self.rqlexec(rqlst.as_string(), self.cw_rset.args)
            except:
                self.exception('error while getting vocabulary for %s, rql: %s',
                               self, rqlst.as_string())
                return ()
        finally:
            rqlst.recover()
        # don't call rset_vocabulary on empty result set, it may be an empty
        # *list* (see rqlexec implementation)
        values = rset and self.rset_vocabulary(rset) or []
        if self._include_no_relation():
            values.insert(0, (self._cw._(self.no_relation_label), ''))
        return values

    def possible_values(self):
        """return a list of possible values (as string since it's used to
        compare to a form value in javascript) for this facet
        """
        rqlst = self.rqlst
        rqlst.save_state()
        try:
            _cleanup_rqlst(rqlst, self.filtered_variable)
            if self._select_target_entity:
                _prepare_vocabulary_rqlst(rqlst, self.filtered_variable, self.rtype,
                                          self.role, select_target_entity=True)
            else:
                insert_attr_select_relation(
                    rqlst, self.filtered_variable, self.rtype, self.role, self.target_attr,
                    select_target_entity=False)
            values = [str(x) for x, in self.rqlexec(rqlst.as_string())]
        except:
            self.exception('while computing values for %s', self)
            return []
        finally:
            rqlst.recover()
        if self._include_no_relation():
            values.append('')
        return values

    def rset_vocabulary(self, rset):
        if self.i18nable:
            _ = self._cw._
        else:
            _ = unicode
        if self.rql_sort:
            values = [(_(label), eid) for eid, label in rset]
        else:
            if self.label_vid is None:
                values = [(_(label), eid) for eid, label in rset]
            else:
                values = [(entity.view(self.label_vid), entity.eid)
                          for entity in rset.entities()]
            values = sorted(values)
            if not self.sortasc:
                values = list(reversed(values))
        return values

    def support_and(self):
        return self._search_card('+*')

    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        value = self._cw.form.get(self.__regid__)
        if value is None:
            return
        mainvar = self.filtered_variable
        restrvar, rel = _add_rtype_relation(self.rqlst, mainvar, self.rtype,
                                            self.role)
        if isinstance(value, basestring):
            # only one value selected
            if value:
                self.rqlst.add_eid_restriction(restrvar, value)
            else:
                rel.parent.replace(rel, nodes.Not(rel))
        elif self.operator == 'OR':
            # set_distinct only if rtype cardinality is > 1
            if self.support_and():
                self.rqlst.set_distinct(True)
            # multiple ORed values: using IN is fine
            if '' in value:
                value.remove('')
                self._add_not_rel_restr(rel)
            _add_eid_restr(rel, restrvar, value)
        else:
            # multiple values with AND operator
            if '' in value:
                value.remove('')
                self._add_not_rel_restr(rel)
            _add_eid_restr(rel, restrvar, value.pop())
            while value:
                restrvar, rtrel = _make_relation(self.rqlst, mainvar,
                                                 self.rtype, self.role)
                _add_eid_restr(rel, restrvar, value.pop())

    @cached
    def _search_card(self, cards):
        for rdef in self._iter_rdefs():
            if rdef.role_cardinality(self.role) in cards:
                return True
        return False

    def _iter_rdefs(self):
        rschema = self._cw.vreg.schema.rschema(self.rtype)
        # XXX when called via ajax, no rset to compute possible types
        possibletypes = self.cw_rset and self.cw_rset.column_types(0)
        for rdef in rschema.rdefs.itervalues():
            if possibletypes is not None:
                if self.role == 'subject':
                    if rdef.subject not in possibletypes:
                        continue
                elif rdef.object not in possibletypes:
                    continue
            if self.target_type is not None:
                if self.role == 'subject':
                    if rdef.object != self.target_type:
                        continue
                elif rdef.subject != self.target_type:
                    continue
            yield rdef

    def _include_no_relation(self):
        if not self.no_relation:
            return False
        if self._cw.vreg.schema.rschema(self.rtype).final:
            return False
        if self.role == 'object':
            subj = utils.rqlvar_maker(defined=self.rqlst.defined_vars,
                                      aliases=self.rqlst.aliases).next()
            obj = self.filtered_variable.name
        else:
            subj = self.filtered_variable.name
            obj = utils.rqlvar_maker(defined=self.rqlst.defined_vars,
                                     aliases=self.rqlst.aliases).next()
        restrictions = []
        if self.rqlst.where:
            restrictions.append(self.rqlst.where.as_string())
        if self.rqlst.with_:
            restrictions.append('WITH ' + ','.join(
                term.as_string() for term in self.rqlst.with_))
        if restrictions:
            restrictions = ',' + ','.join(restrictions)
        else:
            restrictions = ''
        rql = 'Any %s LIMIT 1 WHERE NOT %s %s %s%s' % (
            self.filtered_variable.name, subj, self.rtype, obj, restrictions)
        try:
            return bool(self.rqlexec(rql, self.cw_rset and self.cw_rset.args))
        except:
            # catch exception on executing rql, work-around #1356884 until a
            # proper fix
            self.exception('cant handle rql generated by %s', self)
            return False

    def _add_not_rel_restr(self, rel):
        nrrel = nodes.Not(_make_relation(self.rqlst, self.filtered_variable,
                                         self.rtype, self.role)[1])
        rel.parent.replace(rel, nodes.Or(nrrel, rel))


class RelationAttributeFacet(RelationFacet):
    """Base facet to filter some entities according to an attribute of other
    entities to which they are related. Most things work similarly as
    :class:`RelationFacet`, except that:

    * `label_vid` doesn't make sense here

    * you should specify the attribute type using `attrtype` if it's not a
      String

    * you can specify a comparison operator using `comparator`


    Back to our example... if you want to search office by postal code and that
    you use a :class:`RelationFacet` for that, you won't get the expected
    behaviour: if two offices have the same postal code, they've however two
    different addresses.  So you'll see in the facet the same postal code twice,
    though linked to a different address entity. There is a great chance your
    users won't understand that...

    That's where this class come in ! It's used to said that you want to filter
    according to the *attribute value* of a relatied entity, not to the entity
    itself. Now here is the source code for the facet:

    .. sourcecode:: python

      class PostalCodeFacet(RelationAttributeFacet):
          __regid__ = 'postalcode'
          # this facet should only be selected when visualizing offices
          __select__ = RelationAttributeFacet.__select__ & is_instance('Office')
          # this facet is a filter on the PostalAddress entities linked to the
          # office through the 'has_address' relation, where the office is the
          # subject of the relation
          rtype = 'has_address'
          role = 'subject'
          # we want to search according to address 'postal_code' attribute
          target_attr = 'postalcode'
    """
    _select_target_entity = False
    # attribute type
    attrtype = 'String'
    # type of comparison: default is an exact match on the attribute value
    comparator = '=' # could be '<', '<=', '>', '>='

    def rset_vocabulary(self, rset):
        if self.i18nable:
            _ = self._cw._
        else:
            _ = unicode
        if self.rql_sort:
            return [(_(value), value) for value, in rset]
        values = [(_(value), value) for value, in rset]
        if self.sortasc:
            return sorted(values)
        return reversed(sorted(values))

    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        value = self._cw.form.get(self.__regid__)
        if not value:
            return
        mainvar = self.filtered_variable
        restrvar = _add_rtype_relation(self.rqlst, mainvar, self.rtype,
                                       self.role)[0]
        self.rqlst.set_distinct(True)
        if isinstance(value, basestring) or self.operator == 'OR':
            # only one value selected or multiple ORed values: using IN is fine
            self.rqlst.add_constant_restriction(
                restrvar, self.target_attr, value,
                self.attrtype, self.comparator)
        else:
            # multiple values with AND operator
            self.rqlst.add_constant_restriction(
                restrvar, self.target_attr, value.pop(),
                self.attrtype, self.comparator)
            while value:
                restrvar = _add_rtype_relation(self.rqlst, mainvar, self.rtype,
                                               self.role)[0]
                self.rqlst.add_constant_restriction(
                    restrvar, self.target_attr, value.pop(),
                    self.attrtype, self.comparator)


class AttributeFacet(RelationAttributeFacet):
    """Base facet to filter some entities according one of their attribute.
    Configuration is mostly similarly as :class:`RelationAttributeFacet`, except that:

    * `target_attr` doesn't make sense here (you specify the attribute using `rtype`
    * `role` neither, it's systematically 'subject'

    So, suppose that in our office search example you want to refine search according
    to the office's surface. Here is a code snippet achieving this:

    .. sourcecode:: python

      class SurfaceFacet(AttributeFacet):
          __regid__ = 'surface'
          __select__ = AttributeFacet.__select__ & is_instance('Office')
          # this facet is a filter on the office'surface
          rtype = 'surface'
          # override the default value of operator since we want to filter
          # according to a minimal value, not an exact one
          comparator = '>='

          def vocabulary(self):
              '''override the default vocabulary method since we want to
              hard-code our threshold values.

              Not overriding would generate a filter containing all existing
              surfaces defined in the database.
              '''
              return [('> 200', '200'), ('> 250', '250'),
                      ('> 275', '275'), ('> 300', '300')]
    """

    _select_target_entity = True

    @property
    def i18nable(self):
        """should label be internationalized"""
        for rdef in self._iter_rdefs():
            # no 'internationalizable' property for rdef whose object is not a
            # String
            if not getattr(rdef, 'internationalizable', False):
                return False
        return True

    def vocabulary(self):
        """return vocabulary for this facet, eg a list of 2-uple (label, value)
        """
        rqlst = self.rqlst
        rqlst.save_state()
        try:
            mainvar = self.filtered_variable
            _cleanup_rqlst(rqlst, mainvar)
            newvar = _prepare_vocabulary_rqlst(rqlst, mainvar, self.rtype, self.role)
            _set_orderby(rqlst, newvar, self.sortasc, self.sortfunc)
            try:
                rset = self.rqlexec(rqlst.as_string(), self.cw_rset.args)
            except:
                self.exception('error while getting vocabulary for %s, rql: %s',
                               self, rqlst.as_string())
                return ()
        finally:
            rqlst.recover()
        # don't call rset_vocabulary on empty result set, it may be an empty
        # *list* (see rqlexec implementation)
        return rset and self.rset_vocabulary(rset)

    def support_and(self):
        return False

    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        value = self._cw.form.get(self.__regid__)
        if not value:
            return
        mainvar = self.filtered_variable
        self.rqlst.add_constant_restriction(mainvar, self.rtype, value,
                                            self.attrtype, self.comparator)


class RangeFacet(AttributeFacet):
    """This class allows to filter entities according to an attribute of
    numerical type.

    It displays a slider using `jquery`_ to choose a lower bound and an upper
    bound.

    The example below provides an alternative to the surface facet seen earlier,
    in a more powerful way since

    * lower/upper boundaries are computed according to entities to filter
    * user can specify lower/upper boundaries, not only the lower one

    .. sourcecode:: python

      class SurfaceFacet(RangeFacet):
          __regid__ = 'surface'
          __select__ = RangeFacet.__select__ & is_instance('Office')
          # this facet is a filter on the office'surface
          rtype = 'surface'

    All this with even less code!

    The image below display the rendering of the slider:

    .. image:: ../images/facet_range.png

    .. _jquery: http://www.jqueryui.com/
    """
    attrtype = 'Float' # only numerical types are supported

    @property
    def wdgclass(self):
        return FacetRangeWidget

    def get_widget(self):
        """return the widget instance to use to display this facet"""
        values = set(value for _, value in self.vocabulary() if value is not None)
        # Rset with entities (the facet is selected) but without values
        if len(values) == 0:
            return None
        return self.wdgclass(self, min(values), max(values))

    def infvalue(self):
        return self._cw.form.get('%s_inf' % self.__regid__)

    def supvalue(self):
        return self._cw.form.get('%s_sup' % self.__regid__)

    def formatvalue(self, value):
        """format `value` before in order to insert it in the RQL query"""
        return unicode(value)

    def add_rql_restrictions(self):
        infvalue = self.infvalue()
        if infvalue is None: # nothing sent
            return
        supvalue = self.supvalue()
        self.rqlst.add_constant_restriction(self.filtered_variable,
                                            self.rtype,
                                            self.formatvalue(infvalue),
                                            self.attrtype, '>=')
        self.rqlst.add_constant_restriction(self.filtered_variable,
                                            self.rtype,
                                            self.formatvalue(supvalue),
                                            self.attrtype, '<=')


class DateRangeFacet(RangeFacet):
    """This class works similarly as the :class:`RangeFacet` but for attribute
    of date type.

    The image below display the rendering of the slider for a date range:

    .. image:: ../images/facet_date_range.png
    """
    attrtype = 'Date' # only date types are supported

    @property
    def wdgclass(self):
        return DateFacetRangeWidget

    def formatvalue(self, value):
        """format `value` before in order to insert it in the RQL query"""
        return '"%s"' % date.fromtimestamp(float(value) / 1000).strftime('%Y/%m/%d')


class HasRelationFacet(AbstractFacet):
    """This class simply filter according to the presence of a relation
    (whatever the entity at the other end). It display a simple checkbox that
    lets you refine your selection in order to get only entities that actually
    have this relation. You simply have to define which relation using the
    `rtype` and `role` attributes.

    Here is an example of the rendering of thos facet to filter book with image
    and the corresponding code:

    .. image:: ../images/facet_has_image.png

    .. sourcecode:: python

      class HasImageFacet(HasRelationFacet):
          __regid__ = 'hasimage'
          __select__ = HasRelationFacet.__select__ & is_instance('Book')
          rtype = 'has_image'
          role = 'subject'
    """
    rtype = None # override me in subclass
    role = 'subject' # role of filtered entity in the relation

    title = property(rtype_facet_title)

    def support_and(self):
        return False

    def get_widget(self):
        return CheckBoxFacetWidget(self._cw, self,
                                   '%s:%s' % (self.rtype, self),
                                   self._cw.form.get(self.__regid__))

    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        self.rqlst.set_distinct(True) # XXX
        value = self._cw.form.get(self.__regid__)
        if not value: # no value sent for this facet
            return
        var = self.rqlst.make_variable()
        if self.role == 'subject':
            self.rqlst.add_relation(self.filtered_variable, self.rtype, var)
        else:
            self.rqlst.add_relation(var, self.rtype, self.filtered_variable)


## html widets ################################################################

class FacetVocabularyWidget(HTMLWidget):

    def __init__(self, facet):
        self.facet = facet
        self.items = []

    def append(self, item):
        self.items.append(item)

    def _render(self):
        title = xml_escape(self.facet.title)
        facetid = xml_escape(self.facet.__regid__)
        self.w(u'<div id="%s" class="facet">\n' % facetid)
        self.w(u'<div class="facetTitle" cubicweb:facetName="%s">%s</div>\n' %
               (xml_escape(facetid), title))
        if self.facet.support_and():
            _ = self.facet._cw._
            self.w(u'''<select name="%s" class="radio facetOperator" title="%s">
  <option value="OR">%s</option>
  <option value="AND">%s</option>
</select>''' % (facetid + '_andor', _('and/or between different values'),
                _('OR'), _('AND')))
        cssclass = ''
        if not self.facet.start_unfolded:
            cssclass += ' hidden'
        if len(self.items) > 6:
            cssclass += ' overflowed'
        self.w(u'<div class="facetBody%s">\n' % cssclass)
        for item in self.items:
            item.render(w=self.w)
        self.w(u'</div>\n')
        self.w(u'</div>\n')


class FacetStringWidget(HTMLWidget):
    def __init__(self, facet):
        self.facet = facet
        self.value = None

    def _render(self):
        title = xml_escape(self.facet.title)
        facetid = xml_escape(self.facet.__regid__)
        self.w(u'<div id="%s" class="facet">\n' % facetid)
        self.w(u'<div class="facetTitle" cubicweb:facetName="%s">%s</div>\n' %
               (facetid, title))
        self.w(u'<input name="%s" type="text" value="%s" />\n' % (facetid, self.value or u''))
        self.w(u'</div>\n')


class FacetRangeWidget(HTMLWidget):
    formatter = 'function (value) {return value;}'
    onload = u'''
    var _formatter = %(formatter)s;
    jQuery("#%(sliderid)s").slider({
        range: true,
        min: %(minvalue)s,
        max: %(maxvalue)s,
        values: [%(minvalue)s, %(maxvalue)s],
        stop: function(event, ui) { // submit when the user stops sliding
           var form = $('#%(sliderid)s').closest('form');
           buildRQL.apply(null, evalJSON(form.attr('cubicweb:facetargs')));
        },
        slide: function(event, ui) {
            jQuery('#%(sliderid)s_inf').html(_formatter(ui.values[0]));
            jQuery('#%(sliderid)s_sup').html(_formatter(ui.values[1]));
            jQuery('input[name=%(facetid)s_inf]').val(ui.values[0]);
            jQuery('input[name=%(facetid)s_sup]').val(ui.values[1]);
        }
   });
   // use JS formatter to format value on page load
   jQuery('#%(sliderid)s_inf').html(_formatter(jQuery('input[name=%(facetid)s_inf]').val()));
   jQuery('#%(sliderid)s_sup').html(_formatter(jQuery('input[name=%(facetid)s_sup]').val()));
'''
    #'# make emacs happier
    def __init__(self, facet, minvalue, maxvalue):
        self.facet = facet
        self.minvalue = minvalue
        self.maxvalue = maxvalue

    def _render(self):
        facet = self.facet
        facet._cw.add_js('ui.slider.js')
        facet._cw.add_css('ui.all.css')
        sliderid = make_uid('theslider')
        facetid = xml_escape(self.facet.__regid__)
        facet._cw.html_headers.add_onload(self.onload % {
            'sliderid': sliderid,
            'facetid': facetid,
            'minvalue': self.minvalue,
            'maxvalue': self.maxvalue,
            'formatter': self.formatter,
            })
        title = xml_escape(self.facet.title)
        self.w(u'<div id="%s" class="facet">\n' % facetid)
        self.w(u'<div class="facetTitle" cubicweb:facetName="%s">%s</div>\n' %
               (facetid, title))
        self.w(u'<span id="%s_inf"></span> - <span id="%s_sup"></span>'
               % (sliderid, sliderid))
        self.w(u'<input type="hidden" name="%s_inf" value="%s" />'
               % (facetid, self.minvalue))
        self.w(u'<input type="hidden" name="%s_sup" value="%s" />'
               % (facetid, self.maxvalue))
        self.w(u'<div id="%s"></div>' % sliderid)
        self.w(u'</div>\n')


class DateFacetRangeWidget(FacetRangeWidget):

    formatter = 'function (value) {return (new Date(parseFloat(value))).strftime(DATE_FMT);}'

    def round_max_value(self, d):
        'round to upper value to avoid filtering out the max value'
        return datetime(d.year, d.month, d.day) + timedelta(days=1)

    def __init__(self, facet, minvalue, maxvalue):
        maxvalue = self.round_max_value(maxvalue)
        super(DateFacetRangeWidget, self).__init__(facet,
                                                   datetime2ticks(minvalue),
                                                   datetime2ticks(maxvalue))
        fmt = facet._cw.property_value('ui.date-format')
        facet._cw.html_headers.define_var('DATE_FMT', fmt)


class FacetItem(HTMLWidget):

    selected_img = "black-check.png"
    unselected_img = "no-check-no-border.png"

    def __init__(self, req, label, value, selected=False):
        self._cw = req
        self.label = label
        self.value = value
        self.selected = selected

    def _render(self):
        if self.selected:
            cssclass = ' facetValueSelected'
            imgsrc = self._cw.datadir_url + self.selected_img
            imgalt = self._cw._('selected')
        else:
            cssclass = ''
            imgsrc = self._cw.datadir_url + self.unselected_img
            imgalt = self._cw._('not selected')
        self.w(u'<div class="facetValue facetCheckBox%s" cubicweb:value="%s">\n'
               % (cssclass, xml_escape(unicode(self.value))))
        self.w(u'<img src="%s" alt="%s"/>&#160;' % (imgsrc, imgalt))
        self.w(u'<a href="javascript: {}">%s</a>' % xml_escape(self.label))
        self.w(u'</div>')


class CheckBoxFacetWidget(HTMLWidget):
    selected_img = "black-check.png"
    unselected_img = "black-uncheck.png"

    def __init__(self, req, facet, value, selected):
        self._cw = req
        self.facet = facet
        self.value = value
        self.selected = selected

    def _render(self):
        title = xml_escape(self.facet.title)
        facetid = xml_escape(self.facet.__regid__)
        self.w(u'<div id="%s" class="facet">\n' % facetid)
        if self.selected:
            cssclass = ' facetValueSelected'
            imgsrc = self._cw.datadir_url + self.selected_img
            imgalt = self._cw._('selected')
        else:
            cssclass = ''
            imgsrc = self._cw.datadir_url + self.unselected_img
            imgalt = self._cw._('not selected')
        self.w(u'<div class="facetValue facetCheckBox%s" cubicweb:value="%s">\n'
               % (cssclass, xml_escape(unicode(self.value))))
        self.w(u'<div class="facetCheckBoxWidget">')
        self.w(u'<img src="%s" alt="%s" cubicweb:unselimg="true" />&#160;' % (imgsrc, imgalt))
        self.w(u'<label class="facetTitle" cubicweb:facetName="%s"><a href="javascript: {}">%s</a></label>' % (facetid, title))
        self.w(u'</div>\n')
        self.w(u'</div>\n')
        self.w(u'</div>\n')


class FacetSeparator(HTMLWidget):
    def __init__(self, label=None):
        self.label = label or u'&#160;'

    def _render(self):
        pass

# other classes ################################################################

class FilterRQLBuilder(object):
    """called by javascript to get a rql string from filter form"""

    def __init__(self, req):
        self._cw = req

    def build_rql(self):#, tablefilter=False):
        form = self._cw.form
        facetids = form['facets'].split(',')
        # XXX Union unsupported yet
        select = self._cw.vreg.parse(self._cw, form['baserql']).children[0]
        mainvar = filtered_variable(select)
        toupdate = []
        for facetid in facetids:
            facet = get_facet(self._cw, facetid, select, mainvar)
            facet.add_rql_restrictions()
            if facet.needs_update:
                toupdate.append(facetid)
        return select.as_string(), toupdate
