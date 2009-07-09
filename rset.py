"""The `ResultSet` class which is returned as result of a rql query

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

from logilab.common.decorators import cached, clear_cache, copy_cache

from rql import nodes

from cubicweb import NotAnEntity


class ResultSet(object):
    """a result set wrap a RQL query result. This object implements a partial
    list protocol to allow direct use as a list of result rows.

    :type rowcount: int
    :ivar rowcount: number of rows in the result

    :type rows: list
    :ivar rows: list of rows of result

    :type description: list
    :ivar description:
      result's description, using the same structure as the result itself

    :type rql: str or unicode
    :ivar rql: the original RQL query string
    """
    def __init__(self, results, rql, args=None, description=(), cachekey=None,
                 rqlst=None):
        self.rows = results
        self.rowcount = results and len(results) or 0
        # original query and arguments
        self.rql = rql
        self.args = args
        self.cachekey = cachekey
        # entity types for each cell (same shape as rows)
        # maybe discarded if specified when the query has been executed
        self.description = description
        # parsed syntax tree
        if rqlst is not None:
            rqlst.schema = None # reset schema in case of pyro transfert
        self._rqlst = rqlst
        # set to (limit, offset) when a result set is limited using the
        # .limit method
        self.limited = None
        # set by the cursor which returned this resultset
        self.vreg = None
        self.req = None
        # actions cache
        self._rsetactions = None

    def __str__(self):
        if not self.rows:
            return '<empty resultset %s>' % self.rql
        return '<resultset %s (%s rows)>' % (self.rql, len(self.rows))

    def __repr__(self):
        if not self.rows:
            return '<empty resultset for %r>' % self.rql
        rows = self.rows
        if len(rows) > 10:
            rows = rows[:10] + ['...']
        if not self.description:
            return '<resultset %r (%s rows): %s>' % (self.rql, len(self.rows),
                                                     '\n'.join(str(r) for r in rows))
        return '<resultset %r (%s rows): %s>' % (self.rql, len(self.rows),
                                                 '\n'.join('%s (%s)' % (r, d)
                                                           for r, d in zip(rows, self.description)))

    def possible_actions(self, **kwargs):
        if self._rsetactions is None:
            self._rsetactions = {}
        if kwargs:
            key = tuple(sorted(kwargs.iteritems()))
        else:
            key = None
        try:
            return self._rsetactions[key]
        except KeyError:
            actions = self.vreg.possible_vobjects('actions', self.req, self, **kwargs)
            self._rsetactions[key] = actions
            return actions

    def __len__(self):
        """returns the result set's size"""
        return self.rowcount

    def __nonzero__(self):
        return self.rowcount

    def __getitem__(self, i):
        """returns the ith element of the result set"""
        return self.rows[i] #ResultSetRow(self.rows[i])

    def __getslice__(self, i, j):
        """returns slice [i:j] of the result set"""
        return self.rows[i:j]

    def __iter__(self):
        """Returns an iterator over rows"""
        return iter(self.rows)

    def __add__(self, rset):
        # XXX buggy implementation (.rql and .args attributes at least much
        # probably differ)
        # at least rql could be fixed now that we have union and sub-queries
        # but I tend to think that since we have that, we should not need this
        # method anymore (syt)
        rset = ResultSet(self.rows+rset.rows, self.rql, self.args,
                         self.description +rset.description)
        return self.req.decorate_rset(rset)

    def _prepare_copy(self, rows, descr):
        rset = ResultSet(rows, self.rql, self.args, descr)
        return self.req.decorate_rset(rset)

    def transformed_rset(self, transformcb):
        """ the result set according to a given column types

        :type transormcb: callable(row, desc)
        :param transformcb:
          a callable which should take a row and its type description as
          parameters, and return the transformed row and type description.


        :type col: int
        :param col: the column index

        :rtype: `ResultSet`
        """
        rows, descr = [], []
        rset = self._prepare_copy(rows, descr)
        for row, desc in zip(self.rows, self.description):
            nrow, ndesc = transformcb(row, desc)
            if ndesc: # transformcb returns None for ndesc to skip that row
                rows.append(nrow)
                descr.append(ndesc)
        rset.rowcount = len(rows)
        return rset

    def filtered_rset(self, filtercb, col=0):
        """filter the result set according to a given filtercb

        :type filtercb: callable(entity)
        :param filtercb:
          a callable which should take an entity as argument and return
          False if it should be skipped, else True

        :type col: int
        :param col: the column index

        :rtype: `ResultSet`
        """
        rows, descr = [], []
        rset = self._prepare_copy(rows, descr)
        for i in xrange(len(self)):
            if not filtercb(self.get_entity(i, col)):
                continue
            rows.append(self.rows[i])
            descr.append(self.description[i])
        rset.rowcount = len(rows)
        return rset


    def sorted_rset(self, keyfunc, reverse=False, col=0):
        """sorts the result set according to a given keyfunc

        :type keyfunc: callable(entity)
        :param keyfunc:
          a callable which should take an entity as argument and return
          the value used to compare and sort

        :type reverse: bool
        :param reverse: if the result should be reversed

        :type col: int
        :param col: the column index. if col = -1, the whole row are used

        :rtype: `ResultSet`
        """
        rows, descr = [], []
        rset = self._prepare_copy(rows, descr)
        if col >= 0:
            entities = sorted(enumerate(self.entities(col)),
                              key=lambda (i, e): keyfunc(e), reverse=reverse)
        else:
            entities = sorted(enumerate(self),
                              key=lambda (i, e): keyfunc(e), reverse=reverse)
        for index, _ in entities:
            rows.append(self.rows[index])
            descr.append(self.description[index])
        rset.rowcount = len(rows)
        return rset

    def split_rset(self, keyfunc=None, col=0, return_dict=False):
        """Splits the result set in multiple result set according to a given key

        :type keyfunc: callable(entity or FinalType)
        :param keyfunc:
          a callable which should take a value of the rset in argument and
          return the value used to group the value. If not define, raw value
          of the specified columns is used.

        :type col: int
        :param col: the column index. if col = -1, the whole row are used

        :type return_dict: Boolean
        :param return_dict: If true, the function return a mapping
            (key -> rset) instead of a list of rset

        :rtype: List of `ResultSet` or mapping of  `ResultSet`

        """
        result = []
        mapping = {}
        for idx, line in enumerate(self):
            if col >= 0:
                try:
                    key = self.get_entity(idx, col)
                except NotAnEntity:
                    key = line[col]
            else:
                key = line
            if keyfunc is not None:
                key = keyfunc(key)

            if key not in mapping:
                rows, descr = [], []
                rset = self._prepare_copy(rows, descr)
                mapping[key] = rset
                result.append(rset)
            else:
                rset = mapping[key]
            rset.rows.append(self.rows[idx])
            rset.description.append(self.description[idx])


        for rset in result:
            rset.rowcount = len(rset.rows)
        if return_dict:
            return mapping
        else:
            return result

    def limit(self, limit, offset=0, inplace=False):
        """limit the result set to the given number of rows optionaly starting
        from an index different than 0

        :type limit: int
        :param limit: the maximum number of results

        :type offset: int
        :param offset: the offset index

        :type inplace: bool
        :param inplace:
          if true, the result set is modified in place, else a new result set
          is returned and the original is left unmodified

        :rtype: `ResultSet`
        """
        stop = limit+offset
        rows = self.rows[offset:stop]
        descr = self.description[offset:stop]
        if inplace:
            rset = self
            rset.rows, rset.description = rows, descr
            rset.rowcount = len(rows)
            clear_cache(rset, 'description_struct')
            if offset:
                clear_cache(rset, 'get_entity')
            # we also have to fix/remove from the request entity cache entities
            # which get a wrong rset reference by this limit call
            for entity in self.req.cached_entities():
                if entity.rset is self:
                    if offset <= entity.row < stop:
                        entity.row = entity.row - offset
                    else:
                        self.req.drop_entity_cache(entity.eid)
        else:
            rset = self._prepare_copy(rows, descr)
            if not offset:
                # can copy built entity caches
                copy_cache(rset, 'get_entity', self)
        rset.limited = (limit, offset)
        return rset

    def printable_rql(self, encoded=False):
        """return the result set's origin rql as a string, with arguments
        substitued
        """
        encoding = self.req.encoding
        rqlstr = self.syntax_tree().as_string(encoding, self.args)
        # sounds like we get encoded or unicode string due to a bug in as_string
        if not encoded:
            if isinstance(rqlstr, unicode):
                return rqlstr
            return unicode(rqlstr, encoding)
        else:
            if isinstance(rqlstr, unicode):
                return rqlstr.encode(encoding)
            return rqlstr

    # client helper methods ###################################################

    def entities(self, col=0):
        """iter on entities with eid in the `col` column of the result set"""
        for i in xrange(len(self)):
            # may have None values in case of outer join (or aggregat on eid
            # hacks)
            if self.rows[i][col] is not None:
                yield self.get_entity(i, col)

    @cached
    def get_entity(self, row, col=None):
        """special method for query retreiving a single entity, returns a
        partially initialized Entity instance.

        WARNING: due to the cache wrapping this function, you should NEVER
                 give row as a named parameter (i.e. rset.get_entity(req, 0)
                 is OK but rset.get_entity(row=0, req=req) isn't

        :type row,col: int, int
        :param row,col:
          row and col numbers localizing the entity among the result's table

        :return: the partially initialized `Entity` instance
        """
        if col is None:
            from warnings import warn
            msg = 'col parameter will become mandatory in future version'
            warn(msg, DeprecationWarning, stacklevel=3)
            col = 0
        etype = self.description[row][col]
        try:
            eschema = self.vreg.schema.eschema(etype)
            if eschema.is_final():
                raise NotAnEntity(etype)
        except KeyError:
            raise NotAnEntity(etype)
        return self._build_entity(row, col)

    def _build_entity(self, row, col, _localcache=None):
        """internal method to get a single entity, returns a
        partially initialized Entity instance.

        partially means that only attributes selected in the RQL
        query will be directly assigned to the entity.

        :type row,col: int, int
        :param row,col:
          row and col numbers localizing the entity among the result's table

        :return: the partially initialized `Entity` instance
        """
        req = self.req
        if req is None:
            raise AssertionError('dont call get_entity with no req on the result set')
        rowvalues = self.rows[row]
        eid = rowvalues[col]
        assert eid is not None
        # return cached entity if exists. This also avoids potential recursion
        # XXX should we consider updating a cached entity with possible
        #     new attributes found in this resultset ?
        try:
            if hasattr(req, 'is_super_session'):
                # this is a Session object which is not caching entities, so we
                # have to use a local cache to avoid recursion pb
                if _localcache is None:
                    _localcache = {}
                return _localcache[eid]
            else:
                return req.entity_cache(eid)
        except KeyError:
            pass
        # build entity instance
        etype = self.description[row][col]
        entity = self.vreg.etype_class(etype)(req, self, row, col)
        entity.set_eid(eid)
        # cache entity
        if _localcache is not None:
            _localcache[eid] = entity
        req.set_entity_cache(entity)
        eschema = entity.e_schema
        # try to complete the entity if there are some additional columns
        if len(rowvalues) > 1:
            rqlst = self.syntax_tree()
            if rqlst.TYPE == 'select':
                # UNION query, find the subquery from which this entity has been
                # found
                rqlst = rqlst.locate_subquery(col, etype, self.args)
            # take care, due to outer join support, we may find None
            # values for non final relation
            for i, attr, x in attr_desc_iterator(rqlst, col):
                if x == 'subject':
                    rschema = eschema.subject_relation(attr)
                    if rschema.is_final():
                        entity[attr] = rowvalues[i]
                        continue
                    tetype = rschema.objects(etype)[0]
                    card = rschema.rproperty(etype, tetype, 'cardinality')[0]
                else:
                    rschema = eschema.object_relation(attr)
                    tetype = rschema.subjects(etype)[0]
                    card = rschema.rproperty(tetype, etype, 'cardinality')[1]
                # only keep value if it can't be multivalued
                if card in '1?':
                    if rowvalues[i] is None:
                        if x == 'subject':
                            rql = 'Any Y WHERE X %s Y, X eid %s'
                        else:
                            rql = 'Any Y WHERE Y %s X, X eid %s'
                        rrset = ResultSet([], rql % (attr, entity.eid))
                        req.decorate_rset(rrset)
                    else:
                        rrset = self._build_entity(row, i, _localcache).as_rset()
                    entity.set_related_cache(attr, x, rrset)
        return entity

    @cached
    def syntax_tree(self):
        """get the syntax tree for the source query.

        :rtype: rql.stmts.Statement
        :return: the RQL syntax tree of the originating query
        """
        if self._rqlst:
            rqlst = self._rqlst.copy()
            # to avoid transport overhead when pyro is used, the schema has been
            # unset from the syntax tree
            rqlst.schema = self.vreg.schema
            self.vreg.rqlhelper.annotate(rqlst)
        else:
            rqlst = self.vreg.parse(self.req, self.rql, self.args)
        return rqlst

    @cached
    def column_types(self, col):
        """return the list of different types in the column with the given col
        index default to 0 (ie the first column)

        :type col: int
        :param col: the index of the desired column

        :rtype: list
        :return: the different entities type found in the column
        """
        return frozenset(struc[-1][col] for struc in self.description_struct())

    @cached
    def description_struct(self):
        """return a list describing sequence of results with the same
        description, e.g. :
        [[0, 4, ('Bug',)]
        [[0, 4, ('Bug',), [5, 8, ('Story',)]
        [[0, 3, ('Project', 'Version',)]]
        """
        result = []
        last = None
        for i, row in enumerate(self.description):
            if row != last:
                if last is not None:
                    result[-1][1] = i - 1
                result.append( [i, None, row] )
                last = row
        if last is not None:
            result[-1][1] = i
        return result

    @cached
    def related_entity(self, row, col):
        """try to get the related entity to extract format information if any"""
        locate_query_col = col
        rqlst = self.syntax_tree()
        etype = self.description[row][col]
        if self.vreg.schema.eschema(etype).is_final():
            # final type, find a better one to locate the correct subquery
            # (ambiguous if possible)
            for i in xrange(len(rqlst.children[0].selection)):
                if i == col:
                    continue
                coletype = self.description[row][i]
                if coletype is None:
                    continue
                if not self.vreg.schema.eschema(coletype).is_final():
                    etype = coletype
                    locate_query_col = i
                    if len(self.column_types(i)) > 1:
                        break
        # UNION query, find the subquery from which this entity has been found
        select = rqlst.locate_subquery(locate_query_col, etype, self.args)
        try:
            myvar = select.selection[col].variable
        except AttributeError:
            # not a variable
            return None, None
        rel = myvar.main_relation()
        if rel is not None:
            index = rel.children[0].variable.selected_index()
            if index is not None and self.rows[row][index]:
                return self.get_entity(row, index), rel.r_type
        return None, None

    @cached
    def searched_text(self):
        """returns the searched text in case of full-text search

        :return: searched text or `None` if the query is not
                 a full-text query
        """
        rqlst = self.syntax_tree()
        for rel in rqlst.iget_nodes(nodes.Relation):
            if rel.r_type == 'has_text':
                __, rhs = rel.get_variable_parts()
                return rhs.eval(self.args)
        return None


def attr_desc_iterator(rqlst, index=0):
    """return an iterator on a list of 2-uple (index, attr_relation)
    localizing attribute relations of the main variable in a result's row

    :type rqlst: rql.stmts.Select
    :param rqlst: the RQL syntax tree to describe

    :return:
      a generator on (index, relation, target) describing column being
      attribute of the main variable
    """
    main = rqlst.selection[index]
    for i, term in enumerate(rqlst.selection):
        if i == index:
            continue
        # XXX rewritten const
        # use iget_nodes for (hack) case where we have things like MAX(V)
        for vref in term.iget_nodes(nodes.VariableRef):
            var = vref.variable
            break
        else:
            continue
        #varname = var.name
        for ref in var.references():
            rel = ref.relation()
            if rel is None or rel.is_types_restriction():
                continue
            lhs, rhs = rel.get_variable_parts()
            if main.is_equivalent(lhs):
                if rhs.is_equivalent(term):
                    yield (i, rel.r_type, 'subject')
            elif main.is_equivalent(rhs):
                if lhs.is_equivalent(term):
                    yield (i, rel.r_type, 'object')
