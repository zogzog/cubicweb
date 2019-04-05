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
import codecs
import csv as csvmod

from logilab.common import shellutils


def count_lines(stream_or_filename):
    if isinstance(stream_or_filename, str):
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
                  skipfirst=False, withpb=True, skip_empty=True):
    """same as :func:`ucsvreader` but a progress bar is displayed as we iter on rows"""
    if isinstance(stream_or_path, str):
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
               skipfirst=False, ignore_errors=False, skip_empty=True):
    """A csv reader that accepts files with any encoding and outputs unicode
    strings

    if skip_empty (the default), lines without any values specified (only
    separators) will be skipped. This is useful for Excel exports which may be
    full of such lines.
    """
    stream = codecs.getreader(encoding)(stream)
    it = iter(csvmod.reader(stream, delimiter=delimiter, quotechar=quotechar))
    if not ignore_errors:
        if skipfirst:
            next(it)
        for row in it:
            if not skip_empty or any(row):
                yield row
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
            if not skip_empty or any(row):
                yield row
