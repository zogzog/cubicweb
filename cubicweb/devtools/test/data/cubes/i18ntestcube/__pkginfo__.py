# pylint: disable=W0622
"""cubicweb i18n test cube application packaging information"""

modname = 'i18ntestcube'
distname = 'cubicweb-i18ntestcube'

numversion = (0, 1, 0)
version = '.'.join(str(num) for num in numversion)

license = 'LGPL'
author = 'LOGILAB S.A. (Paris, FRANCE)'
author_email = 'contact@logilab.fr'
description = 'forum'
web = 'http://www.cubicweb.org/project/%s' % distname

__depends__ =  {'cubicweb': '>= 3.16.4',
               }
__recommends__ = {}
