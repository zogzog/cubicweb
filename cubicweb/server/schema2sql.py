# copyright 2004-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of cubicweb.
#
# yams is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# yams is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with yams. If not, see <http://www.gnu.org/licenses/>.
"""write a schema as sql"""

from hashlib import md5

from yams.constraints import (SizeConstraint, UniqueConstraint, Attribute,
                              NOW, TODAY)
from logilab import database
from logilab.common.decorators import monkeypatch

from cubicweb.schema import constraint_name_for

# default are usually not handled at the sql level. If you want them, set
# SET_DEFAULT to True
SET_DEFAULT = False


# backport fix for lgdb #6662663
@monkeypatch(database._GenericAdvFuncHelper)
def sql_create_index(self, table, column, unique=False):
    idx = self._index_name(table, column, unique)
    if unique:
        return 'ALTER TABLE %s ADD CONSTRAINT %s UNIQUE(%s)' % (table, idx, column)
    else:
        return 'CREATE INDEX %s ON %s(%s)' % (idx, table, column)


@monkeypatch(database._GenericAdvFuncHelper)
def _index_name(self, table, column, unique=False):
    if unique:
        return build_index_name(table, [column], prefix='key_')
    else:
        return build_index_name(table, [column], prefix='idx_')


def build_index_name(table, columns, prefix='idx_'):
    """Return a predictable-but-size-constrained name for an index on `table(*columns)`, using an
    md5 hash.
    """
    return '%s%s' % (prefix, md5((
        table + ',' + ','.join(sorted(columns))).encode('ascii')).hexdigest())


def rschema_has_table(rschema, skip_relations):
    """Return True if the given schema should have a table in the database."""
    return not (rschema.final or rschema.inlined or rschema.rule or rschema.type in skip_relations)


def schema2sql(dbhelper, schema, skip_entities=(), skip_relations=(), prefix=''):
    """Yield SQL statements to create a database schema for the given Yams schema.

    `prefix` may be a string that will be prepended to all table / column names (usually, 'cw_').
    """
    for etype in sorted(schema.entities()):
        eschema = schema.eschema(etype)
        if eschema.final or eschema.type in skip_entities:
            continue
        for sql in eschema2sql(dbhelper, eschema, skip_relations, prefix):
            yield sql
    for rtype in sorted(schema.relations()):
        rschema = schema.rschema(rtype)
        if rschema_has_table(rschema, skip_relations):
            for sql in rschema2sql(rschema):
                yield sql


def unique_index_name(eschema, attrs):
    """Return a predictable-but-size-constrained name for a multi-columns unique index on
    given attributes of the entity schema (actually, the later may be a schema or a string).
    """
    # keep giving eschema instead of table name for bw compat
    table = str(eschema)
    # unique_index_name is used as name of CWUniqueConstraint, hence it should be unicode
    return build_index_name(table, attrs, 'unique_')


def iter_unique_index_names(eschema):
    """Yield (attrs, index name) where attrs is a list of entity type's attribute names that should
    be unique together, and index name the unique index name.
    """
    for attrs in eschema._unique_together or ():
        yield attrs, unique_index_name(eschema, attrs)


def eschema_sql_def(dbhelper, eschema, skip_relations=(), prefix=''):
    """Return a list of (column names, sql type def) for the given entity schema.

    No constraint nor index are considered - this function is usually for massive import purpose.
    """
    attrs = [attrdef for attrdef in eschema.attribute_definitions()
             if not attrdef[0].type in skip_relations]
    attrs += [(rschema, None)
              for rschema in eschema.subject_relations()
              if not rschema.final and rschema.inlined]
    result = []
    for i in range(len(attrs)):
        rschema, attrschema = attrs[i]
        if attrschema is not None:
            # creating = False will avoid NOT NULL / REFERENCES constraints
            sqltype = aschema2sql(dbhelper, eschema, rschema, attrschema, creating=False)
        else:  # inline relation
            sqltype = 'integer'
        result.append(('%s%s' % (prefix, rschema.type), sqltype))
    return result


