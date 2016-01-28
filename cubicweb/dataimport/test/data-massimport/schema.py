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

from yams.buildobjs import (EntityType, RelationDefinition, SubjectRelation,
                            String, Int, BigInt, Float, Date)


class TestLocation(EntityType):
    """
    Entity type for location of Geonames.
    See cities1000.zip, cities5000.zip, cities15000.zip and allCountries.txt
    """
    name = String(maxsize=1024, indexed=True, fulltextindexed=True)
    geonameid = Int(required=True, unique=True, indexed=True)


class Location(EntityType):
    """
    Entity type for location of Geonames.
    See cities1000.zip, cities5000.zip, cities15000.zip and allCountries.txt
    """
    name = String(maxsize=1024, indexed=True, fulltextindexed=True)
    geonameid = Int(indexed=True)
    asciiname = String(maxsize=200, fulltextindexed=True)
    alternatenames = String(fulltextindexed=True)
    names = SubjectRelation('LocationName', cardinality='**')
    latitude = Float(indexed=True)
    longitude = Float(indexed=True)
    feature_class = String(maxsize=1, indexed=True)
    feature_code = SubjectRelation('FeatureCode', cardinality='?*', inlined=True)
    country = SubjectRelation('Country', cardinality='?*', inlined=True)
    alternate_country_code = String(maxsize=60)
    main_administrative_region = SubjectRelation('AdministrativeRegion',
                                                 cardinality='?*', inlined=True)
    second_administrative_region = SubjectRelation('AdministrativeRegion',
                                                   cardinality='?*', inlined=True)
    admin_code_1 = String(maxsize=124)
    admin_code_2 = String(maxsize=124)
    admin_code_3 = String(maxsize=20)
    admin_code_4 = String(maxsize=20)
    population = BigInt(indexed=True)
    elevation = Int(indexed=True)
    gtopo30 = Int(indexed=True)
    timezone = SubjectRelation('TimeZone', cardinality='?*', inlined=True)
    geonames_date = Date()


class LocationName(EntityType):
    """
    Name of a Location
    """
    name = String(maxsize=1024, indexed=True, fulltextindexed=True)
    language = SubjectRelation('Language', cardinality='?*', inlined=True)
    alternatenamesid = Int(indexed=True)


class FeatureCode(EntityType):
    """
    Entity type for feature codes of Geonames.
    See featureCodes_en.txt
    """
    name = String(maxsize=1024, indexed=True, fulltextindexed=True)
    main_code = String(maxsize=1, indexed=True)
    code = String(maxsize=12)
    description = String(maxsize=1024, fulltextindexed=True)


class AdministrativeRegion(EntityType):
    """
    Entity type for administrative regions of Geonames.
    See admin1CodesASCII.txt and admin2Codes.txt
    """
    name = String(maxsize=1024, indexed=True, fulltextindexed=True)
    code = String(maxsize=64, indexed=True)
    country = SubjectRelation('Country', cardinality='?*', inlined=True)
    geonameid = Int(indexed=True)
    asciiname = String(maxsize=200, fulltextindexed=True)


class Language(EntityType):
    """
    Entity type for languages of Geonames.
    See admin1CodesASCII.txt and admin2Codes.txt
    """
    name = String(maxsize=1024, indexed=True, fulltextindexed=True)
    iso_639_3 = String(maxsize=3, indexed=True)
    iso_639_2 = String(maxsize=64, indexed=True)
    iso_639_1 = String(maxsize=3, indexed=True)


class Continent(EntityType):
    """
    Entity type for continents of geonames.
    """
    name = String(maxsize=1024, indexed=True, fulltextindexed=True)
    code = String(maxsize=2, indexed=True)
    geonameid = Int(indexed=True)


class Country(EntityType):
    """
    Entity type for countries of geonames.
    See countryInfo.txt
    """
    name = String(maxsize=1024, indexed=True, fulltextindexed=True)
    code = String(maxsize=2, indexed=True)
    code3 = String(maxsize=3, indexed=True)
    codenum = Int(indexed=True)
    fips = String(maxsize=2)
    capital = String(maxsize=1024, fulltextindexed=True)
    area = Float(indexed=True)
    population = BigInt(indexed=True)
    continent_code = String(maxsize=3)
    continent = SubjectRelation('Continent', cardinality='?*', inlined=True)
    tld = String(maxsize=64)
    currency = String(maxsize=1024, fulltextindexed=True)
    currency_code = String(maxsize=64)
    geonameid = Int(indexed=True)
    phone = String(maxsize=64)
    postal_code = String(maxsize=200)
    postal_code_regex = String(maxsize=200)
    languages_code = String(maxsize=200)
    neighbours_code = String(maxsize=200)
    equivalent_fips = String(maxsize=2)


class TimeZone(EntityType):
    """
    Entity type for timezone of geonames.
    See timeZones.txt
    """
    code = String(maxsize=1024, indexed=True)
    gmt = Float()
    dst = Float()
    raw_offset = Float()


class used_language(RelationDefinition):
    subject = 'Country'
    object = 'Language'
    cardinality = '**'


class neighbour_of(RelationDefinition):
    subject = 'Country'
    object = 'Country'
    cardinality = '**'
