# following functions have been renamed, but keep old definition for bw compat
"""

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
sql('''CREATE AGGREGATE group_concat (
  basetype = anyelement,
  sfunc = array_append,
  stype = anyarray,
  finalfunc = comma_join,
  initcond = '{}'
)''')

sql('''CREATE FUNCTION text_limit_size (fulltext text, maxsize integer) RETURNS text AS $$
BEGIN
    RETURN limit_size(fulltext, 'text/plain', maxsize);
END
$$ LANGUAGE plpgsql;
''')


synchronize_rschema('bookmarked_by')
