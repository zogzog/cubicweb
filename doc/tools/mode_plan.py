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
>>> from mode_plan import *
>>> ls()
<list of directory content>
>>> ren('A01','A03')
rename A010-joe.en.txt to A030-joe.en.txt
accept [y/N]?
"""

def ren(a,b):
    names = glob.glob('%s*'%a)
    for name in names :
        print 'rename %s to %s' % (name, name.replace(a,b))
    if raw_input('accept [y/N]?').lower() =='y':
        for name in names:
            os.system('hg mv %s %s' % (name, name.replace(a,b)))


def ls(): print '\n'.join(sorted(os.listdir('.')))

def move():
    filenames = []
    for name in sorted(os.listdir('.')):
        num = name[:2]
        if num.isdigit():
            filenames.append( (int(num), name) )


    #print filenames

    for num, name in filenames:
        if num >= start:
            print 'hg mv %s %2i%s' %(name,num+1,name[2:])
