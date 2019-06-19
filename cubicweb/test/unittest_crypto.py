from unittest import TestCase

from cubicweb import crypto


class CryptoTC(TestCase):

    def test_encrypt_decrypt_roundtrip(self):
        data = {'a': u'ah', 'b': [1, 2]}
        seed = 's' * 16
        crypted = crypto.encrypt(data, seed)
        decrypted = crypto.decrypt(crypted, seed)
        self.assertEqual(decrypted, data)


if __name__ == '__main__':
    import unittest
    unittest.main()
