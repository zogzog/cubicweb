"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""

class RepoThread(object):
    def __init__(self, *args):
        pass # XXX raise
    def start(self):
        pass
    def join(self):
        pass

class LoopTask(RepoThread):
    def cancel(self):
        pass
