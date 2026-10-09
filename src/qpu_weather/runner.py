"""Run circuits and return counts, on a real IBM backend or a local simulator."""

from __future__ import annotations

from qiskit import QuantumCircuit
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager

CREG = "c"


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
    result = job.result()
    return [getattr(result[i].data, CREG).get_counts() for i in range(len(circuits))], job.job_id()


def job_info(ret):
    """Normalize run_counts() output to (counts_list, job_id)."""
    if isinstance(ret, tuple):
        return ret
    return ret, None
