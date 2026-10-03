'''Fire-and-forget task handling.'''

import asyncio
import gc

from utilities.utils import _background_tasks, fire_task


async def test_task_runs_to_completion():
    done = asyncio.Event()

    async def work():
        await asyncio.sleep(0)
        done.set()

    fire_task(work())
    await asyncio.wait_for(done.wait(), timeout=1)


async def test_task_survives_garbage_collection():
    '''
    asyncio keeps only a weak reference to a running task, so one with no other
    referent could be collected mid-flight -- silently losing the cache write
    this is used for.
    '''

    ran = asyncio.Event()

    async def work():
        await asyncio.sleep(0.01)
        ran.set()

    fire_task(work())
    gc.collect()

    await asyncio.wait_for(ran.wait(), timeout=1)


async def test_reference_is_released_once_complete():
    async def work():
        return None

    task = fire_task(work())
    await task

    await asyncio.sleep(0)
    assert task not in _background_tasks
