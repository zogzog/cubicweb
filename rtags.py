
class RelationTags(object):

    def __init__(self, use_set=False):
        self.use_set = use_set
        self._tagdefs = {}
        
    def set_rtag(self, tag, role, rtype, stype='*', otype='*'):
        assert not self.use_set
        assert role in ('subject', 'object'), role
        self._tagdefs[(stype, rtype, otype, role)] = tag
        
    def rtag(self, role, rtype, stype='*', otype='*'):
        assert not self.use_set
        for key in reversed(self._get_keys(role, rtype, stype, otype)):
            try:
                return self._tagdefs[key]
            except KeyError:
                continue
        return None
        
    def etype_rtag(self, etype, role, rtype, ttype='*'):
        if role == 'subject':
            return self.rtag(role, rtype, etype, ttype)
        return self.rtag(role, rtype, ttype, etype)
        
    def add_rtag(self, tag, role, rtype, stype='*', otype='*'):
        assert self.use_set
        assert role in ('subject', 'object'), role
        rtags = self._tagdefs.setdefault((stype, rtype, otype, role), set())
        rtags.add(tag)
        
    def rtags(self, role, rtype, stype='*', otype='*'):
        assert self.use_set
        rtags = set()
        for key in self._get_keys(role, rtype, stype, otype):
            try:
                rtags.update(self._tagdefs[key])
            except KeyError:
                continue
        return rtags
        
    def etype_rtags(self, etype, role, rtype, ttype='*'):
        if role == 'subject':
            return self.rtags(role, rtype, etype, ttype)
        return self.rtags(role, rtype, ttype, etype)

    def _get_keys(self, role, rtype, stype, otype): 
        assert role in ('subject', 'object'), role
        keys = [('*', rtype, '*', role),
                ('*', rtype, otype, role),
                (stype, rtype, '*', role),
                (stype, rtype, otype, role)]
        if stype == '*' or otype == '*':
            keys.remove(('*', rtype, '*', role))
            if stype == '*':
                keys.remove(('*', rtype, otype, role))
            if otype == '*':
                keys.remove((stype, rtype, '*', role))            
        return keys
    
    # dict compat
    def __getitem__(self, key):
        if isinstance(key, basestring):
            key = (key,)
        return self.rtags(*key)

    __contains__ = __getitem__
