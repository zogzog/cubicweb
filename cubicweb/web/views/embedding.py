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
"""Objects interacting together to provides the external page embeding
functionality.
"""

from logilab.common.deprecation import class_moved, moved

try:
    from cubes.embed.views import *

    IEmbedableAdapter = class_moved(IEmbedableAdapter, message='[3.17] IEmbedableAdapter moved to cubes.embed.views')
    ExternalTemplate = class_moved(ExternalTemplate, message='[3.17] IEmbedableAdapter moved to cubes.embed.views')
    EmbedController = class_moved(EmbedController, message='[3.17] IEmbedableAdapter moved to cubes.embed.views')
    entity_has_embedable_url = moved('cubes.embed.views', 'entity_has_embedable_url')
    EmbedAction = class_moved(EmbedAction, message='[3.17] EmbedAction moved to cubes.embed.views')
    replace_href = class_moved(replace_href, message='[3.17] replace_href moved to cubes.embed.views')
    embed_external_page = moved('cubes.embed.views', 'embed_external_page')
    absolutize_links = class_moved(absolutize_links, message='[3.17] absolutize_links moved to cubes.embed.views')
    prefix_links = moved('cubes.embed.views', 'prefix_links')
except ImportError:
    from cubicweb.web import LOGGER
    LOGGER.warning('[3.17] embedding extracted to cube embed that was not found. try installing it.')
