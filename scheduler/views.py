from __future__ import division
from __future__ import division

from math import ceil

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, JsonResponse
from django.http.response import HttpResponseNotFound
from django.shortcuts import redirect
from django.shortcuts import render  # noqa: F401
from django.urls import reverse
from django.views.decorators.cache import never_cache
from redis.exceptions import ResponseError
from rq import requeue_job
from rq.exceptions import NoSuchJobError
from rq.registry import (
    DeferredJobRegistry,
    FailedJobRegistry,
    FinishedJobRegistry,
    ScheduledJobRegistry,
    StartedJobRegistry,
)
from rq.registry import (
    clean_registries,
)
from rq.worker import Worker
from rq.worker_registration import clean_worker_registry

from .queues import get_connection, get_all_workers
from .queues import get_queue_by_index
from .rq_classes import JobExecution, ExecutionStatus
from .settings import QUEUES_LIST


def get_scheduler_pid(queue):
    """Checks whether there's a scheduler-lock on a particular queue, and returns the PID.
    """
    try:
        from rq.scheduler import RQScheduler
        # When a scheduler acquires a lock it adds an expiring key: (e.g: rq:scheduler-lock:<queue.name>)
        # TODO: (RQ>= 1.13) return queue.scheduler_pid
        pid = queue.connection.get(RQScheduler.get_locking_key(queue.name))
        return int(pid.decode()) if pid is not None else None
    except Exception as e:  # noqa: F841
        pass  # Return None
    return None


# Create your views here.
@never_cache
@staff_member_required
def stats(request):
    context_data = {**admin.site.each_context(request), **get_statistics(run_maintenance_tasks=True)}
    return render(request, 'admin/scheduler/stats.html', context_data)


def stats_json(request):
    # TODO support API token
    if request.user.is_staff:
        return JsonResponse(get_statistics())

    return HttpResponseNotFound()


def get_statistics(run_maintenance_tasks=False):
    queues = []
    for index, config in enumerate(QUEUES_LIST):
        queue = get_queue_by_index(index)
        connection = queue.connection
        connection_kwargs = connection.connection_pool.connection_kwargs

        if run_maintenance_tasks:
            clean_registries(queue)
            clean_worker_registry(queue)

        # Raw access to the first item from left of the redis list.
        # This might not be accurate since new job can be added from the left
        # with `at_front` parameters.
        # Ideally rq should supports Queue.oldest_job
        last_job_id = connection.lindex(queue.key, 0)
        last_job = queue.fetch_job(last_job_id.decode('utf-8')) if last_job_id else None
        if last_job and last_job.enqueued_at:
            oldest_job_timestamp = last_job.enqueued_at.strftime('%Y-%m-%d, %H:%M:%S')
        else:
            oldest_job_timestamp = "-"

        # parse_class and connection_pool are not needed and not JSON serializable
        connection_kwargs.pop('parser_class', None)
        connection_kwargs.pop('connection_pool', None)

        queue_data = {
            'name': queue.name,
            'jobs': queue.count,
            'oldest_job_timestamp': oldest_job_timestamp,
            'index': index,
            'connection_kwargs': connection_kwargs,
            'scheduler_pid': get_scheduler_pid(queue),
        }

        connection = get_connection(queue.name)
        queue_data['workers'] = Worker.count(queue=queue)

        finished_job_registry = FinishedJobRegistry(queue.name, connection)
        started_job_registry = StartedJobRegistry(queue.name, connection)
        deferred_job_registry = DeferredJobRegistry(queue.name, connection)
        failed_job_registry = FailedJobRegistry(queue.name, connection)
        scheduled_job_registry = ScheduledJobRegistry(queue.name, connection)
        queue_data['finished_jobs'] = len(finished_job_registry)
        queue_data['started_jobs'] = len(started_job_registry)
        queue_data['deferred_jobs'] = len(deferred_job_registry)
        queue_data['failed_jobs'] = len(failed_job_registry)
        queue_data['scheduled_jobs'] = len(scheduled_job_registry)

        queues.append(queue_data)
    return {'queues': queues}


