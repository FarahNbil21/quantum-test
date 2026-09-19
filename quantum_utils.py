"""
Quantum path-selection utilities.

Implements Grover-based "threshold search" (Dürr–Høyer style quantum
minimum finding): repeatedly runs Grover's algorithm to search for a
candidate cheaper than the current best-known threshold, until it
converges on the (probable) minimum-cost candidate.

This is a REAL quantum simulation (via Qiskit Aer) - not a placeholder.
Because Grover search is probabilistic, results can vary slightly
between runs; this is expected and is part of what makes it "quantum".
"""

import random
from math import ceil, log2, pi, sqrt

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator


def oracle_mark(indices, n_qubits):
    """Build an oracle circuit that flips the phase of each marked index."""
    qc = QuantumCircuit(n_qubits)
    for idx in indices:
        bits = format(idx, f"0{n_qubits}b")[::-1]
        for q, b in enumerate(bits):
            if b == "0":
                qc.x(q)
        if n_qubits == 1:
            qc.z(0)
        else:
            qc.h(n_qubits - 1)
            qc.mcx(list(range(n_qubits - 1)), n_qubits - 1)
            qc.h(n_qubits - 1)
        for q, b in enumerate(bits):
            if b == "0":
                qc.x(q)
    return qc


def diffuser(n_qubits):
    """Standard Grover diffusion operator."""
    qc = QuantumCircuit(n_qubits)
    qc.h(range(n_qubits))
    qc.x(range(n_qubits))
    if n_qubits == 1:
        qc.z(0)
    else:
        qc.h(n_qubits - 1)
        qc.mcx(list(range(n_qubits - 1)), n_qubits - 1)
        qc.h(n_qubits - 1)
    qc.x(range(n_qubits))
    qc.h(range(n_qubits))
    return qc


def grover_search(marked_indices, n_qubits, shots=512):
    """Run one full Grover search amplifying `marked_indices` and return measurement counts."""
    if len(marked_indices) == 0:
        return {}

    N = 2 ** n_qubits
    M = len(marked_indices)
    iterations = max(1, round((pi / 4) * sqrt(N / M)))

    qc = QuantumCircuit(n_qubits, n_qubits)
    qc.h(range(n_qubits))

    oracle = oracle_mark(marked_indices, n_qubits)
    diff = diffuser(n_qubits)
    for _ in range(iterations):
        qc.compose(oracle, inplace=True)
        qc.compose(diff, inplace=True)

    qc.measure(range(n_qubits), range(n_qubits))

    backend = AerSimulator()
    transpiled = transpile(qc, backend)
    result = backend.run(transpiled, shots=shots).result()
    return result.get_counts()


def grover_threshold_search(candidates, max_iterations=12, shots=512, seed=None):
    """
    Dürr–Høyer style quantum minimum finding.

    candidates: list of (path, cost) tuples.
    Returns: (best_index, combined_measurement_histogram)
    """
    if seed is not None:
        random.seed(seed)

    N = len(candidates)
    if N == 1:
        return 0, {}

    n_qubits = max(1, ceil(log2(N)))

    threshold_idx = random.randrange(N)
    threshold_cost = candidates[threshold_idx][1]
    history = {}

    for _ in range(max_iterations):
        marked = [i for i in range(N) if candidates[i][1] < threshold_cost]
        if not marked:
            break

        counts = grover_search(marked, n_qubits, shots=shots)
        for bitstring, c in counts.items():
            history[bitstring] = history.get(bitstring, 0) + c

        best_bitstring = max(counts, key=counts.get)
        measured_idx = int(best_bitstring, 2)

        if measured_idx < N and candidates[measured_idx][1] < threshold_cost:
            threshold_idx = measured_idx
            threshold_cost = candidates[measured_idx][1]

    return threshold_idx, history
