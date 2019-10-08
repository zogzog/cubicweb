# copyright 2019 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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

"""
Debug view for pyramid debug toolbar and others to help development
"""

import os

from pyramid.response import Response
from mako.template import Template

from cubicweb.misc.source_highlight import highlight_html, generate_css, has_pygments


DEBUG_DISPLAY_SOURCE_CODE_PATH = '_debug_display_source_code'


def debug_display_source_code(request):
    """
    This view display a python source file content for making debugging easier.

    It is only activated on debug mode (-D) for pyramid during development.

    It will uses pygment if installed to colorize the source code.
    """

    if "file" not in request.params:
        return Response('Error: you should have end up on this page following a link in the '
                        'pyramid debug toolbar with the correct parameters.')

    source_code_file = request.params["file"]

    if not os.path.exists(source_code_file):
        return Response("Error: file '%s' doesn't exist on the filesystem." % source_code_file)

    try:
        content = open(source_code_file, "r").read()
    except Exception as e:
        return Response("Error: while opening file '%s' got the error: %s" % (source_code_file, e))

    lines = []
    line_begin = request.params.get("line", None)
    if line_begin:
        line_end = request.params.get("end", line_begin)
        lines = list(range(int(line_begin), int(line_end) + 1))

    this_file_directory = os.path.split(os.path.realpath(__file__))[0]
    template_filename = os.path.join(this_file_directory,
                                     "debug_toolbar_templates/debug_source_code.mako")

    html = Template(filename=template_filename).render(
        file_path=source_code_file,
        content=content,
        has_pygments=has_pygments,
        highlight_html=highlight_html,
        css=generate_css(),
        lines=lines,
    )

    return Response(html)
