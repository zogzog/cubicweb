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
.. autoclass:: cubicweb.web.facet.RQLPathFacet
.. autoclass:: cubicweb.web.facet.RangeFacet
.. autoclass:: cubicweb.web.facet.DateRangeFacet
.. autoclass:: cubicweb.web.facet.BitFieldFacet
.. autoclass:: cubicweb.web.facet.AbstractRangeRQLPathFacet
.. autoclass:: cubicweb.web.facet.RangeRQLPathFacet
.. autoclass:: cubicweb.web.facet.DateRangeRQLPathFacet

Classes for facets implementor
------------------------------
Unless you didn't find the class that does the job you want above, you may want
to skip those classes...

.. autoclass:: cubicweb.web.facet.AbstractFacet
.. autoclass:: cubicweb.web.facet.VocabularyFacet

.. comment: XXX widgets
"""

__docformat__ = "restructuredtext en"
from cubicweb import _

from functools import reduce
from warnings import warn
from copy import deepcopy
from datetime import datetime, timedelta

from six import text_type, string_types

from logilab.mtconverter import xml_escape
from logilab.common.graph import has_path
from logilab.common.decorators import cached, cachedproperty
from logilab.common.date import datetime2ticks, ustrftime, ticks2datetime
from logilab.common.deprecation import deprecated
from logilab.common.registry import yes

from rql import nodes, utils

from cubicweb import Unauthorized
from cubicweb.schema import display_name
from cubicweb.uilib import css_em_num_value, domid
from cubicweb.utils import make_uid
from cubicweb.predicates import match_context_prop, partial_relation_possible
from cubicweb.appobject import AppObject
from cubicweb.web import RequestError, htmlwidgets


def rtype_facet_title(facet):
    if facet.cw_rset:
        ptypes = facet.cw_rset.column_types(0)
        if len(ptypes) == 1:
            return display_name(facet._cw, facet.rtype, form=facet.role,
                                context=next(iter(ptypes)))
    return display_name(facet._cw, facet.rtype, form=facet.role)

def get_facet(req, facetid, select, filtered_variable):
    return req.vreg['facets'].object_by_id(facetid, req, select=select,
                                           filtered_variable=filtered_variable)

@deprecated('[3.13] filter_hiddens moved to cubicweb.web.views.facets with '
            'slightly modified prototype')
def filter_hiddens(w, baserql, **kwargs):
    from cubicweb.web.views.facets import filter_hiddens
    return filter_hiddens(w, baserql, wdgs=kwargs.pop('facets'), **kwargs)


## rqlst manipulation functions used by facets ################################

def init_facets(rset, select, mainvar=None):
    """Alters in place the <select> for filtering and returns related data.

    Calls :func:`prepare_select` to prepare the syntaxtree for selection and
    :func:`get_filtered_variable` that selects the variable to be filtered and
    drops several parts of the select tree. See each function docstring for
    details.

    :param rset: ResultSet we init facet for.
    :type rset: :class:`~cubicweb.rset.ResultSet`

    :param select: Select statement to be *altered* to support filtering.
    :type select:   :class:`~rql.stmts.Select` from the ``rset`` parameters.

    :param mainvar: Name of the variable we want to filter with facets.
    :type mainvar:  string

    :rtype: (filtered_variable, baserql) tuple.
    :return filtered_variable:  A rql class:`~rql.node.VariableRef`
                                instance as returned by
                                :func:`get_filtered_variable`.

    :return baserql: A string containing the rql before
                     :func:`prepare_select` but after
                     :func:`get_filtered_variable`.
    """
    rset.req.vreg.rqlhelper.annotate(select)
    filtered_variable = get_filtered_variable(select, mainvar)
    baserql = select.as_string(kwargs=rset.args) # before call to prepare_select
    prepare_select(select, filtered_variable)
    return filtered_variable, baserql

def get_filtered_variable(select, mainvar=None):
    """ Return the variable whose name is `mainvar`
    or the first variable selected in column 0
    """
    if mainvar is None:
        vref = next(select.selection[0].iget_nodes(nodes.VariableRef))
        return vref.variable
    return select.defined_vars[mainvar]

def prepare_select(select, filtered_variable):
    """prepare a syntax tree to generate facet filters

    * remove ORDERBY/GROUPBY clauses
    * cleanup selection (remove everything)
    * undefine unnecessary variables
    * set DISTINCT

    Notice unset of LIMIT/OFFSET us expected to be done by a previous call to
    :func:`get_filtered_variable`.
    """
    # cleanup sort terms / group by
    select.remove_sort_terms()
    select.remove_groups()
    # XXX remove aggregat from having
    # selection: only vocabulary entity
    for term in select.selection[:]:
        select.remove_selected(term)
    # remove unbound variables which only have some type restriction
    for dvar in list(select.defined_vars.values()):
        if not (dvar is filtered_variable or dvar.stinfo['relations']):
            select.undefine_variable(dvar)
    # global tree config: DISTINCT, LIMIT, OFFSET
    select.set_distinct(True)

@deprecated('[3.13] use init_facets instead')
def prepare_facets_rqlst(rqlst, args=None):
    assert len(rqlst.children) == 1, 'FIXME: union not yet supported'
    select = rqlst.children[0]
    filtered_variable = get_filtered_variable(select)
    baserql = select.as_string(args)
    prepare_select(select, filtered_variable)
    return filtered_variable, baserql

def prepare_vocabulary_select(select, filtered_variable, rtype, role,
                              select_target_entity=True):
    """prepare a syntax tree to generate a filter vocabulary rql using the given
    relation:
    * create a variable to filter on this relation
    * add the relation
    * add the new variable to GROUPBY clause if necessary
    * add the new variable to the selection
    """
    newvar = _add_rtype_relation(select, filtered_variable, rtype, role)[0]
    if select_target_entity:
        # if select.groupby: XXX we remove groupby now
        #     select.add_group_var(newvar)
        select.add_selected(newvar)
    # add is restriction if necessary
    if filtered_variable.stinfo['typerel'] is None:
        etypes = frozenset(sol[filtered_variable.name] for sol in select.solutions)
        select.add_type_restriction(filtered_variable, etypes)
    return newvar


def insert_attr_select_relation(select, filtered_variable, rtype, role, attrname,
                                sortfuncname=None, sortasc=True,
                                select_target_entity=True):
    """modify a syntax tree to :
    * link a new variable to `filtered_variable` through `rtype` (where filtered_variable has `role`)
    * retrieve only the newly inserted variable and its `attrname`

    Sorting:
    * on `attrname` ascendant (`sortasc`=True) or descendant (`sortasc`=False)
    * on `sortfuncname`(`attrname`) if `sortfuncname` is specified
    * no sort if `sortasc` is None
    """
    cleanup_select(select, filtered_variable)
    var = prepare_vocabulary_select(select, filtered_variable, rtype, role,
                                   select_target_entity)
    attrvar = select.make_variable()
    select.add_relation(var, attrname, attrvar)
    # if query is grouped, we have to add the attribute variable
    #if select.groupby: XXX may not occur anymore
    #    if not attrvar in select.groupby:
    #        select.add_group_var(attrvar)
    if sortasc is not None:
        _set_orderby(select, attrvar, sortasc, sortfuncname)
    # add attribute variable to selection
    select.add_selected(attrvar)
    return var


def cleanup_select(select, filtered_variable):
    """cleanup tree from unnecessary restrictions:
    * attribute selection
    * optional relations linked to the main variable
    * mandatory relations linked to the main variable
    """
    if select.where is None:
        return
    schema = select.root.schema
    toremove = set()
    vargraph = deepcopy(select.vargraph) # graph representing links between variable
    for rel in select.where.get_nodes(nodes.Relation):
        ovar = _may_be_removed(rel, schema, filtered_variable)
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
            select.remove_node(rel)
            removed.add(rel)
        rel = trvar.stinfo['typerel']
        if rel is not None and not rel in removed:
            select.remove_node(rel)
            removed.add(rel)
        # cleanup groupby clause
        if select.groupby:
            for vref in select.groupby[:]:
                if vref.name == trvarname:
                    select.remove_group_var(vref)
        # we can also remove all variables which are linked to this variable
        # and have no path to the main variable
        for ovarname in linkedvars:
            if ovarname == filtered_variable.name:
                continue
            if not has_path(vargraph, ovarname, filtered_variable.name):
                toremove.add(select.defined_vars[ovarname])


def _may_be_removed(rel, schema, variable):
    """if the given relation may be removed from the tree, return the variable
    on the other side of `variable`, else return None
    Conditions:
    * the relation is an attribute selection of the main variable
    * the relation is optional relation linked to the main variable
    * the relation is a mandatory relation linked to the main variable
      without any restriction on the other variable
    """
    lhs, rhs = rel.get_variable_parts()
    rschema = schema.rschema(rel.r_type)
    if lhs.variable is variable:
        try:
            ovar = rhs.variable
        except AttributeError:
            # constant restriction
            # XXX: X title LOWER(T) if it makes sense?
            return None
        if rschema.final:
            if len(ovar.stinfo['relations']) == 1 \
                   and not ovar.stinfo.get('having'):
                # attribute selection
                return ovar
            return None
        opt = 'right'
        cardidx = 0
    elif getattr(rhs, 'variable', None) is variable:
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

def _make_relation(select, variable, rtype, role):
    newvar = select.make_variable()
    if role == 'object':
        rel = nodes.make_relation(newvar, rtype, (variable,), nodes.VariableRef)
    else:
        rel = nodes.make_relation(variable, rtype, (newvar,), nodes.VariableRef)
    return newvar, rel

def _add_rtype_relation(select, variable, rtype, role):
    """add a relation relying `variable` to entities linked by the `rtype`
    relation (where `variable` has `role`)

    return the inserted variable for linked entities.
    """
    newvar, newrel = _make_relation(select, variable, rtype, role)
    select.add_restriction(newrel)
    return newvar, newrel

def _remove_relation(select, rel, var):
    """remove a constraint relation from the syntax tree"""
    # remove the relation
    select.remove_node(rel)
    # remove relations where the filtered variable appears on the
    # lhs and rhs is a constant restriction
    extra = []
    for vrel in var.stinfo['relations']:
        if vrel is rel:
            continue
        if vrel.children[0].variable is var:
            if not vrel.children[1].get_nodes(nodes.Constant):
                extra.append(vrel)
            select.remove_node(vrel)
    return extra

def _set_orderby(select, newvar, sortasc, sortfuncname):
    if sortfuncname is None:
        select.add_sort_var(newvar, sortasc)
    else:
        vref = nodes.variable_ref(newvar)
        vref.register_reference()
        sortfunc = nodes.Function(sortfuncname)
        sortfunc.append(vref)
        term = nodes.SortTerm(sortfunc, sortasc)
        select.add_sort_term(term)

def _get_var(select, varname, varmap):
    try:
        return varmap[varname]
    except KeyError:
        varmap[varname] = var = select.make_variable()
        return var


_prepare_vocabulary_rqlst = deprecated('[3.13] renamed prepare_vocabulary_select')(
    prepare_vocabulary_select)
_cleanup_rqlst = deprecated('[3.13] renamed to cleanup_select')(cleanup_select)


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

    * `select`, the :class:`rql.stmts.Select` node of the rql syntax tree being
      filtered

    * `filtered_variable`, the variable node in this rql syntax tree that we're
      interested in filtering

    Facets implementors may also be interested in the following properties /
    methods:

    .. autoattribute:: cubicweb.web.facet.AbstractFacet.operator
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
    allow_hide = True
    cw_rset = None # ensure facets have a cw_rset attribute

    def __init__(self, req, select=None, filtered_variable=None,
                 **kwargs):
        super(AbstractFacet, self).__init__(req, **kwargs)
        assert select is not None
        assert filtered_variable
        # take care: facet may be retreived using `object_by_id` from an ajax call
        # or from `select` using the result set to filter
        self.select = select
        self.filtered_variable = filtered_variable

    def __repr__(self):
        return '<%s>' % self.__class__.__name__

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
        (`self.select`) accordingly.
        """
        raise NotImplementedError

    @property
    def operator(self):
        """Return the operator (AND or OR) to use for this facet when multiple
        values are selected.
        """
        # OR between selected values by default
        return self._cw.form.get(xml_escape(self.__regid__) + '_andor', 'OR')

    def rqlexec(self, rql, args=None):
        """Utility method to execute some rql queries, and simply returning an
        empty list if :exc:`Unauthorized` is raised.
        """
        try:
            return self._cw.execute(rql, args)
        except Unauthorized:
            return []

    @property
    def wdgclass(self):
        raise NotImplementedError

    @property
    @deprecated('[3.13] renamed .select')
    def rqlst(self):
        return self.select


