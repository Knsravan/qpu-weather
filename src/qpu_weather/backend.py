"""Backend access: real IBM QPUs by default, a noisy local fake only for development."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class BackendHandle:
    backend: object  # what circuits are executed on
    name: str
    simulated: bool
    target_backend: object = None  # what circuits are transpiled against

    def __post_init__(self):
        if self.target_backend is None:
            self.target_backend = self.backend


def _connect_service(token: str | None, instance: str | None):
    """Connect to IBM. `instance` (a CRN or name) is optional; IBM may require it."""
    from qiskit_ibm_runtime import QiskitRuntimeService

    if not token:
        return QiskitRuntimeService()
    kwargs = {"channel": "ibm_quantum_platform", "token": token}
    if instance:
        kwargs["instance"] = instance
    return QiskitRuntimeService(**kwargs)


def check_quota(service) -> None:
    """Stop early if IBM reports no QPU time left. Never blocks if usage can't be read."""
    try:
        remaining = service.usage().get("usage_remaining_seconds")
    except Exception:
        return
    if remaining is not None and remaining <= 0:
        raise SystemExit(
            "IBM instance has no QPU time left (usage_remaining_seconds=0); "
            "it resets when IBM makes more time available. Stopping before submitting jobs."
        )


def get_backend(name: str | None = None, simulate: bool = False) -> BackendHandle:
    """Return a backend.

    Real mode needs an IBM Quantum token in the IBM_QUANTUM_TOKEN environment
    variable (or a previously saved QiskitRuntimeService account). An optional
    IBM_INSTANCE variable selects the IBM instance (CRN) if one is required. If `name` is
    None the least busy operational real device is used.

    Simulate mode builds a noisy local simulator from a fake IBM device. It exists
    so the code can be tested without QPU time. Its output is always tagged
    simulated and is never meant to be published as a result.
    """
    if simulate:
        from qiskit_aer import AerSimulator
        from qiskit_ibm_runtime.fake_provider import FakeLagosV2

        fake = FakeLagosV2()
        sim = AerSimulator.from_backend(fake)
        return BackendHandle(sim, "simulated_" + fake.name, True, target_backend=fake)

    from qiskit_ibm_runtime import QiskitRuntimeService

    service = _connect_service(os.environ.get("IBM_QUANTUM_TOKEN"), os.environ.get("IBM_INSTANCE"))
    if name:
        backend = service.backend(name)
    else:
        backend = service.least_busy(operational=True, simulator=False)
    check_quota(service)
    return BackendHandle(backend, backend.name, False)
