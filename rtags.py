"""relation tags store

:organization: Logilab
:copyright: 2001-2009 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
__docformat__ = "restructuredtext en"

import logging

from logilab.common.logging_ext import set_log_methods

RTAGS = []
def register_rtag(rtag):
    RTAGS.append(rtag)

class RelationTags(object):
    """a tag store for full relation definitions :

         (subject type, relation type, object type, tagged)

    allowing to set tags using wildcard (eg '*') as subject type / object type

    This class associates a single tag to each key.
    """
    _allowed_values = None
    def __init__(self, name=None, initfunc=None, allowed_values=None):
        self._name = name or '<unknown>'
        self._tagdefs = {}
        if allowed_values is not None:
            self._allowed_values = allowed_values
        self._initfunc = initfunc
        register_rtag(self)

    def __repr__(self):
        return '%s: %s' % (self._name, repr(self._tagdefs))

    # dict compat
    def __getitem__(self, key):
        return self.get(*key)
    __contains__ = __getitem__

    def _get_keys(self, stype, rtype, otype, tagged):
        keys = [(rtype, tagged, '*', '*'),
                (rtype, tagged, '*', otype),
                (rtype, tagged, stype, '*'),
                (rtype, tagged, stype, otype)]
        if stype == '*' or otype == '*':
            keys.remove((rtype, tagged, '*', '*'))
            if stype == '*':
                keys.remove((rtype, tagged, '*', otype))
            if otype == '*':
                keys.remove((rtype, tagged, stype, '*'))
        return keys

    def init(self, schema, check=True):
        # XXX check existing keys against schema
        if check:
            for (rtype, tagged, stype, otype), value in self._tagdefs.items():
                for ertype in (stype, rtype, otype):
                    if ertype != '*' and not ertype in schema:
                        self.warning('removing rtag %s: %s, %s undefined in schema',
                                     (stype, rtype, otype, tagged), value, ertype)
                        self.del_rtag(stype, rtype, otype, tagged)
                        break
        if self._initfunc is not None:
            for eschema in schema.entities():
                for rschema, tschemas, role in eschema.relation_definitions(True):
                    for tschema in tschemas:
                        if role == 'subject':
                            sschema, oschema = eschema, tschema
                        else:
                            sschema, oschema = tschema, eschema
                        self._initfunc(self, sschema, rschema, oschema, role)

    # rtag declaration api ####################################################

    def tag_attribute(self, key, tag):
        key = list(key)
        key.append('*')
        self.tag_subject_of(key, tag)

    def tag_subject_of(self, key, tag):
        key = list(key)
        key.append('subject')
        self.tag_relation(key, tag)

    def tag_object_of(self, key, tag):
        key = list(key)
        key.append('object')
        self.tag_relation(key, tag)

    def tag_relation(self, key, tag):
        #if isinstance(key, basestring):
        #    stype, rtype, otype = key.split()
        #else:
        stype, rtype, otype, tagged = [str(k) for k in key]
        if self._allowed_values is not None:
            assert tag in self._allowed_values, \
                   '%r is not an allowed tag (should be in %s)' % (
                tag, self._allowed_values)
        self._tagdefs[(rtype, tagged, stype, otype)] = tag
        return tag

    # rtag runtime api ########################################################

    def del_rtag(self, stype, rtype, otype, tagged):
        del self._tagdefs[(rtype, tagged, stype, otype)]

    def get(self, stype, rtype, otype, tagged):
        for key in reversed(self._get_keys(stype, rtype, otype, tagged)):
            try:
                return self._tagdefs[key]
            except KeyError:
                continue
        return None

    def etype_get(self, etype, rtype, role, ttype='*'):
        if role == 'subject':
            return self.get(etype, rtype, ttype, role)
        return self.get(ttype, rtype, etype, role)



class RelationTagsSet(RelationTags):
    """This class associates a set of tags to each key.
    """
    tag_container_cls = set

    def tag_relation(self, key, tag):
        stype, rtype, otype, tagged = [str(k) for k in key]
        rtags = self._tagdefs.setdefault((rtype, tagged, stype, otype),
                                         self.tag_container_cls())
        rtags.add(tag)
        return rtags

    def get(self, stype, rtype, otype, tagged):
        rtags = self.tag_container_cls()
        for key in self._get_keys(stype, rtype, otype, tagged):
            try:
                rtags.update(self._tagdefs[key])
            except KeyError:
                continue
        return rtags


class RelationTagsDict(RelationTagsSet):
    """This class associates a set of tags to each key."""
    tag_container_cls = dict

    def tag_relation(self, key, tag):
        stype, rtype, otype, tagged = [str(k) for k in key]
        try:
            rtags = self._tagdefs[(rtype, tagged, stype, otype)]
            rtags.update(tag)
            return rtags
        except KeyError:
            self._tagdefs[(rtype, tagged, stype, otype)] = tag
            return tag

    def setdefault(self, key, tagkey, tagvalue):
        stype, rtype, otype, tagged = [str(k) for k in key]
        try:
            rtags = self._tagdefs[(rtype, tagged, stype, otype)]
            rtags.setdefault(tagkey, tagvalue)
            return rtags
        except KeyError:
            self._tagdefs[(rtype, tagged, stype, otype)] = {tagkey: tagvalue}
            return self._tagdefs[(rtype, tagged, stype, otype)]


class RelationTagsBool(RelationTags):
    _allowed_values = frozenset((True, False))


set_log_methods(RelationTags, logging.getLogger('cubicweb.rtags'))
