# copyright 2003-2012 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

The `AppObject` class
---------------------

The AppObject class is the base class for all dynamically loaded objects
(application objects) accessible through the vregistry.

We can find a certain number of attributes and methods defined in this class and
common to all the application objects.

"""


from logging import getLogger

from logilab.common.logging_ext import set_log_methods

from logilab.common.registry import RegistrableObject, yes


# the base class for all appobjects ############################################

class AppObject(RegistrableObject):
    """This is the base class for CubicWeb application objects which are
    selected in a request context.

    The following attributes should be set on concrete appobject classes:

    At selection time, the following attributes are set on the instance:

    :attr:`_cw`
      current request
    :attr:`cw_extra_kwargs`
      other received arguments

    And also the following, only if `rset` is found in arguments (in which case
    rset/row/col will be removed from `cwextra_kwargs`):

    :attr:`cw_rset`
      context result set or None

    :attr:`cw_row`
      if a result set is set and the context is about a particular cell in the
      result set, and not the result set as a whole, specify the row number we
      are interested in, else None

    :attr:`cw_col`
      if a result set is set and the context is about a particular cell in the
      result set, and not the result set as a whole, specify the col number we
      are interested in, else None


    .. Note::

      * do not inherit directly from this class but from a more specific class
        such as `AnyEntity`, `EntityView`, `AnyRsetView`, `Action`...

    """
    __select__ = yes()

    @classmethod
    def __registered__(cls, registry):
        """called by the registry when the appobject has been registered.

        It must return the object that will be actually registered (this may be
        the right hook to create an instance for example). By default the
        appobject is returned without any transformation.
        """
        pdefs = getattr(cls, 'cw_property_defs', {})
        for propid, pdef in pdefs.items():
            pdef = pdef.copy() # may be shared
            pdef['default'] = getattr(cls, propid, pdef['default'])
            pdef['sitewide'] = getattr(cls, 'site_wide', pdef.get('sitewide'))
            registry.vreg.register_property(cls._cwpropkey(propid), **pdef)
        assert callable(cls.__select__), cls
        return cls

    def __init__(self, req, **extra):
        super(AppObject, self).__init__()
        self._cw = req
        try:
            self.cw_rset = extra.pop('rset')
            self.cw_row = extra.pop('row', None)
            self.cw_col = extra.pop('col', None)
        except KeyError:
            pass
        self.cw_extra_kwargs = extra

    # persistent class properties ##############################################
    #
    # optional `cw_property_defs` dict on a class defines available persistent
    # properties for this class:
    #
    # * key: id of the property (the actual CWProperty key is build using
    #        <registry name>.<obj id>.<property id>
    # * value: tuple (property type, vocabfunc, default value, property description)
    #         possible types are those used by `logilab.common.configuration`
    #
    # notice that when it exists multiple objects with the same id (adaptation,
    # overriding) only the first encountered definition is considered, so those
    # objects can't try to have different default values for instance.
    #
    # you can then access to a property value using self.cw_propval, where self
    # is an instance of class

    @classmethod
    def _cwpropkey(cls, propid):
        """return cw property key for the property of the given id for this
        class
        """
        return '%s.%s.%s' % (cls.__registry__, cls.__regid__, propid)

    def cw_propval(self, propid):
        """return cw property value associated to key

        <cls.__registry__>.<cls.id>.<propid>
        """
        return self._cw.property_value(self._cwpropkey(propid))

    # these are overridden by set_log_methods below
    # only defining here to prevent pylint from complaining
    info = warning = error = critical = exception = debug = lambda msg,*a,**kw: None

set_log_methods(AppObject, getLogger('cubicweb.appobject'))
