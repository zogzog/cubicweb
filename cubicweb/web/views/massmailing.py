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
"""Mass mailing handling: send mail to entities adaptable to IEmailable"""

try:
    from cubes.massmailing.views import (SendEmailAction,
                                         recipient_vocabulary,
                                         MassMailingForm,
                                         MassMailingFormRenderer,
                                         MassMailingFormView,
                                         SendMailController)


    from logilab.common.deprecation import class_moved, moved

    msg = '[3.17] cubicweb.web.views.massmailing moved to cubes.massmailing.views'
    SendEmailAction = class_moved(SendEmailAction, message=msg)
    recipient_vocabulary = moved('cubes.massmailing.views', 'recipient_vocabulary')
    MassMailingForm = class_moved(MassMailingForm, message=msg)
    MassMailingFormRenderer = class_moved(MassMailingFormRenderer, message=msg)
    MassMailingFormView = class_moved(MassMailingFormView, message=msg)
    SendMailController = class_moved(SendMailController, message=msg)
except ImportError:
    from cubicweb.web import LOGGER
    LOGGER.warning('[3.17] massmailing extracted to cube massmailing that was not found. try installing it.')
