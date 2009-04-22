function set_tab(tabname, cookiename) {
    // set appropriate cookie
    asyncRemoteExec('set_cookie', cookiename, tabname);
    // trigger show + tabname event
    trigger_load(tabname);
}
