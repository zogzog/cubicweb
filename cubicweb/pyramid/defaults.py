# copyright 2017 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# copyright 2014-2016 UNLISH S.A.S. (Montpellier, FRANCE), all rights reserved.
#
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

""" Defaults for a classical CubicWeb instance. """


def includeme(config):
    """ Enable the defaults that make the application behave like a classical
    CubicWeb instance.

    The following modules get included:

    -   :func:`cubicweb.pyramid.session <cubicweb.pyramid.session.includeme>`
    -   :func:`cubicweb.pyramid.auth <cubicweb.pyramid.auth.includeme>`
    -   :func:`cubicweb.pyramid.login <cubicweb.pyramid.login.includeme>`

    It is automatically included by the configuration system, unless the
    following entry is added to the :ref:`pyramid_settings`:

    .. code-block:: ini

        cubicweb.defaults = no

    """
    config.include('cubicweb.pyramid.session')
    config.include('cubicweb.pyramid.auth')
    config.include('cubicweb.pyramid.login')