def get_jobs(queue, job_ids, registry=None):
    """Fetch jobs in bulk from Redis.
    1. If job data is not present in Redis, discard the result
    2. If `registry` argument is supplied, delete empty jobs from registry
    """
    jobs = JobExecution.fetch_many(job_ids, connection=queue.connection)
    valid_jobs = []
    for i, job in enumerate(jobs):
        if job is None:
            if registry:
                registry.remove(job_ids[i])
        else:
            valid_jobs.append(job)

    return valid_jobs


@never_cache
@staff_member_required
def jobs(request, queue_index):
    queue_index = int(queue_index)
    queue = get_queue_by_index(queue_index)

    items_per_page = 100
    num_jobs = queue.count
    page = int(request.GET.get('page', 1))

    if num_jobs > 0:
        last_page = int(ceil(num_jobs / items_per_page))
        page_range = range(1, last_page + 1)
        offset = items_per_page * (page - 1)
        jobs = queue.get_jobs(offset, items_per_page)
    else:
        jobs = []
        page_range = []

    context_data = {
        **admin.site.each_context(request),
        'queue': queue,
        'queue_index': queue_index,
        'jobs': jobs,
        'num_jobs': num_jobs,
        'page': page,
        'page_range': page_range,
        'job_status': 'Queued',
    }
    return render(request, 'admin/scheduler/jobs.html', context_data)


@never_cache
@staff_member_required
def finished_jobs(request, queue_index):
    queue_index = int(queue_index)
    queue = get_queue_by_index(queue_index)

    registry = FinishedJobRegistry(queue.name, queue.connection)

    items_per_page = 100
    num_jobs = len(registry)
    page = int(request.GET.get('page', 1))
    jobs = []

    if num_jobs > 0:
        last_page = int(ceil(num_jobs / items_per_page))
        page_range = range(1, last_page + 1)
        offset = items_per_page * (page - 1)
        job_ids = registry.get_job_ids(offset, offset + items_per_page - 1)
        jobs = get_jobs(queue, job_ids, registry)

    else:
        page_range = []

    context_data = {
        **admin.site.each_context(request),
        'queue': queue,
        'queue_index': queue_index,
        'jobs': jobs,
        'num_jobs': num_jobs,
        'page': page,
        'page_range': page_range,
        'job_status': 'Finished',
    }
    return render(request, 'admin/scheduler/jobs.html', context_data)


@never_cache
@staff_member_required
def failed_jobs(request, queue_index):
    queue_index = int(queue_index)
    queue = get_queue_by_index(queue_index)

    registry = FailedJobRegistry(queue.name, queue.connection)

    items_per_page = 100
    num_jobs = len(registry)
    page = int(request.GET.get('page', 1))
    jobs = []

    if num_jobs > 0:
        last_page = int(ceil(num_jobs / items_per_page))
        page_range = range(1, last_page + 1)
        offset = items_per_page * (page - 1)
        job_ids = registry.get_job_ids(offset, offset + items_per_page - 1)
        jobs = get_jobs(queue, job_ids, registry)

    else:
        page_range = []

    context_data = {
        **admin.site.each_context(request),
        'queue': queue,
        'queue_index': queue_index,
        'jobs': jobs,
        'num_jobs': num_jobs,
        'page': page,
        'page_range': page_range,
        'job_status': 'Failed',
    }
    return render(request, 'admin/scheduler/jobs.html', context_data)


