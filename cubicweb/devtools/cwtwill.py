# copyright 2003-2010 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""cubicweb extensions for twill

"""

import re
from urllib.parse import quote

from twill import commands as twc

# convenience / consistency renaming
has_text = twc.find
hasnt_text = twc.notfind


# specific commands
_LINK = re.compile('<a.*?href="(.*?)".*?>(.*?)</a>', re.I | re.S)

def has_link(text, url=''):
    browser = twc.get_browser()
    html = browser.get_html()
    if html:
        for match in _LINK.finditer(html):
            linkurl = match.group(1)
            linktext = match.group(2)
            if linktext == text:
                # if url is specified linkurl must match
                if url and linkurl != url:
                    continue
                return
    raise AssertionError('link %s (%s) not found' % (text, url))


def view(rql, vid=''):
    """
    >> view 'Project P'

    apply <vid> to <rql>'s rset
    """
    if vid:
        twc.go('view?rql=%s&vid=%s' % (quote(rql), vid))
    else:
        twc.go('view?rql=%s' % quote(rql))

def create(etype):
    """
    >> create Project

    go to <etype>'s creation page
    """
    twc.go('view?etype=%s&vid=creation' % etype)

def edit(rql):
    """
    >> edit "Project P WHERE P eid 123"

    calls edition view for <rql>
    """
    twc.go('view?rql=%s&vid=edition' % quote(rql))




def setvalue(formname, fieldname, value):
    """
    >> setvalue entityForm name pylint

    sets the field's value in the form
    <forname> should either be the form's index, the form's name
    or the form's id
    """
    browser = twc.get_browser()
    form = browser.get_form(formname)
    if form is None:
        # try to find if one of the forms has <formname> as id
        for index, form in enumerate(browser._browser.forms()):
            # forms in cubicweb don't always have a name
            if form.attrs.get('id') == formname:
                # browser.get_form_field knows how to deal with form index
                formname = str(index+1)
                break
        else:
            raise ValueError('could not find form named <%s>' % formname)
    eid = browser.get_form_field(form, 'eid').value
    twc.formvalue(formname, '%s:%s' % (fieldname, eid), value)


def submitform(formname, submit_button=None):
    """
    >> submitform entityForm

    Submit the form named entityForm. This is useful when the form is pre-filed
    and we only want to click on submit.
    (The original submit command chooses the form to submit according to the last
    formvalue instruction)
    """
    browser = twc.get_browser()
    form = browser.get_form(formname)
    if form is None:
        # try to find if one of the forms has <formname> as id
        for form in browser._browser.forms():
            # forms in cubicweb don't always have a name
            if form.attrs.get('id') == formname:
                break
        else:
            raise ValueError('could not find form named <%s>' % formname)
    browser._browser.form = form
    browser.submit(submit_button)


# missing actions: delete, copy, changeview
