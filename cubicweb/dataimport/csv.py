# copyright 2003-2015 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Functions to help importing CSV data"""
from __future__ import absolute_import, print_function

import codecs
import csv as csvmod
import warnings

from six import PY2, PY3, string_types

from logilab.common import shellutils


def count_lines(stream_or_filename):
    if isinstance(stream_or_filename, string_types):
        f = open(stream_or_filename)
    else:
        f = stream_or_filename
        f.seek(0)
    i = 0  # useful is f is an empty file
    for i, line in enumerate(f):
        pass
    f.seek(0)
    return i + 1


def ucsvreader_pb(stream_or_path, encoding='utf-8', delimiter=',', quotechar='"',
                  skipfirst=False, withpb=True, skip_empty=True, separator=None,
                  quote=None):
    """same as :func:`ucsvreader` but a progress bar is displayed as we iter on rows"""
    if separator is not None:
        delimiter = separator
        warnings.warn("[3.20] 'separator' kwarg is deprecated, use 'delimiter' instead")
    if quote is not None:
        quotechar = quote
        warnings.warn("[3.20] 'quote' kwarg is deprecated, use 'quotechar' instead")
    if isinstance(stream_or_path, string_types):
        stream = open(stream_or_path, 'rb')
    else:
        stream = stream_or_path
    rowcount = count_lines(stream)
    if skipfirst:
        rowcount -= 1
    if withpb:
        pb = shellutils.ProgressBar(rowcount, 50)
    for urow in ucsvreader(stream, encoding, delimiter, quotechar,
                           skipfirst=skipfirst, skip_empty=skip_empty):
        yield urow
        if withpb:
            pb.update()
    print(' %s rows imported' % rowcount)


def ucsvreader(stream, encoding='utf-8', delimiter=',', quotechar='"',
               skipfirst=False, ignore_errors=False, skip_empty=True,
               separator=None, quote=None):
    """A csv reader that accepts files with any encoding and outputs unicode
    strings

    if skip_empty (the default), lines without any values specified (only
    separators) will be skipped. This is useful for Excel exports which may be
    full of such lines.
    """
    if PY3:
        stream = codecs.getreader(encoding)(stream)
    if separator is not None:
        delimiter = separator
        warnings.warn("[3.20] 'separator' kwarg is deprecated, use 'delimiter' instead")
    if quote is not None:
        quotechar = quote
        warnings.warn("[3.20] 'quote' kwarg is deprecated, use 'quotechar' instead")
    it = iter(csvmod.reader(stream, delimiter=delimiter, quotechar=quotechar))
    if not ignore_errors:
        if skipfirst:
            next(it)
        for row in it:
            if PY2:
                decoded = [item.decode(encoding) for item in row]
            else:
                decoded = row
            if not skip_empty or any(decoded):
                yield decoded
    else:
        if skipfirst:
            try:
                row = next(it)
            except csvmod.Error:
                pass
        # Safe version, that can cope with error in CSV file
        while True:
            try:
                row = next(it)
            # End of CSV, break
            except StopIteration:
                break
            # Error in CSV, ignore line and continue
            except csvmod.Error:
                continue
            if PY2:
                decoded = [item.decode(encoding) for item in row]
            else:
                decoded = row
            if not skip_empty or any(decoded):
                yield decoded
