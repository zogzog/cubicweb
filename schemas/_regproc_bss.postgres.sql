/* -*- sql -*-

   postgres specific registered procedures for the Bytes File System storage,
   require the plpythonu language installed

*/


CREATE OR REPLACE FUNCTION _fsopen(bytea) RETURNS bytea AS $$
    fpath = args[0]
    if fpath:
        try:
	    data = file(fpath, 'rb').read()
	    #/* XXX due to plpython bug we have to replace some characters... */
            return data.replace("\\", r"\134").replace("\000", r"\000").replace("'", r"\047") #'
        except Exception, ex:
	    plpy.warning('failed to get content for %s: %s', fpath, ex)
     return None
$$ LANGUAGE plpythonu
/* WITH(ISCACHABLE) XXX does postgres handle caching of large data nicely */
;;

/* fspath(eid, entity type, attribute) */
CREATE OR REPLACE FUNCTION fspath(bigint, text, text) RETURNS bytea AS $$
    pkey = 'plan%s%s' % (args[1], args[2])
    try:
        plan = SD[pkey]
    except KeyError:
        #/* then prepare and cache plan to get versioned file information from a
        # version content eid */
        plan = plpy.prepare(
            'SELECT X.cw_%s FROM cw_%s as X WHERE X.cw_eid=$1' % (args[2], args[1]),
            ['bigint'])
        SD[pkey] = plan
    return plpy.execute(plan, [args[0]])[0]
$$ LANGUAGE plpythonu
/* WITH(ISCACHABLE) XXX does postgres handle caching of large data nicely */
;;
