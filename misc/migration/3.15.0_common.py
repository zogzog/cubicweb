undo_actions = config.cfgfile_parser.get('MAIN', 'undo-support', False)
config.global_set_option('undo-enabled', bool(undo_actions))
