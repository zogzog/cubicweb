"""

:organization: Logilab
:copyright: 2001-2010 LOGILAB S.A. (Paris, FRANCE), license is LGPL v2.
:contact: http://www.logilab.fr/ -- mailto:contact@logilab.fr
:license: GNU Lesser General Public License, v2.1 - http://www.gnu.org/licenses
"""
def postinit(vreg):
    """this callback is called at the end of initialization process
    and can be used to load explicit modules (views or entities).

    For instance :
    import someviews
    vreg.load_module(someviws)
    """
    # from migration import migrate
    # migrate(vreg)
