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


def test_check_quota_stops_when_zero_and_ignores_unreadable():
    import pytest
    from qpu_weather.backend import check_quota

    svc = mock.Mock()
    svc.usage.return_value = {"usage_remaining_seconds": 0}
    with pytest.raises(SystemExit):
        check_quota(svc)
    svc.usage.return_value = {"usage_remaining_seconds": 120}
    check_quota(svc)
    svc.usage.side_effect = RuntimeError("no api")
    check_quota(svc)
