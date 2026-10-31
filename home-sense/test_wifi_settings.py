import unittest
from tools.check_wifi_settings import read_settings, validate, FIELDS

class WifiSettingsTests(unittest.TestCase):
    def settings(self, url):
        return dict(zip(FIELDS, ('demo', '', 'sensor-id', 'private-token', url, 'invalid-ca')))

    def test_parser_supports_multiline_ca_and_does_not_evaluate_code(self):
        source = '\n'.join('#define '+name+' "value"' for name in FIELDS[:-1])
        source += '\n#define HAVEN_ROOT_CA R"PEM(line1\nline2)PEM"'
        self.assertEqual(read_settings(source)['HAVEN_ROOT_CA'], 'line1\nline2')
        with self.assertRaises(ValueError):
            read_settings(source.replace('"value"', 'getSecret()'))

    def test_unreachable_and_plaintext_addresses_rejected_without_secrets(self):
        for url in ('https://127.0.0.1:8768/api/wifi/exchange',
                    'https://localhost:8768/api/wifi/exchange',
                    'https://[::1]:8768/api/wifi/exchange',
                    'http://haven.local/api/wifi/exchange'):
            errors = validate(self.settings(url))
            self.assertGreater(len(errors), 1)
            self.assertNotIn('private-token', '\n'.join(errors))

    def test_private_lan_url_permitted_but_invalid_ca_rejected(self):
        self.assertEqual(len(validate(self.settings('https://192.168.1.5:8768/api/wifi/exchange'))), 1)
