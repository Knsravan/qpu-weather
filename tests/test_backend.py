from unittest import mock

from qpu_weather.backend import _connect_service


def test_connect_passes_instance_only_when_given():
    with mock.patch("qiskit_ibm_runtime.QiskitRuntimeService") as svc:
        _connect_service("tok", None)
        svc.assert_called_with(channel="ibm_quantum_platform", token="tok")
        _connect_service("tok", "crn:abc")
        svc.assert_called_with(channel="ibm_quantum_platform", token="tok", instance="crn:abc")


def test_connect_without_token_uses_saved_account():
    with mock.patch("qiskit_ibm_runtime.QiskitRuntimeService") as svc:
        _connect_service(None, "crn:abc")
        svc.assert_called_with()
