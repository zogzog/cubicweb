# copyright 2003-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Base class for entity objects manipulated in clients"""

from warnings import warn

from six import text_type, string_types, integer_types
from six.moves import range

from logilab.common.decorators import cached
from logilab.common.deprecation import deprecated
from logilab.common.registry import yes
from logilab.mtconverter import TransformData, xml_escape

from rql.utils import rqlvar_maker
from rql.stmts import Select
from rql.nodes import (Not, VariableRef, Constant, make_relation,
                       Relation as RqlRelation)

from cubicweb import Unauthorized, neg_role
from cubicweb.utils import support_args
from cubicweb.rset import ResultSet
from cubicweb.appobject import AppObject
from cubicweb.schema import (RQLVocabularyConstraint, RQLConstraint,
                             GeneratedConstraint)
from cubicweb.rqlrewrite import RQLRewriter

from cubicweb.uilib import soup2xhtml
from cubicweb.mttransforms import ENGINE

_marker = object()


def greater_card(rschema, subjtypes, objtypes, index):
    for subjtype in subjtypes:
        for objtype in objtypes:
            card = rschema.rdef(subjtype, objtype).cardinality[index]
            if card in '+*':
                return card
    return '1'

def can_use_rest_path(value):
    """return True if value can be used at the end of a Rest URL path"""
    if value is None:
        return False
    value = text_type(value)
    # the check for ?, /, & are to prevent problems when running
    # behind Apache mod_proxy
    if value == u'' or u'?' in value or u'/' in value or u'&' in value:
        return False
    return True

def rel_vars(rel):
    return ((isinstance(rel.children[0], VariableRef)
             and rel.children[0].variable or None),
            (isinstance(rel.children[1].children[0], VariableRef)
             and rel.children[1].children[0].variable or None)
            )

def rel_matches(rel, rtype, role, varname, operator='='):
    if rel.r_type == rtype and rel.children[1].operator == operator:
        same_role_var_idx = 0 if role == 'subject' else 1
        variables = rel_vars(rel)
        if variables[same_role_var_idx].name == varname:
            return variables[1 - same_role_var_idx]

def build_cstr_with_linkto_infos(cstr, args, searchedvar, evar,
                                 lt_infos, eidvars):
    """restrict vocabulary as much as possible in entity creation,
    based on infos provided by __linkto form param.

    Example based on following schema:

      class works_in(RelationDefinition):
          subject = 'CWUser'
          object = 'Lab'
          cardinality = '1*'
          constraints = [RQLConstraint('S in_group G, O welcomes G')]

      class welcomes(RelationDefinition):
          subject = 'Lab'
          object = 'CWGroup'

    If you create a CWUser in the "scientists" CWGroup you can show
    only the labs that welcome them using :

      lt_infos = {('in_group', 'subject'): 321}

    You get following restriction : 'O welcomes G, G eid 321'

    """
    st = cstr.snippet_rqlst.copy()
    # replace relations in ST by eid infos from linkto where possible
    for (info_rtype, info_role), eids in lt_infos.items():
        eid = eids[0] # NOTE: we currently assume a pruned lt_info with only 1 eid
        for rel in st.iget_nodes(RqlRelation):
            targetvar = rel_matches(rel, info_rtype, info_role, evar.name)
            if targetvar is not None:
                if targetvar.name in eidvars:
                    rel.parent.remove(rel)
                else:
                    eidrel = make_relation(
                        targetvar, 'eid', (targetvar.name, 'Substitute'),
                        Constant)
                    rel.parent.replace(rel, eidrel)
                    args[targetvar.name] = eid
                    eidvars.add(targetvar.name)
    # if modified ST still contains evar references we must discard the
    # constraint, otherwise evar is unknown in the final rql query which can
    # lead to a SQL table cartesian product and multiple occurences of solutions
    evarname = evar.name
    for rel in st.iget_nodes(RqlRelation):
        for variable in rel_vars(rel):
            if variable and evarname == variable.name:
                return
    # else insert snippets into the global tree
    return GeneratedConstraint(st, cstr.mainvars - set(evarname))

def pruned_lt_info(eschema, lt_infos):
    pruned = {}
    for (lt_rtype, lt_role), eids in lt_infos.items():
        # we can only use lt_infos describing relation with a cardinality
        # of value 1 towards the linked entity
        if not len(eids) == 1:
            continue
        lt_card = eschema.rdef(lt_rtype, lt_role).cardinality[
            0 if lt_role == 'subject' else 1]
        if lt_card not in '?1':
            continue
        pruned[(lt_rtype, lt_role)] = eids
    return pruned


