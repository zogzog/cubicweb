# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This file is part of CubicWeb.
#
# CubicWeb is free software: you can redistribute it and/or modify it under the
# terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# CubicWeb is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with CubicWeb.  If not, see <http://www.gnu.org/licenses/>.
"""
A RelationTag object is an object which allows to link a configuration
information to a relation definition. For instance, the standard
primary view uses a RelationTag object (uicfg.primaryview_section) to
get the section to display relations.

.. sourcecode:: python

   # display ``entry_of`` relations in the ``relations`` section in the ``BlogEntry`` primary view
   uicfg.primaryview_section.tag_subject_of(('BlogEntry', 'entry_of', '*'),
                                             'relations')

   # hide every relation ``entry_of`` in the ``Blog`` primary view
   uicfg.primaryview_section.tag_object_of(('*', 'entry_of', 'Blog'), 'hidden')

Three primitives are defined:
   * ``tag_subject_of`` tag a relation in the subject's context
   * ``tag_object_of`` tag a relation in the object's context
   * ``tag_attribute`` shortcut for tag_subject_of
"""


import logging

from six import string_types

from logilab.common.logging_ext import set_log_methods
from logilab.common.registry import RegistrableInstance, yes


def _ensure_str_key(key):
    return tuple(str(k) for k in key)


def rtags_chain(rtag):
    """Return the rtags chain, starting from the given one, and going back through each parent rtag
    up to the root (i.e. which as no parent).
    """
    while rtag is not None:
        yield rtag
        rtag = rtag._parent


class RegistrableRtags(RegistrableInstance):
    __registry__ = 'uicfg'
    __select__ = yes()


class RelationTags(RegistrableRtags):
    """a tag store for full relation definitions :

         (subject type, relation type, object type, tagged)

    allowing to set tags using wildcard (eg '*') as subject type / object type

    This class associates a single tag to each key.
    """
    _allowed_values = None
    # _init expected to be a method (introduced in 3.17), while _initfunc a
    # function given as __init__ argument and kept for bw compat
    _init = _initfunc = None

    def __init__(self, parent=None, __module__=None):
        super(RelationTags, self).__init__(__module__)
        self._tagdefs = {}
        self._parent = parent
        if parent is not None:
            assert parent.__class__ is self.__class__, \
                'inconsistent class for parent rtag {0}'.format(parent)

    def __repr__(self):
        # find a way to have more infos but keep it readable
        # (in error messages in case of an ambiguity for instance)
        return '<%s %s>' % (self.__regid__, self._short_repr())

    def _short_repr(self):
        # find a way to have more infos but keep it readable
        # (in error messages in case of an ambiguity for instance)
        return '%s@0x%x%s' % (
            self.__module__, id(self),
            ' derived from %s' % self._parent._short_repr() if self._parent else '')

    # dict compat
    def __getitem__(self, key):
        return self.get(*key)
    __contains__ = __getitem__

    def clear(self):
        self._tagdefs.clear()

    def _get_keys(self, stype, rtype, otype, tagged):
        keys = []
        if '*' not in (stype, otype):
            keys.append(('*', rtype, '*', tagged))
        if '*' != stype:
            keys.append(('*', rtype, otype, tagged))
        if '*' != otype:
            keys.append((stype, rtype, '*', tagged))
        keys.append((stype, rtype, otype, tagged))
        return keys

    def init(self, schema, check=True):
        # XXX check existing keys against schema
        if check:
            for (stype, rtype, otype, tagged), value in list(self._tagdefs.items()):
                for ertype in (stype, rtype, otype):
                    if ertype != '*' and ertype not in schema:
                        self.warning('removing rtag %s: %s, %s undefined in schema',
                                     (stype, rtype, otype, tagged), value, ertype)
                        self.del_rtag(stype, rtype, otype, tagged)
                        break
        if self._parent is None and self._init is not None:
            self.apply(schema, self._init)

    def apply(self, schema, func):
        for eschema in schema.entities():
            if eschema.final:
                continue
            for rschema, tschemas, role in eschema.relation_definitions(True):
                for tschema in tschemas:
                    if role == 'subject':
                        sschema, oschema = eschema, tschema
                    else:
                        sschema, oschema = tschema, eschema
                    func(sschema, rschema, oschema, role)

    # rtag declaration api ####################################################

    def derive(self, module, select):
        """Return a derivated of this relation tag, associated to given module and selector.

        This derivated will hold a set of specific rules but delegate to its "parent" relation tags
        for unfound keys.

        >>> class_afs = uicfg.autoform_section.derive(__name__, is_instance('Class'))
        """
        copied = self.__class__(self, __module__=__name__)
        copied.__module__ = module
        copied.__select__ = select
        return copied

    def tag_attribute(self, key, *args, **kwargs):
        key = list(key)
        key.append('*')
        key.append('subject')
        self.tag_relation(key, *args, **kwargs)

    def tag_subject_of(self, key, *args, **kwargs):
        key = list(key)
        key.append('subject')
        self.tag_relation(key, *args, **kwargs)

    def tag_object_of(self, key, *args, **kwargs):
        key = list(key)
        key.append('object')
        self.tag_relation(key, *args, **kwargs)

    def tag_relation(self, key, tag):
        assert len(key) == 4, 'bad key: %s' % list(key)
        if self._allowed_values is not None:
            assert tag in self._allowed_values, \
                '%r is not an allowed tag (should be in %s)' % (
                    tag, self._allowed_values)
        self._tagdefs[_ensure_str_key(key)] = tag
        return tag

    def _tag_etype_attr(self, etype, attr, desttype='*', *args, **kwargs):
        if isinstance(attr, string_types):
            attr, role = attr, 'subject'
        else:
            attr, role = attr
        if role == 'subject':
            self.tag_subject_of((etype, attr, desttype), *args, **kwargs)
        else:
            self.tag_object_of((desttype, attr, etype), *args, **kwargs)

    # rtag runtime api ########################################################

    def del_rtag(self, *key):
        del self._tagdefs[key]

    def get(self, *key):
        """Return value for the given key, by looking from the most specific key to the more
        generic (using '*' wildcards). For each key, look into this rtag and its parent rtags.
        """
        for key in reversed(self._get_keys(*key)):
            for rtag in rtags_chain(self):
                try:
                    return rtag._tagdefs[key]
                except KeyError:
                    continue
        return None

    def etype_get(self, etype, rtype, role, ttype='*'):
        if role == 'subject':
            return self.get(etype, rtype, ttype, role)
        return self.get(ttype, rtype, etype, role)

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg, *a, **kw: None