def eschema2sql(dbhelper, eschema, skip_relations=(), prefix=''):
    """Yield SQL statements to initialize database from an entity schema."""
    table = prefix + eschema.type
    output = []
    w = output.append
    w('CREATE TABLE %s(' % (table))
    attrs = [attrdef for attrdef in eschema.attribute_definitions()
             if not attrdef[0].type in skip_relations]
    attrs += [(rschema, None)
              for rschema in eschema.subject_relations()
              if not rschema.final and rschema.inlined]
    for i in range(len(attrs)):
        rschema, attrschema = attrs[i]
        if attrschema is not None:
            sqltype = aschema2sql(dbhelper, eschema, rschema, attrschema)
        else:  # inline relation
            sqltype = 'integer REFERENCES entities (eid)'
        if i == len(attrs) - 1:
            w(' %s%s %s' % (prefix, rschema.type, sqltype))
        else:
            w(' %s%s %s,' % (prefix, rschema.type, sqltype))
    for rschema, aschema in attrs:
        if aschema is None:  # inline relation
            continue
        rdef = rschema.rdef(eschema.type, aschema.type)
        for constraint in rdef.constraints:
            cstrname, check = check_constraint(rdef, constraint, dbhelper, prefix=prefix)
            if cstrname is not None:
                w(', CONSTRAINT %s CHECK(%s)' % (cstrname, check))
    w(')')
    yield '\n'.join(output)
    # create indexes
    for i in range(len(attrs)):
        rschema, attrschema = attrs[i]
        if attrschema is None or eschema.rdef(rschema).indexed:
            yield dbhelper.sql_create_index(table, prefix + rschema.type)
        if attrschema and any(isinstance(cstr, UniqueConstraint)
                              for cstr in eschema.rdef(rschema).constraints):
            yield dbhelper.sql_create_index(table, prefix + rschema.type, unique=True)
    for attrs, index_name in iter_unique_index_names(eschema):
        columns = ['%s%s' % (prefix, attr) for attr in attrs]
        sqls = dbhelper.sqls_create_multicol_unique_index(table, columns, index_name)
        for sql in sqls:
            yield sql.rstrip(';')  # remove trailing ';' for consistency


def constraint_value_as_sql(value, dbhelper, prefix):
    """Return the SQL value from a Yams constraint's value, handling special cases where it's a
    `Attribute`, `TODAY` or `NOW` instance instead of a literal value.
    """
    if isinstance(value, Attribute):
        return prefix + value.attr
    elif isinstance(value, TODAY):
        return dbhelper.sql_current_date()
    elif isinstance(value, NOW):
        return dbhelper.sql_current_timestamp()
    else:
        # XXX more quoting for literals?
        return value


def check_constraint(rdef, constraint, dbhelper, prefix=''):
    """Return (constraint name, constraint SQL definition) for the given relation definition's
    constraint. Maybe (None, None) if the constraint is not handled in the backend.
    """
    attr = rdef.rtype.type
    cstrname = constraint_name_for(constraint, rdef)
    if constraint.type() == 'BoundaryConstraint':
        value = constraint_value_as_sql(constraint.boundary, dbhelper, prefix)
        return cstrname, '%s%s %s %s' % (prefix, attr, constraint.operator, value)
    elif constraint.type() == 'IntervalBoundConstraint':
        condition = []
        if constraint.minvalue is not None:
            value = constraint_value_as_sql(constraint.minvalue, dbhelper, prefix)
            condition.append('%s%s >= %s' % (prefix, attr, value))
        if constraint.maxvalue is not None:
            value = constraint_value_as_sql(constraint.maxvalue, dbhelper, prefix)
            condition.append('%s%s <= %s' % (prefix, attr, value))
        return cstrname, ' AND '.join(condition)
    elif constraint.type() == 'StaticVocabularyConstraint':
        sample = next(iter(constraint.vocabulary()))
        if not isinstance(sample, str):
            values = ', '.join(str(word) for word in constraint.vocabulary())
        else:
            # XXX better quoting?
            values = ', '.join("'%s'" % word.replace("'", "''") for word in constraint.vocabulary())
        return cstrname, '%s%s IN (%s)' % (prefix, attr, values)
    return None, None