@never_cache
@staff_member_required
def scheduled_jobs(request, queue_index):
    queue_index = int(queue_index)
    queue = get_queue_by_index(queue_index)

    registry = ScheduledJobRegistry(queue.name, queue.connection)

    items_per_page = 100
    num_jobs = len(registry)
    page = int(request.GET.get('page', 1))
    jobs = []

    if num_jobs > 0:
        last_page = int(ceil(num_jobs / items_per_page))
        page_range = range(1, last_page + 1)
        offset = items_per_page * (page - 1)
        job_ids = registry.get_job_ids(offset, offset + items_per_page - 1)

        jobs = get_jobs(queue, job_ids, registry)
        for job in jobs:
            job.scheduled_at = registry.get_scheduled_time(job)

    else:
        page_range = []

    context_data = {
        **admin.site.each_context(request),
        'queue': queue,
        'queue_index': queue_index,
        'jobs': jobs,
        'num_jobs': num_jobs,
        'page': page,
        'page_range': page_range,
        'job_status': 'Scheduled',
    }
    return render(request, 'admin/scheduler/jobs.html', context_data)


@never_cache
@staff_member_required
def started_jobs(request, queue_index):
    queue_index = int(queue_index)
    queue = get_queue_by_index(queue_index)

    registry = StartedJobRegistry(queue.name, queue.connection)

    items_per_page = 100
    num_jobs = len(registry)
    page = int(request.GET.get('page', 1))
    jobs = []

    if num_jobs > 0:
        last_page = int(ceil(num_jobs / items_per_page))
        page_range = range(1, last_page + 1)
        offset = items_per_page * (page - 1)
        job_ids = registry.get_job_ids(offset, offset + items_per_page - 1)
        jobs = get_jobs(queue, job_ids, registry)

    else:
        page_range = []

    context_data = {
        **admin.site.each_context(request),
        'queue': queue,
        'queue_index': queue_index,
        'jobs': jobs,
        'num_jobs': num_jobs,
        'page': page,
        'page_range': page_range,
        'job_status': 'Started',
    }
    return render(request, 'admin/scheduler/jobs.html', context_data)


@never_cache
@staff_member_required
def queue_workers(request, queue_index):
    queue_index = int(queue_index)
    queue = get_queue_by_index(queue_index)
    clean_worker_registry(queue)
    all_workers = Worker.all(queue.connection)
    workers = [worker for worker in all_workers if queue.name in worker.queue_names()]

    context_data = {
        **admin.site.each_context(request),
        'queue': queue,
        'queue_index': queue_index,
        'workers': workers,
    }
    return render(request, 'admin/scheduler/queue_workers.html', context_data)


@never_cache
@staff_member_required
def workers(request):
    all_workers = get_all_workers()
    workers = [worker for worker in all_workers]

    context_data = {
        **admin.site.each_context(request),
        'workers': workers,
    }
    return render(request, 'admin/scheduler/workers.html', context_data)


@never_cache
@staff_member_required
def worker_details(request, key):
    queue_index = 0
    queue = get_queue_by_index(queue_index)
    worker = Worker.find_by_key(key, connection=queue.connection)
    # Convert microseconds to milliseconds
    worker.total_working_time = worker.total_working_time / 1000

    queue_names = ', '.join(worker.queue_names())

    context_data = {
        **admin.site.each_context(request),
        'queue': queue,
        'queue_index': queue_index,
        'worker': worker,
        'queue_names': queue_names,
        'job': worker.get_current_job(),
        'total_working_time': worker.total_working_time * 1000,
    }
    return render(request, 'admin/scheduler/worker_details.html', context_data)


@never_cache
@staff_member_required
def deferred_jobs(request, queue_index):
    queue_index = int(queue_index)
    queue = get_queue_by_index(queue_index)

    registry = DeferredJobRegistry(queue.name, queue.connection)

    items_per_page = 100
    num_jobs = len(registry)
    page = int(request.GET.get('page', 1))
    jobs = []

    if num_jobs > 0:
        last_page = int(ceil(num_jobs / items_per_page))
        page_range = range(1, last_page + 1)
        offset = items_per_page * (page - 1)
        job_ids = registry.get_job_ids(offset, offset + items_per_page - 1)

        for job_id in job_ids:
            try:
                item = JobExecution.fetch(job_id, connection=queue.connection)
                jobs.append(item)
            except NoSuchJobError:
                pass

    else:
        page_range = []

    context_data = {
        **admin.site.each_context(request),
        'queue': queue,
        'queue_index': queue_index,
        'jobs': jobs,
        'num_jobs': num_jobs,
        'page': page,
        'page_range': page_range,
        'job_status': 'Deferred',
    }
    return render(request, 'admin/scheduler/jobs.html', context_data)


