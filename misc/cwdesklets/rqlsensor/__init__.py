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
"""

"""
import webbrowser
reload(webbrowser)

from sensor.Sensor import Sensor
from utils import datatypes, i18n

from cubicweb.dbapi import connect

_ = str

class RQLSensor(Sensor):

    def __init__(self, *args):
        global _; _ = i18n.Translator("rql-desklet")
        Sensor.__init__(self)
        # define configuration
        self._set_config_type("appid", datatypes.TYPE_STRING, "")
        self._set_config_type("user", datatypes.TYPE_STRING, "")
        self._set_config_type("passwd", datatypes.TYPE_SECRET_STRING, "")
        self._set_config_type("rql", datatypes.TYPE_STRING, "")
        self._set_config_type("url", datatypes.TYPE_STRING, "")
        self._set_config_type("delay", datatypes.TYPE_STRING, "600")
        # default timer
        self._add_timer(20, self.__update)

    def get_configurator(self):
        configurator = self._new_configurator()
        configurator.set_name(_("RQL"))
        configurator.add_title(_("CubicWeb source settings"))
        configurator.add_entry(_("ID",), "appid", _("The application id of this source"))
        configurator.add_entry(_("User",), "user", _("The user to connect to this source"))
        configurator.add_entry(_("Password",), "passwd", _("The user's password to connect to this source"))
        configurator.add_entry(_("URL",), "url", _("The url of the web interface for this source"))
        configurator.add_entry(_("RQL",), "rql", _("The rql query"))
        configurator.add_entry(_("Update interval",), "delay", _("Delay in seconds between updates"))
        return configurator


    def call_action(self, action, path, args=[]):
        index = path[-1]
        output = self._new_output()
#        import sys
#        print >>sys.stderr, action, path, args
        if action=="enter-line":
            # change background
            output.set('resultbg[%s]' % index, 'yellow')
        elif action=="leave-line":
            # change background
            output.set('resultbg[%s]' % index, 'black')
        elif action=="click-line":
            # open url
            output.set('resultbg[%s]' % index, 'black')
            webbrowser.open(self._urls[index])
        self._send_output(output)

    def __get_connection(self):
        try:
            return self._v_cnx
        except AttributeError:
            appid, user, passwd = self._get_config("appid"), self._get_config("user"), self._get_config("passwd")
            cnx = connect(database=appid, login=user, password=passwd)
            self._v_cnx = cnx
            return cnx

    def __run_query(self, output):
        base = self._get_config('url')
        rql = self._get_config('rql')
        cnx = self.__get_connection()
        cursor = cnx.cursor()
        try:
            rset = cursor.execute(rql)
        except:
            del self._v_cnx
            raise
        self._urls = []
        output.set('layout', 'vertical, 14')
        output.set('length', rset.rowcount)
        i = 0
        for line in rset:
            output.set('result[%s]' % i, ', '.join([str(v) for v in line[1:]]))
            output.set('resultbg[%s]' % i, 'black')
            try:
                self._urls.append(base % 'Any X WHERE X eid %s' % line[0])
            except:
                self._urls.append('')
            i += 1

    def __update(self):
        output = self._new_output()
        try:
            self.__run_query(output)
        except Exception, ex:
            import traceback
            traceback.print_exc()
            output.set('layout', 'vertical, 10')
            output.set('length', 1)
            output.set('result[0]', str(ex))
        self._send_output(output)
        self._add_timer(int(self._get_config('delay'))*1000, self.__update)


def new_sensor(args):
    return RQLSensor(*args)
