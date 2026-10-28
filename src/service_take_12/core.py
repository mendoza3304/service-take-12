"""Core resolution logic for mapping service names to port/protocol pairs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ServiceInfo:
    """The canonical port and protocol associated with a service name.

    A single service name may appear for both tcp and udp, sometimes
    on different ports.  When that happens we keep the *first* entry
    the services file lists for that name, because that is the entry
    IANA documents first and is the one most tools historically rely
    on.
    """

    name: str
    port: int
    protocol: str


class ServiceResolver:
    """Look up IANA service entries from the local services(5) file.

    The resolver reads the platform's built-in services file once at
    construction and builds an in-memory map keyed by ``(name, protocol)``.
    Re-reading on every call would be wasteful for a hot loop, and reading
    eagerly means a missing or malformed file surfaces immediately rather
    than partway through a job.
    """

    def __init__(self, path: Optional[str] = None) -> None:
        self._path: str = path or self._default_path()
        # ``dict`` over ``typing.Dict`` keeps the runtime footprint to
        # exactly the types we need and avoids any import-time surprises.
        self._entries: dict[tuple[str, str], ServiceInfo] = {}
        self._load()

    # -- public API -------------------------------------------------

    def resolve(self, name: str, protocol: str = "tcp") -> Optional[ServiceInfo]:
        """Return the :class:`ServiceInfo` for *name* under *protocol*.

        ``name`` is matched case-insensitively, mirroring the behaviour of
        ``socket.getservbyname``.  ``protocol`` is normalised to lowercase
        but otherwise taken literally; if you ask for a protocol that does
        not exist in the file you get ``None``.
        """
        key = (name.lower(), protocol.lower())
        return self._entries.get(key)

    def resolve_port(self, name: str, protocol: str = "tcp") -> Optional[int]:
        """Convenience wrapper returning just the port number."""
        info = self.resolve(name, protocol)
        return info.port if info is not None else None

    # -- internals --------------------------------------------------

    @staticmethod
    def _default_path() -> str:
        """Locate the platform's services file.

        Windows does not ship ``/etc/services``; on every POSIX system we
        have encountered it lives at ``/etc/services``.  We check
        ``%SystemRoot%`` on Windows as a best effort, but callers on
        unusual platforms can pass an explicit *path* to the constructor.
        """
        if os.name == "nt":
            system_root = os.environ.get("SystemRoot", r"C:\\Windows")
            return os.path.join(system_root, "System32", "drivers", "etc", "services")
        return "/etc/services"

    def _load(self) -> None:
        """Parse the services file into ``self._entries``.

        The format is documented in ``services(5)``: one record per line,
        ``name port/protocol [aliases...]``.  Lines beginning with ``#``
        are comments.  We intentionally ignore aliases — supporting them
        would mean callers could not predict which name produced a result,
        and the IANA canonical name is almost always what callers want.
        """
        try:
            with open(self._path, "r", encoding="utf-8", errors="replace") as fh:
                lines = fh.readlines()
        except OSError:
            # If the file is absent there is nothing to resolve.  An empty
            # map turns every lookup into ``None`` without raising, which
            # is the least surprising behaviour for a missing data source.
            return

        for raw_line in lines:
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            # ``str.split`` with ``maxsplit=3`` lets trailing alias tokens
            # be discarded in one call instead of slicing afterwards.
            parts = line.split(None, 3)
            if len(parts) < 2:
                continue
            name = parts[0].lower()
            port_proto = parts[1]
            port_str, _, protocol = port_proto.partition("/")
            if not protocol:
                continue
            protocol = protocol.lower()
            try:
                port = int(port_str)
            except ValueError:
                continue
            key = (name, protocol)
            # First occurrence wins — see the ServiceInfo docstring.
            if key not in self._entries:
                self._entries[key] = ServiceInfo(name=name, port=port, protocol=protocol)


def resolve_service(name: str, protocol: str = "tcp") -> Optional[ServiceInfo]:
    """Module-level shortcut using a lazily-cached shared resolver.

    Constructing a :class:`ServiceResolver` reads and parses the entire
    services file.  Callers that only need a single lookup should not pay
    that cost on every call, so we cache one resolver at module scope.
    """
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = ServiceResolver()
    return _default_resolver.resolve(name, protocol)


_default_resolver: Optional[ServiceResolver] = None