class Entity(AppObject):
    """an entity instance has e_schema automagically set on
    the class and instances has access to their issuing cursor.

    A property is set for each attribute and relation on each entity's type
    class. Becare that among attributes, 'eid' is *NEVER* stored in the
    dict containment (which acts as a cache for other attributes dynamically
    fetched)

    :type e_schema: `cubicweb.schema.EntitySchema`
    :ivar e_schema: the entity's schema

    :type rest_attr: str
    :cvar rest_attr: indicates which attribute should be used to build REST urls
       If `None` is specified (the default), the first unique attribute will
       be used ('eid' if none found)

    :type cw_skip_copy_for: list
    :cvar cw_skip_copy_for: a list of couples (rtype, role) for each relation
       that should be skipped when copying this kind of entity. Note that some
       relations such as composite relations or relations that have '?1' as
       object cardinality are always skipped.
    """
    __registry__ = 'etypes'
    __select__ = yes()

    # class attributes that must be set in class definition
    rest_attr = None
    fetch_attrs = None
    skip_copy_for = () # bw compat (< 3.14), use cw_skip_copy_for instead
    cw_skip_copy_for = [('in_state', 'subject')]
    # class attributes set automatically at registration time
    e_schema = None

    @classmethod
    def __initialize__(cls, schema):
        """initialize a specific entity class by adding descriptors to access
        entity type's attributes and relations
        """
        etype = cls.__regid__
        assert etype != 'Any', etype
        cls.e_schema = eschema = schema.eschema(etype)
        for rschema, _ in eschema.attribute_definitions():
            if rschema.type == 'eid':
                continue
            setattr(cls, rschema.type, Attribute(rschema.type))
        mixins = []
        for rschema, _, role in eschema.relation_definitions():
            if role == 'subject':
                attr = rschema.type
            else:
                attr = 'reverse_%s' % rschema.type
            setattr(cls, attr, Relation(rschema, role))

    fetch_attrs = ('modification_date',)

    @classmethod
    def cw_fetch_order(cls, select, attr, var):
        """This class method may be used to control sort order when multiple
        entities of this type are fetched through ORM methods. Its arguments
        are:

        * `select`, the RQL syntax tree

        * `attr`, the attribute being watched

        * `var`, the variable through which this attribute's value may be
          accessed in the query

        When you want to do some sorting on the given attribute, you should
        modify the syntax tree accordingly. For instance:

        .. sourcecode:: python

          from rql import nodes

          class Version(AnyEntity):
              __regid__ = 'Version'

              fetch_attrs = ('num', 'description', 'in_state')

              @classmethod
              def cw_fetch_order(cls, select, attr, var):
                  if attr == 'num':
                      func = nodes.Function('version_sort_value')
                      func.append(nodes.variable_ref(var))
                      sterm = nodes.SortTerm(func, asc=False)
                      select.add_sort_term(sterm)

        The default implementation call
        :meth:`~cubicweb.entity.Entity.cw_fetch_unrelated_order`
        """
        cls.cw_fetch_unrelated_order(select, attr, var)

    @classmethod
    def cw_fetch_unrelated_order(cls, select, attr, var):
        """This class method may be used to control sort order when multiple entities of
        this type are fetched to use in edition (e.g. propose them to create a
        new relation on an edited entity).

        See :meth:`~cubicweb.entity.Entity.cw_fetch_unrelated_order` for a
        description of its arguments and usage.

        By default entities will be listed on their modification date descending,
        i.e. you'll get entities recently modified first.
        """
        if attr == 'modification_date':
            select.add_sort_var(var, asc=False)

    @classmethod
    def fetch_rql(cls, user, restriction=None, fetchattrs=None, mainvar='X',
                  settype=True, ordermethod='fetch_order'):
        st = cls.fetch_rqlst(user, mainvar=mainvar, fetchattrs=fetchattrs,
                             settype=settype, ordermethod=ordermethod)
        rql = st.as_string()
        if restriction:
            # cannot use RQLRewriter API to insert 'X rtype %(x)s' restriction
            warn('[3.14] fetch_rql: use of `restriction` parameter is '
                 'deprecated, please use fetch_rqlst and supply a syntax'
                 'tree with your restriction instead', DeprecationWarning)
            insert = ' WHERE ' + ','.join(restriction)
            if ' WHERE ' in rql:
                select, where = rql.split(' WHERE ', 1)
                rql = select + insert + ',' + where
            else:
                rql += insert
        return rql

    @classmethod
    def fetch_rqlst(cls, user, select=None, mainvar='X', fetchattrs=None,
                    settype=True, ordermethod='fetch_order'):
        if select is None:
            select = Select()
            mainvar = select.get_variable(mainvar)
            select.add_selected(mainvar)
        elif isinstance(mainvar, string_types):
            assert mainvar in select.defined_vars
            mainvar = select.get_variable(mainvar)
        # eases string -> syntax tree test transition: please remove once stable
        select._varmaker = rqlvar_maker(defined=select.defined_vars,
                                        aliases=select.aliases, index=26)
        if settype:
            rel = select.add_type_restriction(mainvar, cls.__regid__)
            # should use 'is_instance_of' instead of 'is' so we retrieve
            # subclasses instances as well
            rel.r_type = 'is_instance_of'
        if fetchattrs is None:
            fetchattrs = cls.fetch_attrs
        cls._fetch_restrictions(mainvar, select, fetchattrs, user, ordermethod)
        return select

    @classmethod
    def _fetch_ambiguous_rtypes(cls, select, var, fetchattrs, subjtypes, schema):
        """find rtypes in `fetchattrs` that relate different subject etypes
        taken from (`subjtypes`) to different target etypes; these so called
        "ambiguous" relations, are added directly to the `select` syntax tree
        selection but removed from `fetchattrs` to avoid the fetch recursion
        because we have to choose only one targettype for the recursion and
        adding its own fetch attrs to the selection -when we recurse- would
        filter out the other possible target types from the result set
        """
        for attr in fetchattrs.copy():
            rschema = schema.rschema(attr)
            if rschema.final:
                continue
            ttypes = None
            for subjtype in subjtypes:
                cur_ttypes = set(rschema.objects(subjtype))
                if ttypes is None:
                    ttypes = cur_ttypes
                elif cur_ttypes != ttypes:
                    # we found an ambiguous relation: remove it from fetchattrs
                    fetchattrs.remove(attr)
                    # ... and add it to the selection
                    targetvar = select.make_variable()
                    select.add_selected(targetvar)
                    rel = make_relation(var, attr, (targetvar,), VariableRef)
                    select.add_restriction(rel)
                    break

    @classmethod
    def _fetch_restrictions(cls, mainvar, select, fetchattrs,
                            user, ordermethod='fetch_order', visited=None):
        eschema = cls.e_schema
        if visited is None:
            visited = set((eschema.type,))
        elif eschema.type in visited:
            # avoid infinite recursion
            return
        else:
            visited.add(eschema.type)
        for attr in sorted(fetchattrs):
            try:
                rschema = eschema.subjrels[attr]
            except KeyError:
                cls.warning('skipping fetch_attr %s defined in %s (not found in schema)',
                            attr, cls.__regid__)
                continue
            # XXX takefirst=True to remove warning triggered by ambiguous inlined relations
            rdef = eschema.rdef(attr, takefirst=True)
            if not user.matching_groups(rdef.get_groups('read')):
                continue
            if rschema.final or rdef.cardinality[0] in '?1':
                var = select.make_variable()
                select.add_selected(var)
                rel = make_relation(mainvar, attr, (var,), VariableRef)
                select.add_restriction(rel)
            else:
                cls.warning('bad relation %s specified in fetch attrs for %s',
                            attr, cls)
                continue
            if not rschema.final:
                # XXX we need outer join in case the relation is not mandatory
                # (card == '?')  *or if the entity is being added*, since in
                # that case the relation may still be missing. As we miss this
                # later information here, systematically add it.
                rel.change_optional('right')
                targettypes = rschema.objects(eschema.type)
                vreg = user._cw.vreg  # XXX user._cw.vreg iiiirk
                etypecls = vreg['etypes'].etype_class(targettypes[0])
                if len(targettypes) > 1:
                    # find fetch_attrs common to all destination types
                    fetchattrs = vreg['etypes'].fetch_attrs(targettypes)
                    # ... and handle ambiguous relations
                    cls._fetch_ambiguous_rtypes(select, var, fetchattrs,
                                                targettypes, vreg.schema)
                else:
                    fetchattrs = etypecls.fetch_attrs
                etypecls._fetch_restrictions(var, select, fetchattrs,
                                             user, None, visited=visited)
            if ordermethod is not None:
                try:
                    cmeth = getattr(cls, ordermethod)
                    warn('[3.14] %s %s class method should be renamed to cw_%s'
                         % (cls.__regid__, ordermethod, ordermethod),
                         DeprecationWarning)
                except AttributeError:
                    cmeth = getattr(cls, 'cw_' + ordermethod)
                if support_args(cmeth, 'select'):
                    cmeth(select, attr, var)
                else:
                    warn('[3.14] %s should now take (select, attr, var) and '
                         'modify the syntax tree when desired instead of '
                         'returning something' % cmeth, DeprecationWarning)
                    orderterm = cmeth(attr, var.name)
                    if orderterm is not None:
                        try:
                            var, order = orderterm.split()
                        except ValueError:
                            if '(' in orderterm:
                                cls.error('ignore %s until %s is upgraded',
                                          orderterm, cmeth)
                                orderterm = None
                            elif not ' ' in orderterm.strip():
                                var = orderterm
                                order = 'ASC'
                        if orderterm is not None:
                            select.add_sort_var(select.get_variable(var),
                                                order=='ASC')

    @classmethod
    @cached
    def cw_rest_attr_info(cls):
        """this class method return an attribute name to be used in URL for
        entities of this type and a boolean flag telling if its value should be
        checked for uniqness.

        The attribute returned is, in order of priority:

        * class's `rest_attr` class attribute
        * an attribute defined as unique in the class'schema
        * 'eid'
        """
        mainattr, needcheck = 'eid', True
        if cls.rest_attr:
            mainattr = cls.rest_attr
            needcheck = not cls.e_schema.has_unique_values(mainattr)
        else:
            for rschema in cls.e_schema.subject_relations():
                if (rschema.final
                    and rschema not in ('eid', 'cwuri')
                    and cls.e_schema.has_unique_values(rschema)
                    and cls.e_schema.rdef(rschema.type).cardinality[0] == '1'):
                    mainattr = str(rschema)
                    needcheck = False
                    break
        if mainattr == 'eid':
            needcheck = False
        return mainattr, needcheck

    @classmethod
    def _cw_build_entity_query(cls, kwargs):
        relations = []
        restrictions = set()
        pendingrels = []
        eschema = cls.e_schema
        qargs = {}
        attrcache = {}
        for attr, value in kwargs.items():
            if attr.startswith('reverse_'):
                attr = attr[len('reverse_'):]
                role = 'object'
            else:
                role = 'subject'
            assert eschema.has_relation(attr, role), '%s %s not found on %s' % (attr, role, eschema)
            rschema = eschema.subjrels[attr] if role == 'subject' else eschema.objrels[attr]
            if not rschema.final and isinstance(value, (tuple, list, set, frozenset)):
                if len(value) == 0:
                    continue # avoid crash with empty IN clause
                elif len(value) == 1:
                    value = next(iter(value))
                else:
                    # prepare IN clause
                    pendingrels.append( (attr, role, value) )
                    continue
            if rschema.final: # attribute
                relations.append('X %s %%(%s)s' % (attr, attr))
                attrcache[attr] = value
            elif value is None:
                pendingrels.append( (attr, role, value) )
            else:
                rvar = attr.upper()
                if role == 'object':
                    relations.append('%s %s X' % (rvar, attr))
                else:
                    relations.append('X %s %s' % (attr, rvar))
                restriction = '%s eid %%(%s)s' % (rvar, attr)
                if not restriction in restrictions:
                    restrictions.add(restriction)
                if hasattr(value, 'eid'):
                    value = value.eid
            qargs[attr] = value
        rql = u''
        if relations:
            rql += ', '.join(relations)
        if restrictions:
            rql += ' WHERE %s' % ', '.join(restrictions)
        return rql, qargs, pendingrels, attrcache

    @classmethod
    def _cw_handle_pending_relations(cls, eid, pendingrels, execute):
        for attr, role, values in pendingrels:
            if role == 'object':
                restr = 'Y %s X' % attr
            else:
                restr = 'X %s Y' % attr
            if values is None:
                execute('DELETE %s WHERE X eid %%(x)s' % restr, {'x': eid})
                continue
            execute('SET %s WHERE X eid %%(x)s, Y eid IN (%s)' % (
                restr, ','.join(str(getattr(r, 'eid', r)) for r in values)),
                    {'x': eid}, build_descr=False)

    @classmethod
    def cw_instantiate(cls, execute, **kwargs):
        """add a new entity of this given type

        Example (in a shell session):

        >>> companycls = vreg['etypes'].etype_class('Company')
        >>> personcls = vreg['etypes'].etype_class('Person')
        >>> c = companycls.cw_instantiate(session.execute, name=u'Logilab')
        >>> p = personcls.cw_instantiate(session.execute, firstname=u'John', lastname=u'Doe',
        ...                              works_for=c)

        You can also set relations where the entity has 'object' role by
        prefixing the relation name by 'reverse_'. Also, relation values may be
        an entity or eid, a list of entities or eids.
        """
        rql, qargs, pendingrels, attrcache = cls._cw_build_entity_query(kwargs)
        if rql:
            rql = 'INSERT %s X: %s' % (cls.__regid__, rql)
        else:
            rql = 'INSERT %s X' % (cls.__regid__)
        try:
            created = execute(rql, qargs).get_entity(0, 0)
        except IndexError:
            raise Exception('could not create a %r with %r (%r)' %
                            (cls.__regid__, rql, qargs))
        created._cw_update_attr_cache(attrcache)
        cls._cw_handle_pending_relations(created.eid, pendingrels, execute)
        return created

    def __init__(self, req, rset=None, row=None, col=0):
        AppObject.__init__(self, req, rset=rset, row=row, col=col)
        self._cw_related_cache = {}
        self._cw_adapters_cache = {}
        if rset is not None:
            self.eid = rset[row][col]
        else:
            self.eid = None
        self._cw_is_saved = True
        self.cw_attr_cache = {}

    def __repr__(self):
        return '<Entity %s %s %s at %s>' % (
            self.e_schema, self.eid, list(self.cw_attr_cache), id(self))

    def __lt__(self, other):
        return NotImplemented

    def __eq__(self, other):
        if isinstance(self.eid, integer_types):
            return self.eid == other.eid
        return self is other

    def __hash__(self):
        if isinstance(self.eid, integer_types):
            return self.eid
        return super(Entity, self).__hash__()

    def _cw_update_attr_cache(self, attrcache):
        trdata = self._cw.transaction_data
        uncached_attrs = trdata.get('%s.storage-special-process-attrs' % self.eid, set())
        uncached_attrs.update(trdata.get('%s.dont-cache-attrs' % self.eid, set()))
        for attr in uncached_attrs:
            attrcache.pop(attr, None)
            self.cw_attr_cache.pop(attr, None)
        self.cw_attr_cache.update(attrcache)

    def _cw_dont_cache_attribute(self, attr, repo_side=False):
        """Called when some attribute has been transformed by a *storage*,
        hence the original value should not be cached **by anyone**.

        For example we have a special "fs_importing" mode in BFSS
        where a file path is given as attribute value and stored as is
        in the data base. Later access to the attribute will provide
        the content of the file at the specified path. We do not want
        the "filepath" value to be cached.

        """
        trdata = self._cw.transaction_data
        trdata.setdefault('%s.dont-cache-attrs' % self.eid, set()).add(attr)
        if repo_side:
            trdata.setdefault('%s.storage-special-process-attrs' % self.eid, set()).add(attr)

    def __json_encode__(self):
        """custom json dumps hook to dump the entity's eid
        which is not part of dict structure itself
        """
        dumpable = self.cw_attr_cache.copy()
        dumpable['eid'] = self.eid
        return dumpable

    def cw_adapt_to(self, interface):
        """return an adapter the entity to the given interface name.

        return None if it can not be adapted.
        """
        cache = self._cw_adapters_cache
        try:
            return cache[interface]
        except KeyError:
            adapter = self._cw.vreg['adapters'].select_or_none(
                interface, self._cw, entity=self)
            cache[interface] = adapter
            return adapter

    def has_eid(self): # XXX cw_has_eid
        """return True if the entity has an attributed eid (False
        meaning that the entity has to be created
        """
        try:
            int(self.eid)
            return True
        except (ValueError, TypeError):
            return False

    def cw_is_saved(self):
        """during entity creation, there is some time during which the entity
        has an eid attributed though it's not saved (eg during
        'before_add_entity' hooks). You can use this method to ensure the entity
        has an eid *and* is saved in its source.
        """
        return self.has_eid() and self._cw_is_saved

    @deprecated('[3.24] cw_metainformation is deprecated')
    @cached
    def cw_metainformation(self):
        source = self.cw_source[0].name
        return {'type': self.cw_etype,
                'extid': self.cwuri if source != 'system' else None,
                'source': {'uri': source}}

    def cw_check_perm(self, action):
        self.e_schema.check_perm(self._cw, action, eid=self.eid)

    def cw_has_perm(self, action):
        return self.e_schema.has_perm(self._cw, action, eid=self.eid)

    def view(self, __vid, __registry='views', w=None, initargs=None, **kwargs): # XXX cw_view
        """shortcut to apply a view on this entity"""
        if initargs is None:
            initargs = kwargs
        else:
            initargs.update(kwargs)
        view = self._cw.vreg[__registry].select(__vid, self._cw, rset=self.cw_rset,
                                                row=self.cw_row, col=self.cw_col,
                                                **initargs)
        return view.render(row=self.cw_row, col=self.cw_col, w=w, **kwargs)

    def absolute_url(self, *args, **kwargs): # XXX cw_url
        """return an absolute url to view this entity"""
        # use *args since we don't want first argument to be "anonymous" to
        # avoid potential clash with kwargs
        if args:
            assert len(args) == 1, 'only 0 or 1 non-named-argument expected'
            method = args[0]
        else:
            method = None
        if method in (None, 'view'):
            kwargs['_restpath'] = self.rest_path()
        else:
            kwargs['rql'] = 'Any X WHERE X eid %s' % self.eid
        return self._cw.build_url(method, **kwargs)

    def rest_path(self, *args, **kwargs): # XXX cw_rest_path
        """returns a REST-like (relative) path for this entity"""
        if args or kwargs:
            warn("[3.24] rest_path doesn't take parameters anymore", DeprecationWarning)
        mainattr, needcheck = self.cw_rest_attr_info()
        etype = str(self.e_schema)
        path = etype.lower()
        fallback = False
        if mainattr != 'eid':
            value = getattr(self, mainattr)
            if not can_use_rest_path(value):
                mainattr = 'eid'
                path = None
            elif needcheck:
                # make sure url is not ambiguous
                try:
                    nbresults = self.__unique
                except AttributeError:
                    rql = 'Any COUNT(X) WHERE X is %s, X %s %%(value)s' % (
                        etype, mainattr)
                    nbresults = self.__unique = self._cw.execute(rql, {'value' : value})[0][0]
                if nbresults != 1: # ambiguity?
                    mainattr = 'eid'
                    path = None
        if mainattr == 'eid':
            value = self.eid
        if path is None:
            # fallback url: <base-url>/<eid> url is used as cw entities uri,
            # prefer it to <base-url>/<etype>/eid/<eid>
            return text_type(value)
        return u'%s/%s' % (path, self._cw.url_quote(value))

    def cw_attr_metadata(self, attr, metadata):
        """return a metadata for an attribute (None if unspecified)"""
        value = getattr(self, '%s_%s' % (attr, metadata), None)
        if value is None and metadata == 'encoding':
            value = self._cw.vreg.property_value('ui.encoding')
        return value

    def printable_value(self, attr, value=_marker, attrtype=None,
                        format='text/html', displaytime=True): # XXX cw_printable_value
        """return a displayable value (i.e. unicode string) which may contains
        html tags
        """
        attr = str(attr)
        if value is _marker:
            value = getattr(self, attr)
        if isinstance(value, string_types):
            value = value.strip()
        if value is None or value == '': # don't use "not", 0 is an acceptable value
            return u''
        if attrtype is None:
            attrtype = self.e_schema.destination(attr)
        props = self.e_schema.rdef(attr)
        if attrtype == 'String':
            # internalinalized *and* formatted string such as schema
            # description...
            if props.internationalizable:
                value = self._cw._(value)
            attrformat = self.cw_attr_metadata(attr, 'format')
            if attrformat:
                return self._cw_mtc_transform(value, attrformat, format,
                                              self._cw.encoding)
        elif attrtype == 'Bytes':
            attrformat = self.cw_attr_metadata(attr, 'format')
            if attrformat:
                encoding = self.cw_attr_metadata(attr, 'encoding')
                return self._cw_mtc_transform(value.getvalue(), attrformat, format,
                                              encoding)
            return u''
        value = self._cw.printable_value(attrtype, value, props,
                                         displaytime=displaytime)
        if format == 'text/html':
            value = xml_escape(value)
        return value

    def _cw_mtc_transform(self, data, format, target_format, encoding,
                          _engine=ENGINE):
        trdata = TransformData(data, format, encoding, appobject=self)
        data = _engine.convert(trdata, target_format).decode()
        if target_format == 'text/html':
            data = soup2xhtml(data, self._cw.encoding)
        return data

    # entity cloning ##########################################################

    def copy_relations(self, ceid): # XXX cw_copy_relations
        """copy relations of the object with the given eid on this
        object (this method is called on the newly created copy, and
        ceid designates the original entity).

        By default meta and composite relations are skipped.
        Overrides this if you want another behaviour
        """
        assert self.has_eid()
        execute = self._cw.execute
        skip_copy_for = {'subject': set(), 'object': set()}
        for rtype in self.skip_copy_for:
            skip_copy_for['subject'].add(rtype)
            warn('[3.14] skip_copy_for on entity classes (%s) is deprecated, '
                 'use cw_skip_copy_for instead with list of couples (rtype, role)' % self.cw_etype,
                 DeprecationWarning)
        for rtype, role in self.cw_skip_copy_for:
            assert role in ('subject', 'object'), role
            skip_copy_for[role].add(rtype)
        for rschema in self.e_schema.subject_relations():
            if rschema.type in skip_copy_for['subject']:
                continue
            if rschema.final or rschema.meta or rschema.rule:
                continue
            # skip already defined relations
            if getattr(self, rschema.type):
                continue
            # XXX takefirst=True to remove warning triggered by ambiguous relations
            rdef = self.e_schema.rdef(rschema, takefirst=True)
            # skip composite relation
            if rdef.composite:
                continue
            # skip relation with card in ?1 else we either change the copied
            # object (inlined relation) or inserting some inconsistency
            if rdef.cardinality[1] in '?1':
                continue
            rql = 'SET X %s V WHERE X eid %%(x)s, Y eid %%(y)s, Y %s V' % (
                rschema.type, rschema.type)
            execute(rql, {'x': self.eid, 'y': ceid})
            self.cw_clear_relation_cache(rschema.type, 'subject')
        for rschema in self.e_schema.object_relations():
            if rschema.meta or rschema.rule:
                continue
            # skip already defined relations
            if self.related(rschema.type, 'object'):
                continue
            if rschema.type in skip_copy_for['object']:
                continue
            # XXX takefirst=True to remove warning triggered by ambiguous relations
            rdef = self.e_schema.rdef(rschema, 'object', takefirst=True)
            # skip composite relation
            if rdef.composite:
                continue
            # skip relation with card in ?1 else we either change the copied
            # object (inlined relation) or inserting some inconsistency
            if rdef.cardinality[0] in '?1':
                continue
            rql = 'SET V %s X WHERE X eid %%(x)s, Y eid %%(y)s, V %s Y' % (
                rschema.type, rschema.type)
            execute(rql, {'x': self.eid, 'y': ceid})
            self.cw_clear_relation_cache(rschema.type, 'object')

    # data fetching methods ###################################################

    @cached
    def as_rset(self): # XXX .cw_as_rset
        """returns a resultset containing `self` information"""
        rset = ResultSet([(self.eid,)], 'Any X WHERE X eid %(x)s',
                         {'x': self.eid}, [(self.cw_etype,)])
        rset.req = self._cw
        return rset

    def _cw_to_complete_relations(self):
        """by default complete final relations to when calling .complete()"""
        for rschema in self.e_schema.subject_relations():
            if rschema.final:
                continue
            targets = rschema.objects(self.e_schema)
            if rschema.inlined:
                matching_groups = self._cw.user.matching_groups
                if all(matching_groups(e.get_groups('read')) and
                       rschema.rdef(self.e_schema, e).get_groups('read')
                       for e in targets):
                    yield rschema, 'subject'

    def _cw_to_complete_attributes(self, skip_bytes=True, skip_pwd=True):
        for rschema, attrschema in self.e_schema.attribute_definitions():
            # skip binary data by default
            if skip_bytes and attrschema.type == 'Bytes':
                continue
            attr = rschema.type
            if attr == 'eid':
                continue
            # password retrieval is blocked at the repository server level
            rdef = rschema.rdef(self.e_schema, attrschema)
            if not self._cw.user.matching_groups(rdef.get_groups('read')) \
                   or (attrschema.type == 'Password' and skip_pwd):
                self.cw_attr_cache[attr] = None
                continue
            yield attr

    _cw_completed = False
    def complete(self, attributes=None, skip_bytes=True, skip_pwd=True): # XXX cw_complete
        """complete this entity by adding missing attributes (i.e. query the
        repository to fill the entity)

        :type skip_bytes: bool
        :param skip_bytes:
          if true, attribute of type Bytes won't be considered
        """
        assert self.has_eid()
        if self._cw_completed:
            return
        if attributes is None:
            self._cw_completed = True
        varmaker = rqlvar_maker()
        V = next(varmaker)
        rql = ['WHERE %s eid %%(x)s' % V]
        selected = []
        for attr in (attributes or self._cw_to_complete_attributes(skip_bytes, skip_pwd)):
            # if attribute already in entity, nothing to do
            if attr in self.cw_attr_cache:
                continue
            # case where attribute must be completed, but is not yet in entity
            var = next(varmaker)
            rql.append('%s %s %s' % (V, attr, var))
            selected.append((attr, var))
        # +1 since this doesn't include the main variable
        lastattr = len(selected) + 1
        if attributes is None:
            # fetch additional relations (restricted to 0..1 relations)
            for rschema, role in self._cw_to_complete_relations():
                rtype = rschema.type
                if self.cw_relation_cached(rtype, role):
                    continue
                # at this point we suppose that:
                # * this is a inlined relation
                # * entity (self) is the subject
                # * user has read perm on the relation and on the target entity
                assert rschema.inlined
                assert role == 'subject'
                var = next(varmaker)
                # keep outer join anyway, we don't want .complete to crash on
                # missing mandatory relation (see #1058267)
                rql.append('%s %s %s?' % (V, rtype, var))
                selected.append(((rtype, role), var))
        if selected:
            # select V, we need it as the left most selected variable
            # if some outer join are included to fetch inlined relations
            rql = 'Any %s,%s %s' % (V, ','.join(var for attr, var in selected),
                                    ','.join(rql))
            try:
                rset = self._cw.execute(rql, {'x': self.eid}, build_descr=False)[0]
            except IndexError:
                raise Exception('unable to fetch attributes for entity with eid %s'
                                % self.eid)
            # handle attributes
            for i in range(1, lastattr):
                self.cw_attr_cache[str(selected[i-1][0])] = rset[i]
            # handle relations
            for i in range(lastattr, len(rset)):
                rtype, role = selected[i-1][0]
                value = rset[i]
                if value is None:
                    rrset = ResultSet([], rql, {'x': self.eid})
                    rrset.req = self._cw
                else:
                    rrset = self._cw.eid_rset(value)
                self.cw_set_relation_cache(rtype, role, rrset)

    def cw_attr_value(self, name):
        """get value for the attribute relation <name>, query the repository
        to get the value if necessary.

        :type name: str
        :param name: name of the attribute to get
        """
        try:
            return self.cw_attr_cache[name]
        except KeyError:
            if not self.cw_is_saved():
                return None
            rql = "Any A WHERE X eid %%(x)s, X %s A" % name
            try:
                rset = self._cw.execute(rql, {'x': self.eid})
            except Unauthorized:
                self.cw_attr_cache[name] = value = None
            else:
                assert rset.rowcount <= 1, (self, rql, rset.rowcount)
                try:
                    self.cw_attr_cache[name] = value = rset.rows[0][0]
                except IndexError:
                    # probably a multisource error
                    self.critical("can't get value for attribute %s of entity with eid %s",
                                  name, self.eid)
                    if self.e_schema.destination(name) == 'String':
                        self.cw_attr_cache[name] = value = self._cw._('unaccessible')
                    else:
                        self.cw_attr_cache[name] = value = None
            return value

    def related(self, rtype, role='subject', limit=None, entities=False, # XXX .cw_related
                safe=False, targettypes=None):
        """returns a resultset of related entities

        :param rtype:
          the name of the relation, aka relation type
        :param role:
          the role played by 'self' in the relation ('subject' or 'object')
        :param limit:
          resultset's maximum size
        :param entities:
          if True, the entites are returned; if False, a result set is returned
        :param safe:
          if True, an empty rset/list of entities will be returned in case of
          :exc:`Unauthorized`, else (the default), the exception is propagated
        :param targettypes:
          a tuple of target entity types to restrict the query
        """
        rtype = str(rtype)
        # Caching restricted/limited results is best avoided.
        cacheable = limit is None and targettypes is None
        if cacheable:
            cache_key = '%s_%s' % (rtype, role)
            if cache_key in self._cw_related_cache:
                return self._cw_related_cache[cache_key][entities]
        if not self.has_eid():
            if entities:
                return []
            return self._cw.empty_rset()
        rql = self.cw_related_rql(rtype, role, limit=limit, targettypes=targettypes)
        try:
            rset = self._cw.execute(rql, {'x': self.eid})
        except Unauthorized:
            if not safe:
                raise
            rset = self._cw.empty_rset()
        if cacheable:
            self.cw_set_relation_cache(rtype, role, rset)
        if entities:
            return tuple(rset.entities())
        else:
            return rset

    def cw_related_rql(self, rtype, role='subject', targettypes=None, limit=None):
        return self.cw_related_rqlst(
            rtype, role=role, targettypes=targettypes, limit=limit).as_string()

    def cw_related_rqlst(self, rtype, role='subject', targettypes=None,
                         limit=None, sort_terms=None):
        """Return the select node of the RQL query of entities related through
        `rtype` with this entity as `role`, possibly filtered by
        `targettypes`.

        The RQL query can be given a `limit` and sort terms with `sort_terms`
        arguments being a sequence of ``(<relation type>, <sort ascending>)``
        (e.g. ``[('name', True), ('modification_date', False)]`` would lead to
        a sorting by ``name``, ascending and then by ``modification_date``,
        descending. If `sort_terms` is not specified the default sorting is by
        ``modification_date``, descending.
        """
        vreg = self._cw.vreg
        rschema = vreg.schema[rtype]
        select = Select()
        mainvar, evar = select.get_variable('X'), select.get_variable('E')
        select.add_selected(mainvar)
        if limit is not None:
            select.set_limit(limit)
        select.add_eid_restriction(evar, 'x', 'Substitute')
        if role == 'subject':
            rel = make_relation(evar, rtype, (mainvar,), VariableRef)
            select.add_restriction(rel)
            if targettypes is None:
                targettypes = rschema.objects(self.e_schema)
            else:
                select.add_constant_restriction(mainvar, 'is',
                                                targettypes, 'etype')
            gcard = greater_card(rschema, (self.e_schema,), targettypes, 0)
        else:
            rel = make_relation(mainvar, rtype, (evar,), VariableRef)
            select.add_restriction(rel)
            if targettypes is None:
                targettypes = rschema.subjects(self.e_schema)
            else:
                select.add_constant_restriction(mainvar, 'is', targettypes,
                                                'etype')
            gcard = greater_card(rschema, targettypes, (self.e_schema,), 1)
        etypecls = vreg['etypes'].etype_class(targettypes[0])
        if len(targettypes) > 1:
            fetchattrs = vreg['etypes'].fetch_attrs(targettypes)
            self._fetch_ambiguous_rtypes(select, mainvar, fetchattrs,
                                         targettypes, vreg.schema)
        else:
            fetchattrs = etypecls.fetch_attrs
        etypecls.fetch_rqlst(self._cw.user, select, mainvar, fetchattrs,
                             settype=False)
        # optimisation: remove ORDERBY if cardinality is 1 or ? (though
        # greater_card return 1 for those both cases)
        if gcard == '1':
            select.remove_sort_terms()
        elif not select.orderby:
            # Build a mapping (rtype, node) for relations usable for sorting.
            sorting_relations = {}
            for r in select.where.get_nodes(RqlRelation):
                lhs, rhs = r.children
                if lhs.variable != mainvar:
                    continue
                if r.operator() != '=':
                    continue
                rhs_term = rhs.children[0]
                if not isinstance(rhs_term, VariableRef):
                    continue
                sorting_relations[r.r_type] = r
            sort_terms = sort_terms or [('modification_date', False)]
            for term, order in sort_terms:
                # Add a relation for sorting only if it is not only retrieved
                # (e.g. modification_date) instead of adding another variable
                # for sorting. This should not be problematic, but it is with
                # sqlserver, see ticket #694445.
                rel = sorting_relations.get(term)
                if rel is None:
                    mdvar = select.make_variable()
                    rel = make_relation(mainvar, term, (mdvar,), VariableRef)
                    select.add_restriction(rel)
                var = rel.children[1].children[0].variable
                select.add_sort_var(var, asc=order)
        return select

    # generic vocabulary methods ##############################################

    def cw_linkable_rql(self, rtype, targettype, role, ordermethod=None,
                        vocabconstraints=True, lt_infos={}, limit=None):
        """build a rql to fetch targettype entities either related or unrelated
        to this entity using (rtype, role) relation.

        Consider relation permissions so that returned entities may be actually
        linked by `rtype`.

        `lt_infos` are supplementary informations, usually coming from __linkto
        parameter, that can help further restricting the results in case current
        entity is not yet created. It is a dict describing entities the current
        entity will be linked to, which keys are (rtype, role) tuples and values
        are a list of eids.
        """
        return self._cw_compute_linkable_rql(rtype, targettype, role, ordermethod=None,
                                             vocabconstraints=vocabconstraints,
                                             lt_infos=lt_infos, limit=limit,
                                             unrelated_only=False)

    def cw_unrelated_rql(self, rtype, targettype, role, ordermethod=None,
                         vocabconstraints=True, lt_infos={}, limit=None):
        """build a rql to fetch `targettype` entities unrelated to this entity
        using (rtype, role) relation.

        Consider relation permissions so that returned entities may be actually
        linked by `rtype`.

        `lt_infos` are supplementary informations, usually coming from __linkto
        parameter, that can help further restricting the results in case current
        entity is not yet created. It is a dict describing entities the current
        entity will be linked to, which keys are (rtype, role) tuples and values
        are a list of eids.
        """
        return self._cw_compute_linkable_rql(rtype, targettype, role, ordermethod=None,
                                             vocabconstraints=vocabconstraints,
                                             lt_infos=lt_infos, limit=limit,
                                             unrelated_only=True)

    def _cw_compute_linkable_rql(self, rtype, targettype, role, ordermethod=None,
                                 vocabconstraints=True, lt_infos={}, limit=None,
                                 unrelated_only=False):
        """build a rql to fetch `targettype` entities that may be related to
        this entity using the (rtype, role) relation.

        By default (unrelated_only=False), this includes the already linked
        entities as well as the unrelated ones. If `unrelated_only` is True, the
        rql filters out the already related entities.
        """
        ordermethod = ordermethod or 'fetch_unrelated_order'
        rschema = self._cw.vreg.schema.rschema(rtype)
        rdef = rschema.role_rdef(self.e_schema, targettype, role)
        rewriter = RQLRewriter(self._cw)
        select = Select()
        # initialize some variables according to the `role` of `self` in the
        # relation (variable names must respect constraints conventions):
        # * variable for myself (`evar`)
        # * variable for searched entities (`searchvedvar`)
        if role == 'subject':
            evar = subjvar = select.get_variable('S')
            searchedvar = objvar = select.get_variable('O')
        else:
            searchedvar = subjvar = select.get_variable('S')
            evar = objvar = select.get_variable('O')
        select.add_selected(searchedvar)
        if limit is not None:
            select.set_limit(limit)
        # initialize some variables according to `self` existence
        if rdef.role_cardinality(neg_role(role)) in '?1':
            # if cardinality in '1?', we want a target entity which isn't
            # already linked using this relation
            variable = select.make_variable()
            if role == 'subject':
                rel = make_relation(variable, rtype, (searchedvar,), VariableRef)
            else:
                rel = make_relation(searchedvar, rtype, (variable,), VariableRef)
            select.add_restriction(Not(rel))
        elif self.has_eid() and unrelated_only:
            # elif we have an eid, we don't want a target entity which is
            # already linked to ourself through this relation
            rel = make_relation(subjvar, rtype, (objvar,), VariableRef)
            select.add_restriction(Not(rel))
        if self.has_eid():
            rel = make_relation(evar, 'eid', ('x', 'Substitute'), Constant)
            select.add_restriction(rel)
            args = {'x': self.eid}
            if role == 'subject':
                sec_check_args = {'fromeid': self.eid}
            else:
                sec_check_args = {'toeid': self.eid}
            existant = None # instead of 'SO', improve perfs
        else:
            args = {}
            sec_check_args = {}
            existant = searchedvar.name
            # undefine unused evar, or the type resolver will consider it
            select.undefine_variable(evar)
        # retrieve entity class for targettype to compute base rql
        etypecls = self._cw.vreg['etypes'].etype_class(targettype)
        etypecls.fetch_rqlst(self._cw.user, select, searchedvar,
                             ordermethod=ordermethod)
        # from now on, we need variable type resolving
        self._cw.vreg.solutions(self._cw, select, args)
        # insert RQL expressions for schema constraints into the rql syntax tree
        if vocabconstraints:
            cstrcls = (RQLVocabularyConstraint, RQLConstraint)
        else:
            cstrcls = RQLConstraint
        lt_infos = pruned_lt_info(self.e_schema, lt_infos or {})
        # if there are still lt_infos, use set to keep track of added eid
        # relations (adding twice the same eid relation is incorrect RQL)
        eidvars = set()
        for cstr in rdef.constraints:
            # consider constraint.mainvars to check if constraint apply
            if isinstance(cstr, cstrcls) and searchedvar.name in cstr.mainvars:
                if not self.has_eid():
                    if lt_infos:
                        # we can perhaps further restrict with linkto infos using
                        # a custom constraint built from cstr and lt_infos
                        cstr = build_cstr_with_linkto_infos(
                            cstr, args, searchedvar, evar, lt_infos, eidvars)
                        if cstr is None:
                            continue # could not build constraint -> discard
                    elif evar.name in cstr.mainvars:
                        continue
                # compute a varmap suitable to RQLRewriter.rewrite argument
                varmap = dict((v, v) for v in (searchedvar.name, evar.name)
                              if v in select.defined_vars and v in cstr.mainvars)
                # rewrite constraint by constraint since we want a AND between
                # expressions.
                rewriter.rewrite(select, [(varmap, (cstr,))], args, existant)
        # insert security RQL expressions granting the permission to 'add' the
        # relation into the rql syntax tree, if necessary
        rqlexprs = rdef.get_rqlexprs('add')
        if not self.has_eid():
            rqlexprs = [rqlexpr for rqlexpr in rqlexprs
                        if searchedvar.name in rqlexpr.mainvars]
        if rqlexprs and not rdef.has_perm(self._cw, 'add', **sec_check_args):
            # compute a varmap suitable to RQLRewriter.rewrite argument
            varmap = dict((v, v) for v in (searchedvar.name, evar.name)
                          if v in select.defined_vars)
            # rewrite all expressions at once since we want a OR between them.
            rewriter.rewrite(select, [(varmap, rqlexprs)], args, existant)
        # ensure we have an order defined
        if not select.orderby:
            select.add_sort_var(select.defined_vars[searchedvar.name])
        # we're done, turn the rql syntax tree as a string
        rql = select.as_string()
        return rql, args

    def unrelated(self, rtype, targettype, role='subject', limit=None,
                  ordermethod=None, lt_infos={}): # XXX .cw_unrelated
        """return a result set of target type objects that may be related
        by a given relation, with self as subject or object
        """
        try:
            rql, args = self.cw_unrelated_rql(rtype, targettype, role, limit=limit,
                                              ordermethod=ordermethod, lt_infos=lt_infos)
        except Unauthorized:
            return self._cw.empty_rset()
        return self._cw.execute(rql, args)

    # relations cache handling #################################################

    def cw_relation_cached(self, rtype, role):
        """return None if the given relation isn't already cached on the
        instance, else the content of the cache (a 2-uple (rset, entities)).
        """
        return self._cw_related_cache.get('%s_%s' % (rtype, role))

    def cw_set_relation_cache(self, rtype, role, rset):
        """set cached values for the given relation"""
        if rset:
            related = tuple(rset.entities(0))
            rschema = self._cw.vreg.schema.rschema(rtype)
            if role == 'subject':
                rcard = rschema.rdef(self.e_schema, related[0].e_schema).cardinality[1]
                target = 'object'
            else:
                rcard = rschema.rdef(related[0].e_schema, self.e_schema).cardinality[0]
                target = 'subject'
            if rcard in '?1':
                for rentity in related:
                    rentity._cw_related_cache['%s_%s' % (rtype, target)] = (
                        self.as_rset(), (self,))
        else:
            related = ()
        self._cw_related_cache['%s_%s' % (rtype, role)] = (rset, related)

    def cw_clear_relation_cache(self, rtype=None, role=None):
        """clear cached values for the given relation or the entire cache if
        no relation is given
        """
        if rtype is None:
            self._cw_related_cache.clear()
            self._cw_adapters_cache.clear()
        else:
            assert role
            self._cw_related_cache.pop('%s_%s' % (rtype, role), None)

    def cw_clear_all_caches(self):
        """flush all caches on this entity. Further attributes/relations access
        will triggers new database queries to get back values.

        If you use custom caches on your entity class (take care to @cached!),
        you should override this method to clear them as well.
        """
        # clear attributes cache
        self._cw_completed = False
        self.cw_attr_cache.clear()
        # clear relations cache
        self.cw_clear_relation_cache()
        # rest path unique cache
        try:
            del self.__unique
        except AttributeError:
            pass

    # raw edition utilities ###################################################

    def cw_set(self, **kwargs):
        """update this entity using given attributes / relation, working in the
        same fashion as :meth:`cw_instantiate`.

        Example (in a shell session):

        >>> c = rql('Any X WHERE X is Company').get_entity(0, 0)
        >>> p = rql('Any X WHERE X is Person').get_entity(0, 0)
        >>> c.cw_set(name=u'Logilab')
        >>> p.cw_set(firstname=u'John', lastname=u'Doe', works_for=c)

        You can also set relations where the entity has 'object' role by
        prefixing the relation name by 'reverse_'.  Also, relation values may be
        an entity or eid, a list of entities or eids, or None (meaning that all
        relations of the given type from or to this object should be deleted).
        """
        assert kwargs
        assert self.cw_is_saved(), "should not call set_attributes while entity "\
               "hasn't been saved yet"
        rql, qargs, pendingrels, attrcache = self._cw_build_entity_query(kwargs)
        if rql:
            rql = 'SET ' + rql
            qargs['x'] = self.eid
            if ' WHERE ' in rql:
                rql += ', X eid %(x)s'
            else:
                rql += ' WHERE X eid %(x)s'
            self._cw.execute(rql, qargs)
        # update current local object _after_ the rql query to avoid
        # interferences between the query execution itself and the cw_edited /
        # skip_security machinery
        self._cw_update_attr_cache(attrcache)
        self._cw_handle_pending_relations(self.eid, pendingrels, self._cw.execute)
        # XXX update relation cache

    def cw_delete(self, **kwargs):
        assert self.has_eid(), self.eid
        self._cw.execute('DELETE %s X WHERE X eid %%(x)s' % self.e_schema,
                         {'x': self.eid}, **kwargs)

    # server side utilities ####################################################

    def _cw_clear_local_perm_cache(self, action):
        for rqlexpr in self.e_schema.get_rqlexprs(action):
            self._cw.local_perm_cache.pop((rqlexpr.eid, (('x', self.eid),)), None)

    # deprecated stuff #########################################################

    @deprecated('[3.16] use cw_set() instead of set_attributes()')
    def set_attributes(self, **kwargs): # XXX cw_set_attributes
        if kwargs:
            self.cw_set(**kwargs)

    @deprecated('[3.16] use cw_set() instead of set_relations()')
    def set_relations(self, **kwargs): # XXX cw_set_relations
        """add relations to the given object. To set a relation where this entity
        is the object of the relation, use 'reverse_'<relation> as argument name.

        Values may be an entity or eid, a list of entities or eids, or None
        (meaning that all relations of the given type from or to this object
        should be deleted).
        """
        if kwargs:
            self.cw_set(**kwargs)

    @deprecated('[3.13] use entity.cw_clear_all_caches()')
    def clear_all_caches(self):
        return self.cw_clear_all_caches()


# attribute and relation descriptors ##########################################

class Attribute(object):
    """descriptor that controls schema attribute access"""

    def __init__(self, attrname):
        assert attrname != 'eid'
        self._attrname = attrname

    def __get__(self, eobj, eclass):
        if eobj is None:
            return self
        return eobj.cw_attr_value(self._attrname)

    @deprecated('[3.10] assign to entity.cw_attr_cache[attr] or entity.cw_edited[attr]')
    def __set__(self, eobj, value):
        if hasattr(eobj, 'cw_edited') and not eobj.cw_edited.saved:
            eobj.cw_edited[self._attrname] = value
        else:
            eobj.cw_attr_cache[self._attrname] = value


class Relation(object):
    """descriptor that controls schema relation access"""

    def __init__(self, rschema, role):
        self._rtype = rschema.type
        self._role = role

    def __get__(self, eobj, eclass):
        if eobj is None:
            raise AttributeError('%s can only be accessed from instances'
                                 % self._rtype)
        return eobj.related(self._rtype, self._role, entities=True)

    def __set__(self, eobj, value):
        raise NotImplementedError


from logging import getLogger
from cubicweb import set_log_methods
set_log_methods(Entity, getLogger('cubicweb.entity'))