def aschema2sql(dbhelper, eschema, rschema, aschema, creating=True):
    """Return string containing a SQL table's column definition from attribute schema."""
    attr = rschema.type
    rdef = rschema.rdef(eschema.type, aschema.type)
    sqltype = type_from_rdef(dbhelper, rdef)
    if SET_DEFAULT:
        default = eschema.default(attr)
        if default is not None:
            if aschema.type == 'Boolean':
                sqltype += ' DEFAULT %s' % dbhelper.boolean_value(default)
            elif aschema.type == 'String':
                sqltype += ' DEFAULT %r' % str(default)
            elif aschema.type in ('Int', 'BigInt', 'Float'):
                sqltype += ' DEFAULT %s' % default
            # XXX ignore default for other type
            # this is expected for NOW / TODAY
    if creating:
        if rdef.uid:
            sqltype += ' PRIMARY KEY REFERENCES entities (eid)'
        elif rdef.cardinality[0] == '1':
            # don't set NOT NULL if backend isn't able to change it later
            if dbhelper.alter_column_support:
                sqltype += ' NOT NULL'
    # else we're getting sql type to alter a column, we don't want key / indexes
    # / null modifiers
    return sqltype


def type_from_rdef(dbhelper, rdef):
    """Return a string containing SQL type name for the given relation definition."""
    constraints = list(rdef.constraints)
    sqltype = None
    if rdef.object.type == 'String':
        for constraint in constraints:
            if isinstance(constraint, SizeConstraint) and constraint.max is not None:
                size_constrained_string = dbhelper.TYPE_MAPPING.get(
                    'SizeConstrainedString', 'varchar(%s)')
                sqltype = size_constrained_string % constraint.max
                break
    if sqltype is None:
        sqltype = sql_type(dbhelper, rdef)
    return sqltype


def sql_type(dbhelper, rdef):
    """Return a string containing SQL type to use to store values of the given relation definition.
    """
    sqltype = dbhelper.TYPE_MAPPING[rdef.object]
    if callable(sqltype):
        sqltype = sqltype(rdef)
    return sqltype


_SQL_SCHEMA = """
CREATE TABLE %(table)s (
  eid_from INTEGER NOT NULL REFERENCES entities (eid),
  eid_to INTEGER NOT NULL REFERENCES entities (eid),
  CONSTRAINT %(pkey_idx)s PRIMARY KEY(eid_from, eid_to)
);

CREATE INDEX %(from_idx)s ON %(table)s(eid_from);
CREATE INDEX %(to_idx)s ON %(table)s(eid_to)"""


def rschema2sql(rschema):
    """Yield SQL statements to create database table and indexes for a Yams relation schema."""
    assert not rschema.rule
    table = '%s_relation' % rschema.type
    sqls = _SQL_SCHEMA % {'table': table,
                          'pkey_idx': build_index_name(table, ['eid_from', 'eid_to'], 'key_'),
                          'from_idx': build_index_name(table, ['eid_from'], 'idx_'),
                          'to_idx': build_index_name(table, ['eid_to'], 'idx_')}
    for sql in sqls.split(';'):
        yield sql.strip()


def grant_schema(schema, user, set_owner=True, skip_entities=(), prefix=''):
    """Yield SQL statements to give all access (and ownership if `set_owner` is True) on the
    database tables for the given Yams schema to `user`.

    `prefix` may be a string that will be prepended to all table / column names (usually, 'cw_').
    """
    for etype in sorted(schema.entities()):
        eschema = schema.eschema(etype)
        if eschema.final or etype in skip_entities:
            continue
        for sql in grant_eschema(eschema, user, set_owner, prefix=prefix):
            yield sql
    for rtype in sorted(schema.relations()):
        rschema = schema.rschema(rtype)
        if rschema_has_table(rschema, skip_relations=()):  # XXX skip_relations should be specified
            for sql in grant_rschema(rschema, user, set_owner):
                yield sql


def grant_eschema(eschema, user, set_owner=True, prefix=''):
    """Yield SQL statements to give all access (and ownership if `set_owner` is True) on the
    database tables for the given Yams entity schema to `user`.
    """
    etype = eschema.type
    if set_owner:
        yield 'ALTER TABLE %s%s OWNER TO %s' % (prefix, etype, user)
    yield 'GRANT ALL ON %s%s TO %s' % (prefix, etype, user)


def grant_rschema(rschema, user, set_owner=True):
    """Yield SQL statements to give all access (and ownership if `set_owner` is True) on the
    database tables for the given Yams relation schema to `user`.
    """
    if set_owner:
        yield 'ALTER TABLE %s_relation OWNER TO %s' % (rschema.type, user)
    yield 'GRANT ALL ON %s_relation TO %s' % (rschema.type, user)
