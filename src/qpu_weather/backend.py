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


def get_backend(name: str | None = None, simulate: bool = False) -> BackendHandle:
    """Return a backend.

    Real mode needs an IBM Quantum token in the IBM_QUANTUM_TOKEN environment
    variable (or a previously saved QiskitRuntimeService account). If `name` is
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

    token = os.environ.get("IBM_QUANTUM_TOKEN")
    if token:
        service = QiskitRuntimeService(channel="ibm_quantum_platform", token=token)
    else:
        service = QiskitRuntimeService()
    if name:
        backend = service.backend(name)
    else:
        backend = service.least_busy(operational=True, simulator=False)
    return BackendHandle(backend, backend.name, False)
