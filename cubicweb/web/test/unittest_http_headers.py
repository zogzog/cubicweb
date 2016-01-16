import unittest

from cubicweb.web import http_headers


class TestGenerators(unittest.TestCase):
    def test_generate_true_false(self):
        for v in (True, 1, 'true', 'True', 'TRUE'):
            self.assertEqual('true', http_headers.generateTrueFalse(v))
        for v in (False, 0, 'false', 'False', 'FALSE'):
            self.assertEqual('false', http_headers.generateTrueFalse(v))

        with self.assertRaises(ValueError):
            http_headers.generateTrueFalse('any value')

if __name__ == '__main__':
    from unittest import main
    main()
