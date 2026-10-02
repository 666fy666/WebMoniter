import asyncio

import pytest

from src.jobs.execution import ExecutionService, QueueFullError
from src.jobs.task_outcome import TASK_PARTIAL, TASK_SKIPPED


@pytest.mark.asyncio
async def test_bounded_queue_deduplicates_across_sources(tmp_path):
    service = ExecutionService(tmp_path / "runs.db", concurrency=1, capacity=1)
    gate, started = asyncio.Event(), asyncio.Event()
    count = 0

    async def run():
        nonlocal count
        count += 1
        started.set()
        await gate.wait()
        return True

    await service.start()
    try:
        first = await service.submit("same", run, "scheduled")
        await started.wait()
        duplicate = await service.submit("same", run, "manual")
        assert duplicate == {"run_id": first["run_id"], "duplicate": True}
        await service.submit("second", run)
        with pytest.raises(QueueFullError):
            await service.submit("third", run)
        gate.set()
        await asyncio.wait_for(service.queue.join(), 2)
        assert count == 2
        assert all(record["status"] == "success" for record in await service.list_runs())
        assert service.active == {}
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_restart_interrupts_work_without_replaying(tmp_path):
    path = tmp_path / "runs.db"
    service = ExecutionService(path)
    await service.start()

    async def long_job():
        await asyncio.Event().wait()

    await service.submit("job", long_job)
    await asyncio.sleep(0)
    await service.stop()
    restored = ExecutionService(path)
    await restored.start()
    try:
        assert (await restored.list_runs())[0]["status"] == "interrupted"
        assert restored.queue.empty()
    finally:
        await restored.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "outcome, expected",
    [(True, "success"), (False, "failed"), (TASK_SKIPPED, "skipped"), (TASK_PARTIAL, "partial")],
)
async def test_explicit_outcomes(tmp_path, outcome, expected):
    service = ExecutionService(tmp_path / "runs.db")
    await service.start()

    async def run():
        return outcome

    try:
        await service.submit("job", run)
        await service.queue.join()
        assert (await service.list_runs())[0]["status"] == expected
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_exception_does_not_leak_secrets(tmp_path):
    service = ExecutionService(tmp_path / "runs.db")
    await service.start()

    async def run():
        raise ValueError("private-cookie-value")

    try:
        await service.submit("job", run)
        await service.queue.join()
        record = (await service.list_runs())[0]
        assert record["status"] == "failed"
        assert "private-cookie-value" not in record["message"]
    finally:
        await service.stop()


@pytest.mark.asyncio
async def test_latest_runs_keeps_quiet_jobs(tmp_path):
    service = ExecutionService(tmp_path / "runs.db")
    await service.start()

    async def run():
        return True

    try:
        await service.submit("quiet", run)
        await service.queue.join()
        for _ in range(3):
            await service.submit("busy", run)
            await service.queue.join()
        rows = await service.list_runs(latest_per_job=True)
        assert len(rows) == 2
        assert {row["job_id"] for row in rows} == {"quiet", "busy"}
    finally:
        await service.stop()
