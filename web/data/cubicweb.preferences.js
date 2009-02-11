/* toggle visibility of an element by its id
 * & set current visibility status in a cookie
 * XXX whenever used outside of preferences, don't forget to
 *     move me in a more appropriate place
 */
function toggle_and_remember_visibility(elemId, cookiename) {
    jqNode(elemId).toggleClass('hidden');
    async_remote_exec('set_cookie', cookiename,
                      jQuery('#' + elemId).attr('class'));
}
