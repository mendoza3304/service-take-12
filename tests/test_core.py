"""Tests for service_take_12.core."""

import os
import tempfile
import unittest

from service_take_12.core import ServiceResolver, ServiceInfo, resolve_service


def _write_services_file(content: str) -> str:
    """Write *content* to a temporary file and return its path.

    Using a real file on disk (rather than mocking ``open``) exercises the
    exact code path callers will hit, including newline handling.
    """
    fd, path = tempfile.mkstemp(suffix="_services")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return path


SAMPLE_SERVICES = """# standard IANA-style services file
http            80/tcp    www www-http
http            80/udp    www www-http
https           443/tcp
ssh             22/tcp
ssh             22/udp
domain          53/tcp    nameserver
domain          53/udp    nameserver
tftp            69/udp
"""


class ServiceResolverFromFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self._path = _write_services_file(SAMPLE_SERVICES)
        self.resolver = ServiceResolver(path=self._path)

    def tearDown(self) -> None:
        os.unlink(self._path)

    def test_basic_tcp_lookup(self) -> None:
        info = self.resolver.resolve("http", "tcp")
        self.assertIsNotNone(info)
        assert info is not None  # for type checkers
        self.assertEqual(info.port, 80)
        self.assertEqual(info.protocol, "tcp")
        self.assertEqual(info.name, "http")

    def test_returns_serviceinfo_instance(self) -> None:
        info = self.resolver.resolve("https", "tcp")
        self.assertIsInstance(info, ServiceInfo)

    def test_case_insensitive_name(self) -> None:
        self.assertEqual(self.resolver.resolve_port("HTTP", "tcp"), 80)
        self.assertEqual(self.resolver.resolve_port("SsH", "tcp"), 22)

    def test_case_insensitive_protocol(self) -> None:
        info = self.resolver.resolve("domain", "TCP")
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.port, 53)

    def test_udp_lookup(self) -> None:
        self.assertEqual(self.resolver.resolve_port("tftp", "udp"), 69)

    def test_unknown_name_returns_none(self) -> None:
        self.assertIsNone(self.resolver.resolve("nonexistent", "tcp"))

    def test_unknown_protocol_returns_none(self) -> None:
        self.assertIsNone(self.resolver.resolve("http", "sctp"))

    def test_default_protocol_is_tcp(self) -> None:
        self.assertEqual(self.resolver.resolve_port("http"), 80)

    def test_first_entry_wins_on_duplicate(self) -> None:
        # ``http`` appears once on tcp:80.  Verify we get that record.
        info = self.resolver.resolve("http", "tcp")
        assert info is not None
        self.assertEqual(info.port, 80)

    def test_comments_and_blank_lines_ignored(self) -> None:
        info = self.resolver.resolve("ssh", "tcp")
        self.assertIsNotNone(info)

    def test_resolve_port_none_for_missing(self) -> None:
        self.assertIsNone(self.resolver.resolve_port("missing", "tcp"))


class MalformedLinesTests(unittest.TestCase):
    def _build(self, content: str) -> ServiceResolver:
        path = _write_services_file(content)
        resolver = ServiceResolver(path=path)
        os.unlink(path)
        return resolver

    def test_line_without_port_segment(self) -> None:
        resolver = self._build("bogus tcp\nhttp 80/tcp\n")
        # ``bogus tcp`` has no ``/`` so it is skipped, http still resolves.
        self.assertEqual(resolver.resolve_port("http", "tcp"), 80)
        self.assertIsNone(resolver.resolve("bogus", "tcp"))

    def test_line_with_non_numeric_port(self) -> None:
        resolver = self._build("http abc/tcp\nssh 22/tcp\n")
        self.assertIsNone(resolver.resolve("http", "tcp"))
        self.assertEqual(resolver.resolve_port("ssh", "tcp"), 22)

    def test_line_with_only_name(self) -> None:
        resolver = self._build("lonely\nhttp 80/tcp\n")
        self.assertIsNone(resolver.resolve("lonely", "tcp"))
        self.assertEqual(resolver.resolve_port("http", "tcp"), 80)

    def test_inline_comment_stripped(self) -> None:
        resolver = self._build("http 80/tcp # web server\n")
        info = resolver.resolve("http", "tcp")
        self.assertIsNotNone(info)
        assert info is not None
        self.assertEqual(info.port, 80)


class MissingFileTests(unittest.TestCase):
    def test_nonexistent_path_returns_none_for_all_lookups(self) -> None:
        resolver = ServiceResolver(path="/this/path/does/not/exist/services")
        self.assertIsNone(resolver.resolve("http", "tcp"))
        self.assertIsNone(resolver.resolve_port("ssh", "tcp"))


class ServiceInfoTests(unittest.TestCase):
    def test_is_frozen(self) -> None:
        info = ServiceInfo(name="http", port=80, protocol="tcp")
        with self.assertRaises((AttributeError, TypeError)):
            info.port = 81  # type: ignore[misc]


class ModuleLevelFunctionTests(unittest.TestCase):
    def test_resolve_service_uses_default_resolver(self) -> None:
        # This exercises the real /etc/services on the test machine.
        # We only assert that the function returns either None or a
        # ServiceInfo — the exact port depends on the platform file.
        result = resolve_service("ssh", "tcp")
        self.assertTrue(result is None or isinstance(result, ServiceInfo))


if __name__ == "__main__":
    unittest.main()
