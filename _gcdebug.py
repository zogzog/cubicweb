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

import gc, types, weakref

from cubicweb.schema import CubicWebRelationSchema, CubicWebEntitySchema

listiterator = type(iter([]))

IGNORE_CLASSES = (
    type, tuple, dict, list, set, frozenset, type(len),
    weakref.ref, weakref.WeakKeyDictionary,
    listiterator,
    property, classmethod,
    types.ModuleType, types.FunctionType, types.MethodType,
    types.MemberDescriptorType, types.GetSetDescriptorType,
    )

def _get_counted_class(obj, classes):
    for cls in classes:
        if isinstance(obj, cls):
            return cls
    raise AssertionError()

def gc_info(countclasses,
            ignoreclasses=IGNORE_CLASSES,
            viewreferrersclasses=(), showobjs=False, maxlevel=1):
    gc.collect()
    gc.collect()
    counters = {}
    ocounters = {}
    for obj in gc.get_objects():
        if isinstance(obj, countclasses):
            cls = _get_counted_class(obj, countclasses)
            try:
                counters[cls.__name__] += 1
            except KeyError:
                counters[cls.__name__] = 1
        elif not isinstance(obj, ignoreclasses):
            try:
                key = '%s.%s' % (obj.__class__.__module__,
                                 obj.__class__.__name__)
            except AttributeError:
                key = str(obj)
            try:
                ocounters[key] += 1
            except KeyError:
                ocounters[key] = 1
        if isinstance(obj, viewreferrersclasses):
            print '   ', obj, referrers(obj, showobjs, maxlevel)
    return counters, ocounters, gc.garbage


def referrers(obj, showobj=False, maxlevel=1):
    objreferrers = _referrers(obj, maxlevel)
    try:
        return sorted(set((type(x), showobj and x or getattr(x, '__name__', '%#x' % id(x)))
                          for x in objreferrers))
    except TypeError:
        s = set()
        unhashable = []
        for x in objreferrers:
            try:
                s.add(x)
            except TypeError:
                unhashable.append(x)
        return sorted(s) + unhashable

def _referrers(obj, maxlevel, _seen=None, _level=0):
    interesting = []
    if _seen is None:
        _seen = set()
    for x in gc.get_referrers(obj):
        if id(x) in _seen:
            continue
        _seen.add(id(x))
        if isinstance(x, types.FrameType):
            continue
        if isinstance(x, (CubicWebRelationSchema, CubicWebEntitySchema)):
            continue
        if isinstance(x, (list, tuple, set, dict, listiterator)):
            if _level >= maxlevel:
                pass
                #interesting.append(x)
            else:
                interesting += _referrers(x, maxlevel, _seen, _level+1)
        else:
            interesting.append(x)
    return interesting