class VocabularyFacet(AbstractFacet):
    """This abstract class extend :class:`AbstractFacet` to use the
    :class:`FacetVocabularyWidget` as widget, suitable for facets that may
    restrict values according to a (usually computed) vocabulary.

    A class which inherits from VocabularyFacet must define at least these methods:

    .. automethod:: cubicweb.web.facet.VocabularyFacet.vocabulary
    .. automethod:: cubicweb.web.facet.VocabularyFacet.possible_values
    """
    needs_update = True
    support_and = False

    @property
    def wdgclass(self):
        return FacetVocabularyWidget

    def get_selected(self):
        return frozenset(int(eid) for eid in self._cw.list_form_param(self.__regid__))

    def get_widget(self):
        """Return the widget instance to use to display this facet.

        This implementation expects a .vocabulary method on the facet and
        return a combobox displaying this vocabulary.
        """
        vocab = self.vocabulary()
        if len(vocab) <= 1:
            return None
        wdg = self.wdgclass(self)
        selected = self.get_selected()
        for label, value in vocab:
            wdg.items.append((value, label, value in selected))
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


class RelationFacet(VocabularyFacet):
    """Base facet to filter some entities according to other entities to which
    they are related. Create concrete facet by inheriting from this class an then
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

    You can filter out target entity types by specifying `target_type`.

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
    target_type = None
    target_attr = 'eid'
    # for subclasses parametrization, should not change if you want a
    # RelationFacet
    target_attr_type = 'Int'
    restr_attr = 'eid'
    restr_attr_type = 'Int'
    comparator = '=' # could be '<', '<=', '>', '>='
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
    no_relation_label = _('<no relation>')

    def __repr__(self):
        return '<%s on (%s-%s)>' % (self.__class__.__name__, self.rtype, self.role)

    # facet public API #########################################################

    def vocabulary(self):
        """return vocabulary for this facet, eg a list of 2-uple (label, value)
        """
        select = self.select
        select.save_state()
        if self.rql_sort:
            sort = self.sortasc
        else:
            sort = None # will be sorted on label
        try:
            var = insert_attr_select_relation(
                select, self.filtered_variable, self.rtype, self.role,
                self.target_attr, self.sortfunc, sort,
                self._select_target_entity)
            if self.target_type is not None:
                select.add_type_restriction(var, self.target_type)
            try:
                rset = self.rqlexec(select.as_string(), self.cw_rset.args)
            except Exception:
                self.exception('error while getting vocabulary for %s, rql: %s',
                               self, select.as_string())
                return ()
        finally:
            select.recover()
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
        select = self.select
        select.save_state()
        try:
            cleanup_select(select, self.filtered_variable)
            if self._select_target_entity:
                prepare_vocabulary_select(select, self.filtered_variable, self.rtype,
                                         self.role, select_target_entity=True)
            else:
                insert_attr_select_relation(
                    select, self.filtered_variable, self.rtype, self.role,
                    self.target_attr, select_target_entity=False)
            values = [text_type(x) for x, in self.rqlexec(select.as_string())]
        except Exception:
            self.exception('while computing values for %s', self)
            return []
        finally:
            select.recover()
        if self._include_no_relation():
            values.append('')
        return values

    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        value = self._cw.form.get(self.__regid__)
        if value is None:
            return
        filtered_variable = self.filtered_variable
        restrvar, rel = _add_rtype_relation(self.select, filtered_variable,
                                            self.rtype, self.role)
        self.value_restriction(restrvar, rel, value)

    # internal control API #####################################################

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

    def rset_vocabulary(self, rset):
        if self.i18nable:
            tr = self._cw._
        else:
            tr = text_type
        if self.rql_sort:
            values = [(tr(label), eid) for eid, label in rset]
        else:
            if self.label_vid is None:
                values = [(tr(label), eid) for eid, label in rset]
            else:
                values = [(entity.view(self.label_vid), entity.eid)
                          for entity in rset.entities()]
            values = sorted(values)
            if not self.sortasc:
                values = list(reversed(values))
        return values

    @property
    def support_and(self):
        return self._search_card('+*')

    # internal utilities #######################################################

    @cached
    def _support_and_compat(self):
        support = self.support_and
        if callable(support):
            warn('[3.13] %s.support_and is now a property' % self.__class__,
                 DeprecationWarning)
            support = support()
        return support

    def value_restriction(self, restrvar, rel, value):
        # XXX handle rel is None case in RQLPathFacet?
        if self.restr_attr != 'eid':
            self.select.set_distinct(True)
        if isinstance(value, string_types):
            # only one value selected
            if value:
                self.select.add_constant_restriction(
                    restrvar, self.restr_attr, value,
                    self.restr_attr_type)
            else:
                rel.parent.replace(rel, nodes.Not(rel))
        elif self.operator == 'OR':
            # set_distinct only if rtype cardinality is > 1
            if self._support_and_compat():
                self.select.set_distinct(True)
            # multiple ORed values: using IN is fine
            if '' in value:
                value.remove('')
                self._add_not_rel_restr(rel)
            self._and_restriction(rel, restrvar, value)
        else:
            # multiple values with AND operator. We've to generate a query like
            # "X relation A, A eid 1, X relation B, B eid 1", hence the new
            # relations at each iteration in the while loop below 
            if '' in value:
                raise RequestError("this doesn't make sense")
            self._and_restriction(rel, restrvar, value.pop())
            while value:
                restrvar, rtrel = _make_relation(self.select, self.filtered_variable,
                                                 self.rtype, self.role)
                if rel is None:
                    self.select.add_restriction(rtrel)
                else:
                    rel.parent.replace(rel, nodes.And(rel, rtrel))
                self._and_restriction(rel, restrvar, value.pop())

    def _and_restriction(self, rel, restrvar, value):
        if rel is None:
            self.select.add_constant_restriction(restrvar, self.restr_attr,
                                                 value, self.restr_attr_type)
        else:
            rrel = nodes.make_constant_restriction(restrvar, self.restr_attr,
                                                   value, self.restr_attr_type)
            rel.parent.replace(rel, nodes.And(rel, rrel))


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
        for rdef in rschema.rdefs.values():
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
            subj = next(utils.rqlvar_maker(defined=self.select.defined_vars,
                                      aliases=self.select.aliases))
            obj = self.filtered_variable.name
        else:
            subj = self.filtered_variable.name
            obj = next(utils.rqlvar_maker(defined=self.select.defined_vars,
                                     aliases=self.select.aliases))
        restrictions = []
        if self.select.where:
            restrictions.append(self.select.where.as_string())
        if self.select.with_:
            restrictions.append('WITH ' + ','.join(
                term.as_string() for term in self.select.with_))
        if restrictions:
            restrictions = ',' + ','.join(restrictions)
        else:
            restrictions = ''
        rql = 'Any %s LIMIT 1 WHERE NOT %s %s %s%s' % (
            self.filtered_variable.name, subj, self.rtype, obj, restrictions)
        try:
            return bool(self.rqlexec(rql, self.cw_rset and self.cw_rset.args))
        except Exception:
            # catch exception on executing rql, work-around #1356884 until a
            # proper fix
            self.exception('cant handle rql generated by %s', self)
            return False

    def _add_not_rel_restr(self, rel):
        nrrel = nodes.Not(_make_relation(self.select, self.filtered_variable,
                                         self.rtype, self.role)[1])
        rel.parent.replace(rel, nodes.Or(nrrel, rel))


class RelationAttributeFacet(RelationFacet):
    """Base facet to filter some entities according to an attribute of other
    entities to which they are related. Most things work similarly as
    :class:`RelationFacet`, except that:

    * `label_vid` doesn't make sense here

    * you should specify the attribute type using `target_attr_type` if it's not a
      String

    * you can specify a comparison operator using `comparator`


    Back to our example... if you want to search office by postal code and that
    you use a :class:`RelationFacet` for that, you won't get the expected
    behaviour: if two offices have the same postal code, they've however two
    different addresses.  So you'll see in the facet the same postal code twice,
    though linked to a different address entity. There is a great chance your
    users won't understand that...

    That's where this class come in! It's used to said that you want to filter
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
    target_attr_type = 'String'
    # type of comparison: default is an exact match on the attribute value
    comparator = '=' # could be '<', '<=', '>', '>='

    @property
    def restr_attr(self):
        return self.target_attr

    @property
    def restr_attr_type(self):
        return self.target_attr_type

    def rset_vocabulary(self, rset):
        if self.i18nable:
            tr = self._cw._
        else:
            tr = text_type
        if self.rql_sort:
            return [(tr(value), value) for value, in rset]
        values = [(tr(value), value) for value, in rset]
        return sorted(values, reverse=not self.sortasc)


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

    support_and = False
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
        select = self.select
        select.save_state()
        try:
            filtered_variable = self.filtered_variable
            cleanup_select(select, filtered_variable)
            newvar = prepare_vocabulary_select(select, filtered_variable, self.rtype, self.role)
            _set_orderby(select, newvar, self.sortasc, self.sortfunc)
            if self.cw_rset:
                args = self.cw_rset.args
            else: # vocabulary used for possible_values
                args = None
            try:
                rset = self.rqlexec(select.as_string(), args)
            except Exception:
                self.exception('error while getting vocabulary for %s, rql: %s',
                               self, select.as_string())
                return ()
        finally:
            select.recover()
        # don't call rset_vocabulary on empty result set, it may be an empty
        # *list* (see rqlexec implementation)
        return rset and self.rset_vocabulary(rset)

    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        value = self._cw.form.get(self.__regid__)
        if not value:
            return
        filtered_variable = self.filtered_variable
        self.select.add_constant_restriction(filtered_variable, self.rtype, value,
                                            self.target_attr_type, self.comparator)


