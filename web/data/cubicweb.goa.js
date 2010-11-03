/**
 *  functions specific to cubicweb on google appengine
 *
 *  :organization: Logilab
 *  :copyright: 2008-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
 *  :contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
 */

/**
 * .. function:: rql_for_eid(eid)
 *
 * overrides rql_for_eid function from htmlhelpers.hs
 */
function rql_for_eid(eid) {
        return 'Any X WHERE X eid "' + eid + '"';
}
