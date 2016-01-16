if versions_map['cubicweb'][0] == (3, 7, 4):
    config['http-session-time'] *= 60
    config['cleanup-session-time'] *= 60
    config['cleanup-anonymous-session-time'] *= 60