class RQLPathFacet(RelationFacet):
    """Base facet to filter some entities according to an arbitrary rql
    path. Path should be specified as a list of 3-uples or triplet string, where
    'X' represent the filtered variable. You should specify using
    `filter_variable` the snippet variable that will be used to filter out
    results. You may also specify a `label_variable`. If you want to filter on
    an attribute value, you usually don't want to specify the later since it's
    the same as the filter variable, though you may have to specify the attribute
    type using `restr_attr_type` if there are some type ambiguity in the schema
    for the attribute.

    Using this facet, we can rewrite facets we defined previously:

    .. sourcecode:: python

      class AgencyFacet(RQLPathFacet):
          __regid__ = 'agency'
          # this facet should only be selected when visualizing offices
          __select__ = is_instance('Office')
          # this facet is a filter on the 'Agency' entities linked to the office
          # through the 'proposed_by' relation, where the office is the subject
          # of the relation
          path = ['X has_address O', 'O name N']
          filter_variable = 'O'
          label_variable = 'N'

      class PostalCodeFacet(RQLPathFacet):
          __regid__ = 'postalcode'
          # this facet should only be selected when visualizing offices
          __select__ = is_instance('Office')
          # this facet is a filter on the PostalAddress entities linked to the
          # office through the 'has_address' relation, where the office is the
          # subject of the relation
          path = ['X has_address O', 'O postal_code PC']
          filter_variable = 'PC'

    Though some features, such as 'no value' or automatic internationalization,
    won't work. This facet class is designed to be used for cases where
    :class:`RelationFacet` or :class:`RelationAttributeFacet` can't do the trick
    (e.g when you want to filter on entities where are not directly linked to
    the filtered entities).
    """
    __select__ = yes() # we don't want RelationFacet's selector
    # must be specified
    path = None
    filter_variable = None
    # may be specified
    label_variable = None
    # usually guessed, but may be explicitly specified
    restr_attr = None
    restr_attr_type = None

    # XXX disabled features
    i18nable = False
    no_relation = False
    support_and = False

    def __init__(self, *args, **kwargs):
        super(RQLPathFacet, self).__init__(*args, **kwargs)
        assert self.filter_variable != self.label_variable, \
            ('filter_variable and label_variable should be different. '
             'You may want to let label_variable undefined (ie None).')
        assert self.path and isinstance(self.path, (list, tuple)), \
            'path should be a list of 3-uples, not %s' % self.path
        for part in self.path:
            if isinstance(part, string_types):
                part = part.split()
            assert len(part) == 3, \
                   'path should be a list of 3-uples, not %s' % part

    def __repr__(self):
        return '<%s %s>' % (self.__class__.__name__,
                            ','.join(str(p) for p in self.path))

    def vocabulary(self):
        """return vocabulary for this facet, eg a list of (label, value)"""
        select = self.select
        select.save_state()
        if self.rql_sort:
            sort = self.sortasc
        else:
            sort = None # will be sorted on label
        try:
            cleanup_select(select, self.filtered_variable)
            varmap, restrvar = self.add_path_to_select()
            select.append_selected(nodes.VariableRef(restrvar))
            if self.label_variable:
                attrvar = varmap[self.label_variable]
            else:
                attrvar = restrvar
            select.append_selected(nodes.VariableRef(attrvar))
            if sort is not None:
                _set_orderby(select, attrvar, sort, self.sortfunc)
            try:
                rset = self.rqlexec(select.as_string(), self.cw_rset.args)
            except Exception:
                self.exception('error while getting vocabulary for %s, rql: %s',
                               self, select.as_string())
                return ()
        finally:
            select.recover()
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
        select = self.select
        select.save_state()
        try:
            cleanup_select(select, self.filtered_variable)
            varmap, restrvar = self.add_path_to_select(skiplabel=True)
            select.append_selected(nodes.VariableRef(restrvar))
            values = [text_type(x) for x, in self.rqlexec(select.as_string())]
        except Exception:
            self.exception('while computing values for %s', self)
            return []
        finally:
            select.recover()
        if self._include_no_relation():
            values.append('')
        return values

    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        value = self._cw.form.get(self.__regid__)
        if value is None:
            return
        varmap, restrvar = self.add_path_to_select(
            skiplabel=True, skipattrfilter=True)
        self.value_restriction(restrvar, None, value)

    def add_path_to_select(self, skiplabel=False, skipattrfilter=False):
        varmap = {'X': self.filtered_variable}
        actual_filter_variable = None
        for part in self.path:
            if isinstance(part, string_types):
                part = part.split()
            subject, rtype, object = part
            if skiplabel and object == self.label_variable:
                continue
            if object == self.filter_variable:
                rschema = self._cw.vreg.schema.rschema(rtype)
                if rschema.final:
                    # filter variable is an attribute variable
                    if self.restr_attr is None:
                        self.restr_attr = rtype
                    if self.restr_attr_type is None:
                        attrtypes = set(obj for subj,obj in rschema.rdefs)
                        if len(attrtypes) > 1:
                            raise Exception('ambigous attribute %s, specify attrtype on %s'
                                            % (rtype, self.__class__))
                        self.restr_attr_type = next(iter(attrtypes))
                    if skipattrfilter:
                        actual_filter_variable = subject
                        continue
            subjvar = _get_var(self.select, subject, varmap)
            objvar = _get_var(self.select, object, varmap)
            rel = nodes.make_relation(subjvar, rtype, (objvar,),
                                      nodes.VariableRef)
            self.select.add_restriction(rel)
        if self.restr_attr is None:
            self.restr_attr = 'eid'
        if self.restr_attr_type is None:
            self.restr_attr_type = 'Int'
        if actual_filter_variable:
            restrvar = varmap[actual_filter_variable]
        else:
            restrvar = varmap[self.filter_variable]
        return varmap, restrvar


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

    .. image:: ../../images/facet_range.png

    .. _jquery: http://www.jqueryui.com/
    """
    target_attr_type = 'Float' # only numerical types are supported
    needs_update = False # not supported actually

    @property
    def wdgclass(self):
        return FacetRangeWidget

    def _range_rset(self):
        select = self.select
        select.save_state()
        try:
            filtered_variable = self.filtered_variable
            cleanup_select(select, filtered_variable)
            newvar = _add_rtype_relation(select, filtered_variable, self.rtype, self.role)[0]
            minf = nodes.Function('MIN')
            minf.append(nodes.VariableRef(newvar))
            select.add_selected(minf)
            maxf = nodes.Function('MAX')
            maxf.append(nodes.VariableRef(newvar))
            select.add_selected(maxf)
            # add is restriction if necessary
            if filtered_variable.stinfo['typerel'] is None:
                etypes = frozenset(sol[filtered_variable.name] for sol in select.solutions)
                select.add_type_restriction(filtered_variable, etypes)
            try:
                return self.rqlexec(select.as_string(), self.cw_rset.args)
            except Exception:
                self.exception('error while getting vocabulary for %s, rql: %s',
                               self, select.as_string())
                return ()
        finally:
            select.recover()

    def vocabulary(self):
        """return vocabulary for this facet, eg a list of 2-uple (label, value)
        """
        rset = self._range_rset()
        if rset:
            minv, maxv = rset[0]
            return [(text_type(minv), minv), (text_type(maxv), maxv)]
        return []

    def possible_values(self):
        """Return a list of possible values (as string since it's used to
        compare to a form value in javascript) for this facet.
        """
        return [strval for strval, val in self.vocabulary()]

    def get_widget(self):
        """return the widget instance to use to display this facet"""
        values = set(value for _, value in self.vocabulary() if value is not None)
        # Rset with entities (the facet is selected) but without values
        if len(values) < 2:
            return None
        return self.wdgclass(self, min(values), max(values))

    def formatvalue(self, value):
        """format `value` before in order to insert it in the RQL query"""
        return text_type(value)

    def infvalue(self, min=False):
        if min:
            return self._cw.form.get('min_%s_inf' % self.__regid__)
        return self._cw.form.get('%s_inf' % self.__regid__)

    def supvalue(self, max=False):
        if max:
            return self._cw.form.get('max_%s_sup' % self.__regid__)
        return self._cw.form.get('%s_sup' % self.__regid__)

    def add_rql_restrictions(self):
        infvalue = self.infvalue()
        supvalue = self.supvalue()
        if infvalue is None or supvalue is None: # nothing sent
            return
        # when a value is equal to one of the limit, don't add the restriction,
        # else we filter out NULL values implicitly
        if infvalue != self.infvalue(min=True):
            self._add_restriction(infvalue, '>=')
        if supvalue != self.supvalue(max=True):
            self._add_restriction(supvalue, '<=')

    def _add_restriction(self, value, operator):
        self.select.add_constant_restriction(self.filtered_variable,
                                             self.rtype,
                                             self.formatvalue(value),
                                             self.target_attr_type, operator)


class DateRangeFacet(RangeFacet):
    """This class works similarly as the :class:`RangeFacet` but for attribute
    of date type.

    The image below display the rendering of the slider for a date range:

    .. image:: ../../images/facet_date_range.png
    """
    target_attr_type = 'Date' # only date types are supported

    @property
    def wdgclass(self):
        return DateFacetRangeWidget

    def formatvalue(self, value):
        """format `value` before in order to insert it in the RQL query"""
        try:
            date_value = ticks2datetime(float(value))
        except (ValueError, OverflowError):
            return u'"date out-of-range"'
        return '"%s"' % ustrftime(date_value, '%Y/%m/%d')


class AbstractRangeRQLPathFacet(RQLPathFacet):
    """
    The :class:`AbstractRangeRQLPathFacet` is the base class for
    RQLPathFacet-type facets allowing the use of RangeWidgets-like
    widgets (such as (:class:`FacetRangeWidget`,
    class:`DateFacetRangeWidget`) on the parent :class:`RQLPathFacet`
    target attribute.
    """
    __abstract__ = True

    def vocabulary(self):
        """return vocabulary for this facet, eg a list of (label,
        value)"""
        select = self.select
        select.save_state()
        try:
            filtered_variable = self.filtered_variable
            cleanup_select(select, filtered_variable)
            varmap, restrvar = self.add_path_to_select()
            if self.label_variable:
                attrvar = varmap[self.label_variable]
            else:
                attrvar = restrvar
            # start RangeRQLPathFacet
            minf = nodes.Function('MIN')
            minf.append(nodes.VariableRef(restrvar))
            select.add_selected(minf)
            maxf = nodes.Function('MAX')
            maxf.append(nodes.VariableRef(restrvar))
            select.add_selected(maxf)
            # add is restriction if necessary
            if filtered_variable.stinfo['typerel'] is None:
                etypes = frozenset(sol[filtered_variable.name] for sol in select.solutions)
                select.add_type_restriction(filtered_variable, etypes)
            # end RangeRQLPathFacet
            try:
                rset = self.rqlexec(select.as_string(), self.cw_rset.args)
            except Exception:
                self.exception('error while getting vocabulary for %s, rql: %s',
                               self, select.as_string())
                return ()
        finally:
            select.recover()
        # don't call rset_vocabulary on empty result set, it may be an empty
        # *list* (see rqlexec implementation)
        if rset:
            minv, maxv = rset[0]
            return [(text_type(minv), minv), (text_type(maxv), maxv)]
        return []


    def possible_values(self):
        """return a list of possible values (as string since it's used to
        compare to a form value in javascript) for this facet
        """
        return [strval for strval, val in self.vocabulary()]

    def add_rql_restrictions(self):
        infvalue = self.infvalue()
        supvalue = self.supvalue()
        if infvalue is None or supvalue is None: # nothing sent
            return
        varmap, restrvar = self.add_path_to_select(
            skiplabel=True, skipattrfilter=True)
        restrel = None
        for part in self.path:
            if isinstance(part, string_types):
                part = part.split()
            subject, rtype, object = part
            if object == self.filter_variable:
                restrel = rtype
        assert restrel
        # when a value is equal to one of the limit, don't add the restriction,
        # else we filter out NULL values implicitly
        if infvalue != self.infvalue(min=True):

            self._add_restriction(infvalue, '>=', restrvar, restrel)
        if supvalue != self.supvalue(max=True):
            self._add_restriction(supvalue, '<=', restrvar, restrel)

    def _add_restriction(self, value, operator, restrvar, restrel):
        self.select.add_constant_restriction(restrvar,
                                             restrel,
                                             self.formatvalue(value),
                                             self.target_attr_type, operator)


class RangeRQLPathFacet(AbstractRangeRQLPathFacet, RQLPathFacet):
    """
    The :class:`RangeRQLPathFacet` uses the :class:`FacetRangeWidget`
    on the :class:`AbstractRangeRQLPathFacet` target attribute
    """
    pass


class DateRangeRQLPathFacet(AbstractRangeRQLPathFacet, DateRangeFacet):
    """
    The :class:`DateRangeRQLPathFacet` uses the
    :class:`DateFacetRangeWidget` on the
    :class:`AbstractRangeRQLPathFacet` target attribute
    """
    pass


class HasRelationFacet(AbstractFacet):
    """This class simply filter according to the presence of a relation
    (whatever the entity at the other end). It display a simple checkbox that
    lets you refine your selection in order to get only entities that actually
    have this relation. You simply have to define which relation using the
    `rtype` and `role` attributes.

    Here is an example of the rendering of thos facet to filter book with image
    and the corresponding code:

    .. image:: ../../images/facet_has_image.png

    .. sourcecode:: python

      class HasImageFacet(HasRelationFacet):
          __regid__ = 'hasimage'
          __select__ = HasRelationFacet.__select__ & is_instance('Book')
          rtype = 'has_image'
          role = 'subject'
    """
    __select__ = partial_relation_possible() & match_context_prop()
    rtype = None # override me in subclass
    role = 'subject' # role of filtered entity in the relation

    title = property(rtype_facet_title)
    needs_update = False # not supported actually
    support_and = False

    def get_widget(self):
        return CheckBoxFacetWidget(self._cw, self,
                                   '%s:%s' % (self.rtype, self),
                                   self._cw.form.get(self.__regid__))

    def add_rql_restrictions(self):
        """add restriction for this facet into the rql syntax tree"""
        value = self._cw.form.get(self.__regid__)
        if not value: # no value sent for this facet
            return
        exists = nodes.Exists()
        self.select.add_restriction(exists)
        var = self.select.make_variable()
        if self.role == 'subject':
            subj, obj = self.filtered_variable, var
        else:
            subj, obj = var, self.filtered_variable
        exists.add_relation(subj, self.rtype, obj)


class BitFieldFacet(AttributeFacet):
    """Base facet class for Int field holding some bit values using binary
    masks.

    label / value for each bit should be given using the :attr:`choices`
    attribute.

    See also :class:`~cubicweb.web.formwidgets.BitSelect`.
    """
    choices = None # to be set on concret class
    def add_rql_restrictions(self):
        value = self._cw.form.get(self.__regid__)
        if not value:
            return
        if isinstance(value, list):
            value = reduce(lambda x, y: int(x) | int(y), value)
        else:
            value = int(value)
        attr_var = self.select.make_variable()
        self.select.add_relation(self.filtered_variable, self.rtype, attr_var)
        comp = nodes.Comparison('=', nodes.Constant(value, 'Int'))
        if value == 0:
            comp.append(nodes.variable_ref(attr_var))
        else:
            comp.append(nodes.MathExpression('&', nodes.variable_ref(attr_var),
                                             nodes.Constant(value, 'Int')))
        having = self.select.having
        if having:
            self.select.replace(having[0], nodes.And(having[0], comp))
        else:
            self.select.set_having([comp])

    def rset_vocabulary(self, rset):
        mask = reduce(lambda x, y: x | (y[0] or 0), rset, 0)
        return sorted([(self._cw._(label), val) for label, val in self.choices
                       if not val or val & mask])

    def possible_values(self):
        return [text_type(val) for label, val in self.vocabulary()]


## html widets ################################################################
_DEFAULT_VOCAB_WIDGET_HEIGHT = 12
_DEFAULT_FACET_GROUP_HEIGHT = 15

class FacetVocabularyWidget(htmlwidgets.HTMLWidget):

    def __init__(self, facet):
        self.facet = facet
        self.items = []

    @cachedproperty
    def css_overflow_limit(self):
        """ we try to deduce a number of displayed lines from a css property
        if we get another unit we're out of luck and resort to one constant
        hence, it is strongly advised not to specify but ems for this css prop
        """
        return css_em_num_value(self.facet._cw.vreg, 'facet_vocabMaxHeight',
                                _DEFAULT_VOCAB_WIDGET_HEIGHT)

    @cachedproperty
    def height(self):
        """ title, optional and/or dropdown, len(items) or upper limit """
        return (1.5 + # title + small magic constant
                int(self.facet._support_and_compat() +
                    min(len(self.items), self.css_overflow_limit)))

    @property
    @cached
    def overflows(self):
        return len(self.items) >= self.css_overflow_limit

    scrollbar_padding_factor = 4

    def _render(self):
        w = self.w
        title = xml_escape(self.facet.title)
        facetid = domid(make_uid(self.facet.__regid__))
        w(u'<div id="%s" class="facet">\n' % facetid)
        cssclass = 'facetTitle'
        if self.facet.allow_hide:
            cssclass += ' hideFacetBody'
        w(u'<div class="%s" cubicweb:facetName="%s">%s</div>\n' %
          (cssclass, xml_escape(self.facet.__regid__), title))
        if self.facet._support_and_compat():
            self._render_and_or(w)
        cssclass = 'facetBody vocabularyFacet'
        if not self.facet.start_unfolded:
            cssclass += ' hidden'
        overflow = self.overflows
        if overflow:
            if self.facet._support_and_compat():
                cssclass += ' vocabularyFacetBodyWithLogicalSelector'
            else:
                cssclass += ' vocabularyFacetBody'
        w(u'<div class="%s">\n' % cssclass)
        for value, label, selected in self.items:
            if value is None:
                continue
            self._render_value(w, value, label, selected, overflow)
        w(u'</div>\n')
        w(u'</div>\n')

    def _render_and_or(self, w):
        _ = self.facet._cw._
        w(u"""<select name='%s' class='radio facetOperator' title='%s'>
  <option value='OR'>%s</option>
  <option value='AND'>%s</option>
</select>""" % (xml_escape(self.facet.__regid__) + '_andor',
                _('and/or between different values'),
                _('OR'), _('AND')))

    def _render_value(self, w, value, label, selected, overflow):
        cssclass = 'facetValue facetCheckBox'
        if selected:
            cssclass += ' facetValueSelected'
        w(u'<div class="%s" cubicweb:value="%s">\n'
          % (cssclass, xml_escape(text_type(value))))
        # If it is overflowed one must add padding to compensate for the vertical
        # scrollbar; given current css values, 4 blanks work perfectly ...
        padding = u'&#160;' * self.scrollbar_padding_factor if overflow else u''
        w('<span>%s</span>' % xml_escape(label))
        w(padding)
        w(u'</div>')

class FacetStringWidget(htmlwidgets.HTMLWidget):
    def __init__(self, facet):
        self.facet = facet
        self.value = None

    @property
    def height(self):
        return 2.5

    def _render(self):
        w = self.w
        title = xml_escape(self.facet.title)
        facetid = make_uid(self.facet.__regid__)
        w(u'<div id="%s" class="facet">\n' % facetid)
        cssclass = 'facetTitle'
        if self.facet.allow_hide:
            cssclass += ' hideFacetBody'
        w(u'<div class="%s" cubicweb:facetName="%s">%s</div>\n' %
               (cssclass, xml_escape(self.facet.__regid__), title))
        cssclass = 'facetBody'
        if not self.facet.start_unfolded:
            cssclass += ' hidden'
        w(u'<div class="%s">\n' % cssclass)
        w(u'<input name="%s" type="text" value="%s" />\n' % (
                xml_escape(self.facet.__regid__), self.value or u''))
        w(u'</div>\n')
        w(u'</div>\n')


class FacetRangeWidget(htmlwidgets.HTMLWidget):
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
           buildRQL.apply(null, cw.evalJSON(form.attr('cubicweb:facetargs')));
        },
        slide: function(event, ui) {
            jQuery('#%(sliderid)s_inf').html(_formatter(ui.values[0]));
            jQuery('#%(sliderid)s_sup').html(_formatter(ui.values[1]));
            jQuery('input[name="%(facetname)s_inf"]').val(ui.values[0]);
            jQuery('input[name="%(facetname)s_sup"]').val(ui.values[1]);
        }
   });
   // use JS formatter to format value on page load
   jQuery('#%(sliderid)s_inf').html(_formatter(jQuery('input[name="%(facetname)s_inf"]').val()));
   jQuery('#%(sliderid)s_sup').html(_formatter(jQuery('input[name="%(facetname)s_sup"]').val()));
'''
    #'# make emacs happier
    def __init__(self, facet, minvalue, maxvalue):
        self.facet = facet
        self.minvalue = minvalue
        self.maxvalue = maxvalue

    @property
    def height(self):
        return 2.5

    def _render(self):
        w = self.w
        facet = self.facet
        facet._cw.add_js('jquery.ui.js')
        facet._cw.add_css('jquery.ui.css')
        sliderid = make_uid('theslider')
        facetname = self.facet.__regid__
        facetid = make_uid(facetname)
        facet._cw.html_headers.add_onload(self.onload % {
            'sliderid': sliderid,
            'facetid': facetid,
            'facetname': facetname,
            'minvalue': self.minvalue,
            'maxvalue': self.maxvalue,
            'formatter': self.formatter,
            })
        title = xml_escape(self.facet.title)
        facetname = xml_escape(facetname)
        w(u'<div id="%s" class="facet rangeFacet">\n' % facetid)
        cssclass = 'facetTitle'
        if facet.allow_hide:
            cssclass += ' hideFacetBody'
        w(u'<div class="%s" cubicweb:facetName="%s">%s</div>\n' %
          (cssclass, facetname, title))
        cssclass = 'facetBody'
        if not self.facet.start_unfolded:
            cssclass += ' hidden'
        w(u'<div class="%s">\n' % cssclass)
        w(u'<span id="%s_inf"></span> - <span id="%s_sup"></span>'
          % (sliderid, sliderid))
        w(u'<input type="hidden" name="%s_inf" value="%s" />'
          % (facetname, self.minvalue))
        w(u'<input type="hidden" name="%s_sup" value="%s" />'
          % (facetname, self.maxvalue))
        w(u'<input type="hidden" name="min_%s_inf" value="%s" />'
          % (facetname, self.minvalue))
        w(u'<input type="hidden" name="max_%s_sup" value="%s" />'
          % (facetname, self.maxvalue))
        w(u'<div id="%s"></div>' % sliderid)
        w(u'</div>\n')
        w(u'</div>\n')


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


class CheckBoxFacetWidget(htmlwidgets.HTMLWidget):
    selected_img = "black-check.png"
    unselected_img = "black-uncheck.png"

    def __init__(self, req, facet, value, selected):
        self._cw = req
        self.facet = facet
        self.value = value
        self.selected = selected

    @property
    def height(self):
        return 1.5

    def _render(self):
        w = self.w
        title = xml_escape(self.facet.title)
        facetid = make_uid(self.facet.__regid__)
        w(u'<div id="%s" class="facet">\n' % facetid)
        cssclass = 'facetValue facetCheckBox'
        if self.selected:
            cssclass += ' facetValueSelected'
            imgsrc = self._cw.data_url(self.selected_img)
            imgalt = self._cw._('selected')
        else:
            imgsrc = self._cw.data_url(self.unselected_img)
            imgalt = self._cw._('not selected')
        w(u'<div class="%s" cubicweb:value="%s">\n'
          % (cssclass, xml_escape(text_type(self.value))))
        w(u'<div>')
        w(u'<img src="%s" alt="%s" cubicweb:unselimg="true" />&#160;' % (imgsrc, imgalt))
        w(u'<label class="facetTitle" cubicweb:facetName="%s">%s</label>'
          % (xml_escape(self.facet.__regid__), title))
        w(u'</div>\n')
        w(u'</div>\n')
        w(u'</div>\n')


# other classes ################################################################

class FilterRQLBuilder(object):
    """called by javascript to get a rql string from filter form"""

    def __init__(self, req):
        self._cw = req

    def build_rql(self):
        form = self._cw.form
        facetids = form['facets'].split(',')
        # XXX Union unsupported yet
        select = self._cw.vreg.parse(self._cw, form['baserql']).children[0]
        filtered_variable = get_filtered_variable(select, form.get('mainvar'))
        toupdate = []
        for facetid in facetids:
            facet = get_facet(self._cw, facetid, select, filtered_variable)
            facet.add_rql_restrictions()
            if facet.needs_update:
                toupdate.append(facetid)
        return select.as_string(), toupdate
