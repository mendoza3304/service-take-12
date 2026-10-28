"""Resolves IANA service names to canonical port numbers and protocols."""

from .core import ServiceResolver, ServiceInfo, resolve_service

__all__ = ["ServiceResolver", "ServiceInfo", "resolve_service"]
