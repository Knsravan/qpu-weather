import pytest

from qpu_weather.runner import QueueTimeout, wait_until_running


class FakeJob:
    def __init__(self, statuses):
        self.statuses, self.cancelled = list(statuses), False

    def status(self):
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]

    def cancel(self):
        self.cancelled = True

    def job_id(self):
        return "job1"


def test_returns_when_job_starts():
    job = FakeJob(["QUEUED", "QUEUED", "RUNNING"])
    assert wait_until_running(job, sleep=lambda s: None) == "RUNNING"
    assert not job.cancelled


def test_cancels_job_stuck_in_queue():
    job = FakeJob(["QUEUED"])
    t = iter(range(0, 10_000, 100))
    with pytest.raises(QueueTimeout):
        wait_until_running(job, timeout_s=600, sleep=lambda s: None, clock=lambda: next(t))
    assert job.cancelled
