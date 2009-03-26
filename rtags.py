"""relation tags store

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
"""
__docformat__ = "restructuredtext en"

class RelationTags(object):
    """RelationTags instances are a tag store for full relation definitions :

         (subject type, relation type, object type, role)

    allowing to set tags using wildcard (eg '*') as subject type / object type

    if `use_set` is True, a set of tags is associated to each key, and you
    should use rtags / etype_rtags / add_rtag api. Otherwise, a single tag is
    associated to each key, and you should use rtag / etype_rtag / set_rtag api.
    """
    
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
