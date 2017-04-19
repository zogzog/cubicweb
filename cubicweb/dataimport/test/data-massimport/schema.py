# copyright 2015-2016 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
# contact http://www.logilab.fr -- mailto:contact@logilab.fr
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 2.1 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program. If not, see <http://www.gnu.org/licenses/>.
"""cubicweb-geonames schema

See geonames readme.txt for more details.
"""

from yams.buildobjs import (EntityType, SubjectRelation,
                            String, Int, BigInt, Float)


class Location(EntityType):
    """
    Entity type for location of Geonames.
    See cities1000.zip, cities5000.zip, cities15000.zip and allCountries.txt
    """
    name = String(maxsize=1024, indexed=True, fulltextindexed=True)
    geonameid = Int(indexed=True)
    asciiname = String(maxsize=200, fulltextindexed=True)
    alternatenames = String(fulltextindexed=True)
    latitude = Float(indexed=True)
    longitude = Float(indexed=True)
    feature_class = String(maxsize=1, indexed=True)
    alternate_country_code = String(maxsize=60)
    admin_code_3 = String(maxsize=20)
    admin_code_4 = String(maxsize=20)
    population = BigInt(indexed=True)
    elevation = Int(indexed=True)
    gtopo30 = Int(indexed=True)
    timezone = SubjectRelation('TimeZone', cardinality='?*', inlined=True)


class TimeZone(EntityType):
    """
    Entity type for timezone of geonames.
    See timeZones.txt
    """
    code = String(maxsize=1024, indexed=True, required=True)
    gmt = Float()
    dst = Float()
    raw_offset = Float()
