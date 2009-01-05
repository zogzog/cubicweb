"""
usage: python exlog.py < rql.log

will print out the following table

  total execution time || number of occurences || rql query

sorted by descending total execution time

chances are the lines at the top are the ones that will bring
the higher benefit after optimisation. Start there.
"""
import sys, re

def run():
    requests = {}
    for line in sys.stdin:
        if not ' WHERE ' in line:
            continue
        #sys.stderr.write( line )
        rql, time = line.split('--')
        rql = re.sub("(\'\w+': \d*)", '', rql)
        req = requests.setdefault(rql, [])
        time.strip()
        chunks = time.split()
        cputime = float(chunks[-3])
        req.append( cputime )

    stat = []
    for rql, times in requests.items():
        stat.append( (sum(times), len(times), rql) )

    stat.sort()
    stat.reverse()
    for time, occ, rql in stat:
        print time, occ, rql

if __name__ == '__main__':
    run()
