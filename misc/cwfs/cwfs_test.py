from logilab.common.testlib import TestCase, unittest_main

import cubicwebfs
import sre

def spec_parser(filename) :
    """
    extract tests from specification
    """
    sections = []
    buffer = ""
    in_section = False
    for line in file(filename) :
        if line.startswith('Test::'):
            in_section = True
            buffer = ""
        elif in_section :
            if line.startswith("  ") or not line.strip() :
                buffer += line.lstrip()
            else :
                sections.append(buffer)
                in_section = False
    tests = []
    for section in sections :
        subsections = [t for t in section.strip().split('$ ls') if t]
        for subsection in subsections :
            path, results = subsection.splitlines()[0], subsection.splitlines()[1:]
            path = path.strip()
            items = set([i for i in sre.split('[\t\n]', '\n'.join(results)) if i])
            tests.append((path, items))
    return tests

tests = spec_parser("cubicwebfs-spec.txt")

class monTC(TestCase) :
    pass

for index, (path, results) in enumerate(tests) :
    def f(self, p=path, r=results) :
        res = set(cubicwebfs.ls(p))
        self.assertEqual(r, res) #, 'en trop %s\nmanque %s' % (r-results,results-r))
    f.__doc__ = "%s %s"%(index,path)
    setattr(monTC,'test_%s'%index,f)

if __name__ == '__main__':
    unittest_main()
