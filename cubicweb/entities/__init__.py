# copyright 2003-2013 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""base application's entities class implementation: `AnyEntity`"""



from warnings import warn

from six import text_type, string_types

from logilab.common.decorators import classproperty
from logilab.common.deprecation import deprecated

from cubicweb import Unauthorized
from cubicweb.entity import Entity


class AnyEntity(Entity):
    """an entity instance has e_schema automagically set on the class and
    instances have access to their issuing cursor
    """
    __regid__ = 'Any'

    @classproperty
    def cw_etype(cls):
        """entity type as a unicode string"""
        return text_type(cls.__regid__)

    @classmethod
    def cw_create_url(cls, req, **kwargs):
        """ return the url of the entity creation form for this entity type"""
        return req.build_url('add/%s' % cls.__regid__, **kwargs)

    @classmethod
    @deprecated('[3.22] use cw_fti_index_rql_limit instead')
    def cw_fti_index_rql_queries(cls, req):
        """return the list of rql queries to fetch entities to FT-index

        The default is to fetch all entities at once and to prefetch
        indexable attributes but one could imagine iterating over
        "smaller" resultsets if the table is very big or returning
        a subset of entities that match some business-logic condition.
        """
        restrictions = ['X is %s' % cls.__regid__]
        selected = ['X']
        for attrschema in sorted(cls.e_schema.indexable_attributes()):
            varname = attrschema.type.upper()
            restrictions.append('X %s %s' % (attrschema, varname))
            selected.append(varname)
        return ['Any %s WHERE %s' % (', '.join(selected),
                                     ', '.join(restrictions))]

    @classmethod
    def cw_fti_index_rql_limit(cls, req, limit=1000):
        """generate rsets of entities to FT-index

        By default, each successive result set is limited to 1000 entities
        """
        if cls.cw_fti_index_rql_queries.__func__ != AnyEntity.cw_fti_index_rql_queries.__func__:
            warn("[3.22] cw_fti_index_rql_queries is replaced by cw_fti_index_rql_limit",
                 DeprecationWarning)
            for rql in cls.cw_fti_index_rql_queries(req):
                yield req.execute(rql)
            return
        restrictions = ['X is %s' % cls.__regid__]
        selected = ['X']
        start = 0
        for attrschema in sorted(cls.e_schema.indexable_attributes()):
            varname = attrschema.type.upper()
            restrictions.append('X %s %s' % (attrschema, varname))
            selected.append(varname)
        while True:
            q_restrictions = restrictions + ['X eid > %s' % start]
            rset = req.execute('Any %s ORDERBY X LIMIT %s WHERE %s' %
                               (', '.join(selected),
                                limit,
                                ', '.join(q_restrictions)))
            if rset:
                start = rset[-1][0]
                yield rset
            else:
                break

    # meta data api ###########################################################

    def dc_title(self):
        return self.cw_adapt_to('IDublinCore').title()

    def dc_long_title(self):
        return self.cw_adapt_to('IDublinCore').long_title()

    def dc_description(self, *args, **kwargs):
        return self.cw_adapt_to('IDublinCore').description(*args, **kwargs)

    def dc_authors(self):
        return self.cw_adapt_to('IDublinCore').authors()

    def dc_creator(self):
        return self.cw_adapt_to('IDublinCore').creator()

    def dc_date(self, *args, **kwargs):
        return self.cw_adapt_to('IDublinCore').date(*args, **kwargs)

    def dc_type(self, *args, **kwargs):
        return self.cw_adapt_to('IDublinCore').type(*args, **kwargs)

    def dc_language(self):
        return self.cw_adapt_to('IDublinCore').language()

    @property
    def creator(self):
        """return the CWUser entity which has created this entity, or None if
        unknown or if the curent user doesn't has access to this euser
        """
        try:
            return self.created_by[0]
        except (Unauthorized, IndexError):
            return None

    # abstractions making the whole things (well, some at least) working ######

    def sortvalue(self, rtype=None):
        """return a value which can be used to sort this entity or given
        entity's attribute
        """
        if rtype is None:
            return self.dc_title().lower()
        value = self.cw_attr_value(rtype)
        # do not restrict to `unicode` because Bytes will return a `str` value
        if isinstance(value, string_types):
            return self.printable_value(rtype, format='text/plain').lower()
        return value


def fetch_config(fetchattrs, mainattr=None, pclass=AnyEntity, order='ASC'):
    """function to ease basic configuration of an entity class ORM. Basic usage
    is:

    .. sourcecode:: python

      class MyEntity(AnyEntity):

          fetch_attrs, cw_fetch_order = fetch_config(['attr1', 'attr2'])
          # uncomment line below if you want the same sorting for 'unrelated' entities
          # cw_fetch_unrelated_order = cw_fetch_order

    Using this, when using ORM methods retrieving this type of entity, 'attr1'
    and 'attr2' will be automatically prefetched and results will be sorted on
    'attr1' ascending (ie the first attribute in the list).

    This function will automatically add to fetched attributes those defined in
    parent class given using the `pclass` argument.

    Also, You can use `mainattr` and `order` argument to have a different
    sorting.
    """
    if pclass is not None:
        fetchattrs += pclass.fetch_attrs
    if mainattr is None:
        mainattr = fetchattrs[0]
    @classmethod
    def fetch_order(cls, select, attr, var):
        if attr == mainattr:
            select.add_sort_var(var, order=='ASC')
    return fetchattrs, fetch_order
