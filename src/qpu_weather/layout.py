"""Pick the healthiest chain of connected qubits, using MEASURED qubit errors."""

from __future__ import annotations

TWO_Q_GATES = ("ecr", "cz", "cx")


def edge_errors(target) -> dict[tuple[int, int], float]:
    """Vendor-reported 2-qubit gate error per undirected edge (experiment.py overrides with measured)."""
    out: dict[tuple[int, int], float] = {}
    for gate in TWO_Q_GATES:
        if gate not in target.operation_names:
            continue
        for qargs, props in target[gate].items():
            if qargs is None or len(qargs) != 2:
                continue
            a, b = sorted(qargs)
            err = props.error if props is not None and props.error is not None else 0.05
            out[(a, b)] = min(err, out.get((a, b), err))
        break
    return out


def _adjacency(edges):
    adj: dict[int, list[int]] = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    return {k: sorted(v) for k, v in adj.items()}


def all_chains(edges, n: int):
    """Every simple path of n qubits, in deterministic (qubit-index) order."""
    adj = _adjacency(edges)

    def dfs(path):
        if len(path) == n:
            yield list(path)
            return
        for nxt in adj.get(path[-1], []):
            if nxt not in path:
                path.append(nxt)
                yield from dfs(path)
                path.pop()

    for start in sorted(adj):
        yield from dfs([start])


def chain_cost(chain, qubit_cost, edge_cost) -> float:
    c = sum(qubit_cost[q] for q in chain)
    for a, b in zip(chain, chain[1:]):
        c += edge_cost.get(tuple(sorted((a, b))), 0.05)
    return c


def naive_chain(edges, n: int) -> list[int]:
    """What you'd get by just taking the first connected qubits: our baseline."""
    return next(all_chains(edges, n))


def best_chain(edges, n: int, qubit_cost, edge_cost) -> list[int]:
    best, best_c = None, float("inf")
    for chain in all_chains(edges, n):
        c = chain_cost(chain, qubit_cost, edge_cost)
        if c < best_c:
            best, best_c = chain, c
    if best is None:
        raise RuntimeError(f"no connected chain of {n} qubits on this device")
    return best