class RelationTagsSet(RelationTags):
    """This class associates a set of tags to each key.
    """
    tag_container_cls = set

    def tag_relation(self, key, tag):
        rtags = self._tagdefs.setdefault(_ensure_str_key(key),
                                         self.tag_container_cls())
        rtags.add(tag)
        return rtags

    def get(self, stype, rtype, otype, tagged):
        """Return value for the given key, which is an union of the values found from the most
        specific key to the more generic (using '*' wildcards). For each key, look into this rtag
        and its parent rtags.
        """
        rtags = self.tag_container_cls()
        for key in self._get_keys(stype, rtype, otype, tagged):
            for rtag in rtags_chain(self):
                try:
                    rtags.update(rtag._tagdefs[key])
                    break
                except KeyError:
                    continue
        return rtags


class RelationTagsDict(RelationTagsSet):
    """This class associates a dictionary to each key."""
    tag_container_cls = dict

    def tag_relation(self, key, tag):
        key = _ensure_str_key(key)
        try:
            rtags = self._tagdefs[key]
            rtags.update(tag)
            return rtags
        except KeyError:
            self._tagdefs[key] = tag
            return tag

    def setdefault(self, key, tagkey, tagvalue):
        key = _ensure_str_key(key)
        try:
            rtags = self._tagdefs[key]
            rtags.setdefault(tagkey, tagvalue)
            return rtags
        except KeyError:
            self._tagdefs[key] = {tagkey: tagvalue}
            return self._tagdefs[key]


class RelationTagsBool(RelationTags):
    _allowed_values = frozenset((True, False))


class NoTargetRelationTagsDict(RelationTagsDict):

    @property
    def name(self):
        return self.__class__.name

    # tag_subject_of / tag_object_of issue warning if '*' is not given as target
    # type, while tag_relation handle it silently since it may be used during
    # initialization
    def tag_subject_of(self, key, tag):
        subj, rtype, obj = key
        if obj != '*':
            self.warning('using explict target type in %s.tag_subject_of() '
                         'has no effect, use (%s, %s, "*") instead of (%s, %s, %s)',
                         self.name, subj, rtype, subj, rtype, obj)
        super(NoTargetRelationTagsDict, self).tag_subject_of((subj, rtype, '*'), tag)

    def tag_object_of(self, key, tag):
        subj, rtype, obj = key
        if subj != '*':
            self.warning('using explict subject type in %s.tag_object_of() '
                         'has no effect, use ("*", %s, %s) instead of (%s, %s, %s)',
                         self.name, rtype, obj, subj, rtype, obj)
        super(NoTargetRelationTagsDict, self).tag_object_of(('*', rtype, obj), tag)

    def tag_relation(self, key, tag):
        if key[-1] == 'subject' and key[-2] != '*':
            if isinstance(key, tuple):
                key = list(key)
            key[-2] = '*'
        elif key[-1] == 'object' and key[0] != '*':
            if isinstance(key, tuple):
                key = list(key)
            key[0] = '*'
        super(NoTargetRelationTagsDict, self).tag_relation(key, tag)


set_log_methods(RelationTags, logging.getLogger('cubicweb.rtags'))
