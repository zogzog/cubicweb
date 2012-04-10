undo_actions = config.cfgfile_parser.get('MAIN', 'undo-support', False)
config.global_set_option('undo-enabled', bool(undo_actions))
pyro_actions = config.cfgfile_parser.get('REMOTE', 'pyro', False)
if pyro_actions:
    config.global_set_option('repo-uri', 'pyro://')
