"""Run circuits and return counts, on a real IBM backend or a local simulator."""

from __future__ import annotations

from qiskit import QuantumCircuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

import time

CREG = "c"
QUEUE_TIMEOUT_S = 600  # give up if a job has not started running after 10 minutes


class QueueTimeout(RuntimeError):
    """A job never left the queue (busy device, or the instance is out of QPU time)."""


def wait_until_running(job, timeout_s=QUEUE_TIMEOUT_S, poll_s=15, sleep=time.sleep, clock=time.monotonic):
    """Return once `job` is running/finished; cancel it and raise QueueTimeout if it stays queued."""
    start = clock()
    while True:
        status = str(getattr(job.status(), "name", job.status())).upper()
        if status not in ("INITIALIZING", "QUEUED", "VALIDATING"):
            return status
        if clock() - start > timeout_s:
            try:
                job.cancel()
            except Exception:
                pass
            raise QueueTimeout(
                f"job {job.job_id()} still {status} after {timeout_s}s; cancelled it. "
                "The device may be busy, or the IBM instance may be out of QPU time "
                "(check the instance usage page)."
            )
        sleep(poll_s)


def transpile_with_layout(circuits, backend, layout, optimization_level=1):
    """Transpile onto physical qubits `layout` (logical i -> physical layout[i])."""
    pm = generate_preset_pass_manager(
        optimization_level=optimization_level,
        backend=backend,
        initial_layout=layout,
        seed_transpiler=7,
    )
    return pm.run(circuits)


def translate_only(circuits, backend):
    """Re-express gates in the device's native set WITHOUT optimising.

    Needed after folding: inverting native gates can produce non-native ones (e.g. sxdg).
    Circuits must already be physical (full device width). Level 0 never cancels gates.
    """
    pm = generate_preset_pass_manager(optimization_level=0, backend=backend, seed_transpiler=7)
    return pm.run(circuits)


def run_counts(backend, circuits: list[QuantumCircuit], shots: int, simulated: bool):
    """Execute already-transpiled circuits. Returns one counts dict per circuit.

    Bitstring convention (Qiskit): classical bit 0 is the RIGHTMOST character.
    """
    if simulated:
        job = backend.run(circuits, shots=shots)
        result = job.result()
        return [result.get_counts(i) for i in range(len(circuits))]

    from qiskit_ibm_runtime import SamplerV2

    sampler = SamplerV2(mode=backend)
    job = sampler.run(circuits, shots=shots)
    wait_until_running(job)
    result = job.result()
    return [getattr(result[i].data, CREG).get_counts() for i in range(len(circuits))], job.job_id()


def job_info(ret):
    """Normalize run_counts() output to (counts_list, job_id)."""
    if isinstance(ret, tuple):
        return ret
    return ret, None
