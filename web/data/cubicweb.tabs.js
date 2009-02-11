function set_tab(tabname, cookiename) {
    // set appropriate cookie
    async_remote_exec('set_cookie', cookiename, tabname);
    // trigger show + tabname event
    trigger_load(tabname);
}
