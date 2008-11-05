# following functions have been renamed, but keep old definition for bw compat
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
