function set_tab(tabname, cookiename) {
    // set appropriate cookie
    loadRemote('json', ajaxFuncArgs('set_cookie', null, cookiename, tabname));
    // trigger show + tabname event
    trigger_load(tabname);
}