@never_cache
@staff_member_required
def job_detail(request, job_id):
    queue_index = 0
    queue = get_queue_by_index(queue_index)

    try:
        job = JobExecution.fetch(job_id, connection=queue.connection)
    except NoSuchJobError:
        raise Http404("Couldn't find job with this ID: %s" % job_id)

    try:
        job.func_name
        data_is_valid = True
    except Exception:
        data_is_valid = False

    try:
        exc_info = job._exc_info
    except AttributeError:
        exc_info = None

    context_data = {
        **admin.site.each_context(request),
        'queue_index': queue_index,
        'job': job,
        'dependency_id': job._dependency_id,
        'queue': queue,
        'data_is_valid': data_is_valid,
        'exc_info': exc_info,
    }
    return render(request, 'admin/scheduler/job_detail.html', context_data)


@never_cache
@staff_member_required
def delete_job(request, queue_index, job_id):
    queue_index = int(queue_index)
    queue = get_queue_by_index(queue_index)
    job = JobExecution.fetch(job_id, connection=queue.connection)

    if request.method == 'POST':
        # Remove job id from queue and delete the actual job
        queue.connection.lrem(queue.key, 0, job.id)
        job.delete()
        messages.info(request, 'You have successfully deleted %s' % job.id)
        return redirect('queue_jobs', queue_index)

    context_data = {
        **admin.site.each_context(request),
        'queue_index': queue_index,
        'job': job,
        'queue': queue,
    }
    return render(request, 'admin/scheduler/delete_job.html', context_data)


@never_cache
@staff_member_required
def requeue_job_view(request, queue_index, job_id):
    queue_index = int(queue_index)
    queue = get_queue_by_index(queue_index)
    job = JobExecution.fetch(job_id, connection=queue.connection)

    if request.method == 'POST':
        requeue_job(job_id, connection=queue.connection)
        messages.info(request, 'You have successfully requeued %s' % job.id)
        return redirect('job_details', job_id)

    context_data = {
        **admin.site.each_context(request),
        'queue_index': queue_index,
        'job': job,
        'queue': queue,
    }
    return render(request, 'admin/scheduler/delete_job.html', context_data)


@never_cache
@staff_member_required
def clear_queue(request, queue_index):
    queue_index = int(queue_index)
    queue = get_queue_by_index(queue_index)
    next_url = request.META.get('HTTP_REFERER') or reverse('queue_jobs', args=[queue_index])
    if request.method == 'POST':
        try:
            queue.empty()
            messages.info(request, 'You have successfully cleared the queue %s' % queue.name)
        except ResponseError as e:
            messages.error(
                request,
                f'error: {e.message}',
            )
            raise e
        return redirect('queue_jobs', queue_index)

    context_data = {
        **admin.site.each_context(request),
        'queue_index': queue_index,
        'queue': queue,
        'total_jobs': len(queue),
        'action': 'empty',
        'jobs': queue.get_jobs(),
        'next_url': next_url,
        'action_url': reverse('queue_clear', args=[queue_index, ])
    }
    return render(request, 'admin/scheduler/confirm_action.html', context_data)


