import threading, os, time

from logilab.common.testlib import TestCase, unittest_main
from logilab.common.db import get_connection

class SQLiteTC(TestCase):
    sqlite_file = '_extlite_test.sqlite'
    def setUp(self):
        cnx1 = get_connection('sqlite', database=self.sqlite_file)
        cu = cnx1.cursor()
        cu.execute('CREATE TABLE toto(name integer);')
        cnx1.commit()
        cnx1.close()

    def tearDown(self):
        try:
            os.remove(self.sqlite_file)
        except:
            pass

    def test(self):
        lock = threading.Lock()

        def run_thread():
            cnx2 = get_connection('sqlite', database=self.sqlite_file)
            lock.acquire()
            cu = cnx2.cursor()
            cu.execute('SELECT name FROM toto')
            self.failIf(cu.fetchall())
            cnx2.commit()
            lock.release()
            time.sleep(0.1)
            lock.acquire()
            cu.execute('SELECT name FROM toto')
            self.failUnless(cu.fetchall())
            lock.release()

        cnx1 = get_connection('sqlite', database=self.sqlite_file)
        lock.acquire()
        thread = threading.Thread(target=run_thread)
        thread.start()
        cu = cnx1.cursor()
        cu.execute('SELECT name FROM toto')
        lock.release()
        time.sleep(0.1)
        cnx1.commit()
        lock.acquire()
        cu.execute("INSERT INTO toto(name) VALUES ('toto')")
        cnx1.commit()
        lock.release()

if __name__ == '__main__':
    unittest_main()
