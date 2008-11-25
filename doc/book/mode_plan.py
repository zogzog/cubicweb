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
