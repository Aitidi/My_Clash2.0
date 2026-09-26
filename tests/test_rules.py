import unittest

from my_clash.rules import ConfigError, parse_rules


class RuleParsingTests(unittest.TestCase):
    def test_normalizes_mixed_legacy_formats_without_reordering(self):
        result = parse_rules("\ufeff# comment\n[Rule]\nDOMAIN, a.example\nDOMAIN-SUFFIX,b.example\nDOMAIN,a.example\n")
        self.assertEqual(result.rules, ("DOMAIN,a.example", "DOMAIN-SUFFIX,b.example"))
        self.assertEqual(result.duplicates, 1)

    def test_payload(self):
        self.assertEqual(parse_rules("payload:\n  - DOMAIN,a.example\n").rules, ("DOMAIN,a.example",))

    def test_regex_with_comma_is_not_split(self):
        value = "URL-REGEX,^https://example.com/[a-z]{1,3}$"
        self.assertEqual(parse_rules(value).rules, (value,))

    def test_process_name_spaces_and_ip_options_survive(self):
        values = "PROCESS-NAME,WebTorrent Helper.exe\nIP-CIDR,10.0.0.1/24,no-resolve\nIP-CIDR6,::1/128"
        self.assertEqual(parse_rules(values).rules, tuple(values.splitlines()))

    def test_rejects_invalid_rules_with_location(self):
        for text in ("DOMAIN,", "DOMAIN,a.example,DIRECT", "DOMAIN,a.example,no-resolve",
                     "IP-CIDR,broken/24", "IP-CIDR6,1.1.1.1/32", "DOMAIN,https://a.com",
                     "UNKNOWN,a", "[Other]", "DOMAIN,a.com,one,two"):
            with self.subTest(text=text), self.assertRaisesRegex(ConfigError, "test.list:1"):
                parse_rules(text, "test.list")

    def test_rejects_empty_and_invalid_payload(self):
        for text in ("# only comments", "payload:\n - 12", "payload:\n  other: x", "payload:\n - DOMAIN,a\nother: 1"):
            with self.subTest(text=text), self.assertRaises(ConfigError):
                parse_rules(text)
