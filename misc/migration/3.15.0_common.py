import ConfigParser
try:
    undo_actions = config.cfgfile_parser.get('MAIN', 'undo-support', False)
except ConfigParser.NoOptionError:
    pass # this conf. file was probably already migrated
else:
    config.global_set_option('undo-enabled', bool(undo_actions))
