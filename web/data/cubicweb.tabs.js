function set_tab(tabname) {
  // set appropriate cookie
  // XXX see if we can no just do it with jQuery
  async_remote_exec('remember_active_tab', tabname);
  // trigger show + tabname event
  trigger_load(tabname);
}
