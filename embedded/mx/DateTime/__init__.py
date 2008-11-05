""" mxDateTime - Date and time handling routines and types

    Copyright (c) 1998-2000, Marc-Andre Lemburg; mailto:mal@lemburg.com
    Copyright (c) 2000-2007, eGenix.com Software GmbH; mailto:info@egenix.com
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.
"""
from DateTime import *
from DateTime import __version__

## mock strptime implementation
from datetime import datetime

def strptime(datestr, formatstr, datetime=datetime):
    """mocked strptime implementation"""
    date = datetime.strptime(datestr, formatstr)
    return DateTime(date.year, date.month, date.day,
                    date.hour, date.minute, date.second)

# don't expose datetime directly
del datetime
