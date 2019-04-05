# copyright 2003-2011 LOGILAB S.A. (Paris, FRANCE), all rights reserved.
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
"""Simple captcha library, based on PIL. Monkey patch functions in this module
if you want something better...
"""



from random import randint, choice
from io import BytesIO

from PIL import Image, ImageFont, ImageDraw, ImageFilter


from time import time

from cubicweb import tags
from cubicweb.web import ProcessFormError, formwidgets as fw


def pil_captcha(text, fontfile, fontsize):
    """Generate a captcha image. Return a PIL image object.

    adapted from http://code.activestate.com/recipes/440588/
    """
    # randomly select the foreground color
    fgcolor = (randint(100, 256), randint(100, 256), randint(100, 256))
    # create a font object
    font = ImageFont.truetype(fontfile, fontsize)
    # determine dimensions of the text
    dim = font.getsize(text)
    # create a new image slightly larger that the text
    img = Image.new('RGB', (dim[0]+15, dim[1]+5), 0)
    draw = ImageDraw.Draw(img)
    # draw 100 random colored boxes on the background
    x, y = img.size
    for num in range(100):
        fill = (randint(0, 100), randint(0, 100), randint(0, 100))
        draw.rectangle((randint(0, x), randint(0, y),
                        randint(0, x), randint(0, y)),
                       fill=fill)
    # add the text to the image
    # we add a trailing space to prevent the last char to be truncated
    draw.text((3, 3), text + ' ', font=font, fill=fgcolor)
    img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    return img


def captcha(fontfile, fontsize, size=5, format='JPEG'):
    """Generate an arbitrary text, return it together with a buffer containing
    the captcha image for the text
    """
    text = u''.join(choice('QWERTYUOPASDFGHJKLZXCVBNM') for i in range(size))
    img = pil_captcha(text, fontfile, fontsize)
    out = BytesIO()
    img.save(out, format)
    out.seek(0)
    return text, out


class CaptchaWidget(fw.TextInput):
    def render(self, form, field, renderer=None):
        # t=int(time()*100) to make sure img is not cached
        src = form._cw.build_url('view', vid='captcha', t=int(time()*100),
                                 captchakey=field.input_name(form))
        img = tags.img(src=src, alt=u'captcha')
        img = u'<div class="captcha">%s</div>' % img
        return img + super(CaptchaWidget, self).render(form, field, renderer)

    def process_field_data(self, form, field):
        captcha = form._cw.session.data.pop(field.input_name(form), None)
        val = super(CaptchaWidget, self).process_field_data(form, field)
        if val is None:
            return val # required will be checked by field
        if captcha is None:
            msg = form._cw._('unable to check captcha, please try again')
            raise ProcessFormError(msg)
        elif val.lower() != captcha.lower():
            msg = form._cw._('incorrect captcha value')
            raise ProcessFormError(msg)
        return val
