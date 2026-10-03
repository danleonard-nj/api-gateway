import asyncio

# asyncio holds only a weak reference to a running task, so a fire-and-forget
# task with no other referent can be garbage collected before it finishes.
# Holding one here until the task completes is the documented workaround.
_background_tasks = set()


def fire_task(func):
    task = asyncio.create_task(func)

    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return task


def validate_leading_slash(url):
    # Guard the empty/missing case explicitly: a route config that omits an
    # endpoint used to raise TypeError from the subscript here, which read as a
    # crash rather than as the configuration error it is.
    if not url or not url.startswith('/'):
        raise Exception(f'{url} must begin with a leading slash')
