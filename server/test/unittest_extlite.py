import threading, os, time

from logilab.common.testlib import TestCase, unittest_main
from logilab.common.db import get_connection

class SQLiteTC(TestCase):
    sqlite_file = '_extlite_test.sqlite'

    def _cleanup(self):
        try:
            os.remove(self.sqlite_file)
        except:
            pass

    def setUp(self):
        self._cleanup()
        cnx1 = get_connection('sqlite', database=self.sqlite_file)
        cu = cnx1.cursor()
        cu.execute('CREATE TABLE toto(name integer);')
        cnx1.commit()
        cnx1.close()

    def tearDown(self):
        self._cleanup()

    def test(self):
        lock1 = threading.Lock()
        lock2 = threading.Lock()
        
        def run_thread():
            cnx2 = get_connection('sqlite', database=self.sqlite_file)
            lock1.acquire()
            cu = cnx2.cursor()
            cu.execute('SELECT name FROM toto')
            self.failIf(cu.fetchall())
            cnx2.commit()
            lock1.release()
            lock2.acquire()
            cu.execute('SELECT name FROM toto')
            self.failUnless(cu.fetchall())
            lock2.release()

        cnx1 = get_connection('sqlite', database=self.sqlite_file)
        lock1.acquire()
        lock2.acquire()
        thread = threading.Thread(target=run_thread)
        thread.start()
        cu = cnx1.cursor()
        cu.execute('SELECT name FROM toto')
        lock1.release()
        cnx1.commit()
        cu.execute("INSERT INTO toto(name) VALUES ('toto')")
        cnx1.commit()
        lock2.release()

if __name__ == '__main__':
    unittest_main()
