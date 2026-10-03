import os
import unittest
from unittest.mock import patch

from tools.config_generator import (
    DEFAULT_CONFIG,
    ENV_OVERRIDES,
    SENSITIVE_KEYS,
    generate_config,
    mask_sensitive,
    merge_config,
)


class ConfigGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.clean_environment = patch.dict(os.environ, {}, clear=True)
        self.clean_environment.start()
        self.addCleanup(self.clean_environment.stop)

    def test_development_and_production_overrides(self):
        development = generate_config("development")
        production = generate_config("production")

        self.assertEqual(development["app"]["environment"], "development")
        self.assertTrue(development["app"]["debug"])
        self.assertEqual(development["database"]["name"], "tent_dev")
        self.assertEqual(development["market"]["rate_limit_per_second"], 1000)
        self.assertEqual(production["app"]["environment"], "production")
        self.assertFalse(production["app"]["debug"])
        self.assertEqual(production["database"]["name"], "tent_production")
        self.assertEqual(production["database"]["pool_max"], 50)
        self.assertTrue(production["auth"]["mfa_required"])

    def test_recursive_merge_preserves_keys_and_does_not_mutate_inputs(self):
        base = {"nested": {"keep": {"base": 1}, "replace": [1]}, "top": 2}
        override = {"nested": {"keep": {"extra": 3}, "replace": [4]}}

        result = merge_config(base, override)
        self.assertEqual(result, {
            "nested": {"keep": {"base": 1, "extra": 3}, "replace": [4]},
            "top": 2,
        })

        result["nested"]["keep"]["base"] = 99
        result["nested"]["replace"].append(5)
        self.assertEqual(base, {"nested": {"keep": {"base": 1}, "replace": [1]}, "top": 2})
        self.assertEqual(override, {"nested": {"keep": {"extra": 3}, "replace": [4]}})

    def test_generate_config_returns_independent_nested_data(self):
        generated = generate_config("development")
        generated["market"]["fees"]["maker"] = 50
        generated["market"]["rate_limit_per_second"] = 1
        generated["kafka"]["brokers"].append("example:9092")

        self.assertEqual(DEFAULT_CONFIG["market"]["fees"]["maker"], 0.001)
        self.assertEqual(DEFAULT_CONFIG["kafka"]["brokers"], ["localhost:9092"])
        self.assertEqual(ENV_OVERRIDES["development"]["market"]["rate_limit_per_second"], 1000)

    def test_sensitive_values_are_masked_and_safe_values_remain(self):
        source = {
            "database": {"password": "db-secret", "host": "db.internal"},
            "redis": {"password": "redis-secret", "port": 6379},
            "auth": {"jwt_secret": "jwt-secret", "jwt_expiry_minutes": 60},
        }

        masked = mask_sensitive(source)
        self.assertEqual(masked["database"]["password"], "***REDACTED***")
        self.assertEqual(masked["redis"]["password"], "***REDACTED***")
        self.assertEqual(masked["auth"]["jwt_secret"], "***REDACTED***")
        self.assertEqual(masked["database"]["host"], "db.internal")
        self.assertEqual(masked["redis"]["port"], 6379)
        self.assertEqual(masked["auth"]["jwt_expiry_minutes"], 60)
        self.assertEqual(source["database"]["password"], "db-secret")

    def test_masking_does_not_alias_safe_nested_lists(self):
        source = generate_config("development")

        masked = mask_sensitive(source)
        masked["market"]["allowed_instruments"].append("BTC-USD")

        self.assertEqual(source["market"]["allowed_instruments"], ["*"])

    def test_sensitive_key_list_has_no_duplicates(self):
        self.assertEqual(len(SENSITIVE_KEYS), len(set(SENSITIVE_KEYS)))
        self.assertEqual(SENSITIVE_KEYS, [
            "database.password", "redis.password", "auth.jwt_secret",
        ])


if __name__ == "__main__":
    unittest.main()
