from django.test import TestCase

from .models import (
    build_service_tenant_domain,
    normalize_domain,
    normalize_subdomain_label,
    parse_service_tenant_domain,
)


class TenantDomainModelTests(TestCase):
    def test_normalize_domain_strips_scheme_and_port(self):
        self.assertEqual(normalize_domain('https://App.Example.COM:8443/path'), 'app.example.com')

    def test_normalize_subdomain_label(self):
        self.assertEqual(normalize_subdomain_label(' Print Service__A '), 'print-service-a')

    def test_build_service_tenant_domain(self):
        self.assertEqual(
            build_service_tenant_domain('printing', 'tenant-alpha', 'platform.example.com'),
            'printing.tenant-alpha.platform.example.com',
        )

    def test_parse_service_tenant_domain(self):
        parsed = parse_service_tenant_domain(
            'printing.tenant-alpha.platform.example.com',
            'platform.example.com',
        )
        self.assertEqual(parsed, ('printing', 'tenant-alpha'))

    def test_parse_service_tenant_domain_rejects_non_matching_base(self):
        self.assertIsNone(
            parse_service_tenant_domain(
                'printing.tenant-alpha.other.example.com',
                'platform.example.com',
            )
        )