@never_cache
@staff_member_required
def requeue_all(request, queue_index):
    queue_index = int(queue_index)
    queue = get_queue_by_index(queue_index)
    registry = FailedJobRegistry(queue=queue)
    next_url = request.META.get('HTTP_REFERER') or reverse('queue_jobs', args=[queue_index])
    job_ids = registry.get_job_ids()
    if request.method == 'POST':
        count = 0
        # Confirmation received
        for job_id in job_ids:
            try:
                requeue_job(job_id, connection=queue.connection)
                count += 1
            except NoSuchJobError:
                pass

        messages.info(request, 'You have successfully requeued %d jobs!' % count)
        return redirect('queue_jobs', queue_index)

    context_data = {
        **admin.site.each_context(request),
        'queue': queue,
        'total_jobs': len(registry),
        'queue_index': queue_index,
        'action': 'requeue',
        'jobs': [queue.fetch_job(job_id) for job_id in job_ids],
        'next_url': next_url,
        'action_url': reverse('queue_requeue_all', args=[queue_index, ])
    }

    return render(request, 'admin/scheduler/confirm_action.html', context_data)


@never_cache
@staff_member_required
def confirm_action(request, queue_index):
    queue_index = int(queue_index)
    queue = get_queue_by_index(queue_index)
    next_url = request.META.get('HTTP_REFERER') or reverse('queue_jobs', args=[queue_index])

    if request.method == 'POST' and request.POST.get('action', False):
        # confirm action
        if request.POST.get('_selected_action', False):
            job_id_list = request.POST.getlist('_selected_action')
            context_data = {
                **admin.site.each_context(request),
                'queue_index': queue_index,
                'action': request.POST['action'],
                'jobs': [queue.fetch_job(job_id) for job_id in job_id_list],
                'total_jobs': len(job_id_list),
                'queue': queue,
                'next_url': next_url,
                'action_url': reverse('queue_actions', args=[queue_index, ]),
            }
            return render(request, 'admin/scheduler/confirm_action.html', context_data)

    return redirect(next_url)


@never_cache
@staff_member_required
def actions(request, queue_index):
    queue_index = int(queue_index)
    queue = get_queue_by_index(queue_index)
    next_url = request.POST.get('next_url') or reverse('queue_jobs', args=[queue_index])

    if request.method == 'POST' and request.POST.get('action', False):
        # do confirmed action
        if request.POST.get('job_ids', False):
            job_ids = request.POST.getlist('job_ids')

            if request.POST['action'] == 'delete':
                for job_id in job_ids:
                    job = JobExecution.fetch(job_id, connection=queue.connection)
                    # Remove job id from queue and delete the actual job
                    queue.connection.lrem(queue.key, 0, job.id)
                    job.delete()
                messages.info(request, 'You have successfully deleted %s jobs!' % len(job_ids))
            elif request.POST['action'] == 'requeue':
                for job_id in job_ids:
                    requeue_job(job_id, connection=queue.connection)
                messages.info(request, 'You have successfully requeued %d  jobs!' % len(job_ids))

    return redirect(next_url)


@never_cache
@staff_member_required
def enqueue_job(request, queue_index, job_id):
    """Enqueue deferred jobs"""
    queue_index = int(queue_index)
    queue = get_queue_by_index(queue_index)
    job = JobExecution.fetch(job_id, connection=queue.connection)

    if request.method == 'POST':
        queue.enqueue_job(job)

        # Remove job from correct registry if needed
        if job.get_status() == ExecutionStatus.DEFERRED:
            registry = DeferredJobRegistry(queue.name, queue.connection)
            registry.remove(job)
        elif job.get_status() == ExecutionStatus.FINISHED:
            registry = FinishedJobRegistry(queue.name, queue.connection)
            registry.remove(job)
        elif job.get_status() == ExecutionStatus.SCHEDULED:
            registry = ScheduledJobRegistry(queue.name, queue.connection)
            registry.remove(job)

        messages.info(request, 'You have successfully enqueued %s' % job.id)
        return redirect('job_details', job_id)

    context_data = {
        **admin.site.each_context(request),
        'queue_index': queue_index,
        'job': job,
        'queue': queue,
    }
    return render(request, 'admin/scheduler/delete_job.html', context_data)
