# service-take-12

Resolves IANA service names (e.g. `http`, `ssh`) to their canonical port number and protocol using the platform's built-in `services(5)` file.

```python
from service_take_12 import ServiceResolver, ServiceInfo, resolve_service

resolver = ServiceResolver()
info = resolver.resolve("http", "tcp")
print(info.port, info.protocol)  # 80 tcp

# module-level shortcut (lazily cached):
print(resolve_service("ssh", "tcp").port)  # 22

# convenience: just the port
print(resolver.resolve_port("https"))  # 443 (defaults to tcp)
```

## Why

`socket.getservbyname` does the same job but is a thin C wrapper that offers no control over which services file is read and surfaces errors as `OSError` rather than a clean `None`. This library reads and parses the file in pure Python so the data source is explicit and lookups on missing names simply return `None`.

The trade-off: `ServiceResolver` reads and parses the entire file at construction time. For a single lookup that is more work than `socket.getservbyname`; for a loop doing thousands of lookups it avoids repeated syscalls and string parsing.

## Edge case

A service name can appear under multiple protocols on different ports (e.g. `domain` is 53/tcp and 53/udp, but `http` is 80/tcp and 80/udp). This resolver keys on `(name, protocol)` pairs, so you must supply the protocol. If you omit it, `"tcp"` is assumed — which will return `None` for a UDP-only service like `tftp`. When a name/protocol pair appears more than once in the file, the **first** entry wins, matching IANA's documented order.
