from math import ceil

import redis
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.http.response import HttpResponseNotFound, Http404
from django.shortcuts import redirect
from django.shortcuts import render
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
    clean_registries,
)
from rq.worker_registration import clean_worker_registry

from .queues import get_all_workers, get_connection, logger, get_queue
from .rq_classes import JobExecution, ExecutionStatus, DjangoWorker
from .settings import SCHEDULER


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
    from scheduler.settings import QUEUES
    queues = []
    for queue_name in QUEUES:
        try:
            queue = get_queue(queue_name)
            connection = get_connection(queue.name)
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

            queue_data = dict(
                name=queue.name,
                jobs=queue.count,
                oldest_job_timestamp=oldest_job_timestamp,
                connection_kwargs=connection_kwargs,
                scheduler_pid=queue.scheduler_pid,
                workers=DjangoWorker.count(queue=queue),
                finished_jobs=len(queue.finished_job_registry),
                started_jobs=len(queue.started_job_registry),
                deferred_jobs=len(queue.deferred_job_registry),
                failed_jobs=len(queue.failed_job_registry),
                scheduled_jobs=len(queue.scheduled_job_registry),
                canceled_jobs=len(queue.canceled_job_registry),
            )
            queues.append(queue_data)
        except redis.ConnectionError as e:
            logger.error(f'Could not connect for queue {queue_name}: {e}')
            continue

    return {'queues': queues}


def _get_registry_job_list(queue, registry, page):
    items_per_page = SCHEDULER['EXECUTIONS_IN_PAGE']
    num_jobs = len(registry)
    job_list = []

    if num_jobs == 0:
        return job_list, num_jobs, []

    last_page = int(ceil(num_jobs / items_per_page))
    page_range = range(1, last_page + 1)
    offset = items_per_page * (page - 1)
    job_ids = registry.get_job_ids(offset, offset + items_per_page - 1)
    job_list = JobExecution.fetch_many(job_ids, connection=queue.connection)
    remove_job_ids = [job_id for i, job_id in enumerate(job_ids) if job_list[i] is None]
    valid_jobs = [job for job in job_list if job is not None]
    if registry is not queue:
        for job_id in remove_job_ids:
            registry.remove(job_id)

    return valid_jobs, num_jobs, page_range


def jobs_view(request, queue_name, registry_class, status_title):
    queue = get_queue(queue_name)

    registry = registry_class(queue.name, queue.connection) if registry_class is not None else queue
    page = int(request.GET.get('page', 1))
    job_list, num_jobs, page_range = _get_registry_job_list(queue, registry, page)

    context_data = {
        **admin.site.each_context(request),
        'queue': queue,
        'jobs': job_list,
        'num_jobs': num_jobs,
        'page': page,
        'page_range': page_range,
        'job_status': status_title,
    }
    return render(request, 'admin/scheduler/jobs.html', context_data)


@never_cache
@staff_member_required
def jobs(request, queue_name):
    return jobs_view(request, queue_name, None, 'Queued')


@never_cache
@staff_member_required
def finished_jobs(request, queue_name):
    return jobs_view(request, queue_name, FinishedJobRegistry, 'Finished')


@never_cache
@staff_member_required
def failed_jobs(request, queue_name):
    return jobs_view(request, queue_name, FailedJobRegistry, 'Failed')


@never_cache
@staff_member_required
def scheduled_jobs(request, queue_name):
    return jobs_view(request, queue_name, ScheduledJobRegistry, 'Scheduled')


@never_cache
@staff_member_required
def started_jobs(request, queue_name):
    return jobs_view(request, queue_name, StartedJobRegistry, 'Started')


@never_cache
@staff_member_required
def deferred_jobs(request, queue_name):
    return jobs_view(request, queue_name, DeferredJobRegistry, 'Deferred')


@never_cache
@staff_member_required
def queue_workers(request, queue_name):
    queue = get_queue(queue_name)
    clean_worker_registry(queue)
    all_workers = DjangoWorker.all(queue.connection)
    worker_list = [worker for worker in all_workers if queue.name in worker.queue_names()]

    context_data = {
        **admin.site.each_context(request),
        'queue': queue,
        'workers': worker_list,
    }
    return render(request, 'admin/scheduler/queue_workers.html', context_data)


@never_cache
@staff_member_required
def workers(request):
    all_workers = get_all_workers()
    worker_list = [worker for worker in all_workers]

    context_data = {
        **admin.site.each_context(request),
        'workers': worker_list,
    }
    return render(request, 'admin/scheduler/workers.html', context_data)


@never_cache
@staff_member_required
def worker_details(request, key):
    from scheduler.settings import QUEUES
    queue, worker = None, None
    for queue_name in QUEUES:
        try:
            queue = get_queue(queue_name)
            worker = DjangoWorker.find_by_key(key, connection=queue.connection)
            if worker is not None:
                break
        except redis.ConnectionError:
            pass

    if worker is None:
        raise Http404(f"Couldn't find worker with this ID: {key}")
    # Convert microseconds to milliseconds
    worker.total_working_time = worker.total_working_time / 1000

    queue_names = ', '.join(worker.queue_names())

    context_data = {
        **admin.site.each_context(request),
        'queue': queue,
        'worker': worker,
        'queue_names': queue_names,
        'job': worker.get_current_job(),
        'total_working_time': worker.total_working_time * 1000,
    }
    return render(request, 'admin/scheduler/worker_details.html', context_data)


@never_cache
@staff_member_required
def job_detail(request, job_id):
    from scheduler.settings import QUEUES
    queue_index, queue, job = None, None, None

    for queue_name in QUEUES:
        try:
            queue = get_queue(queue_name)
            job = JobExecution.fetch(job_id, connection=queue.connection)
            break
        except NoSuchJobError:
            pass
        except redis.ConnectionError:
            pass
    if job is None:
        raise Http404(f"Couldn't find job with this ID: {job_id}")
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
def delete_job(request, queue_name, job_id):
    queue = get_queue(queue_name)
    job = JobExecution.fetch(job_id, connection=queue.connection)

    if request.method == 'POST':
        # Remove job id from queue and delete the actual job
        queue.connection.lrem(queue.key, 0, job.id)
        job.delete()
        messages.info(request, 'You have successfully deleted %s' % job.id)
        return redirect('queue_jobs', queue_name)

    context_data = {
        **admin.site.each_context(request),
        'job': job,
        'queue': queue,
    }
    return render(request, 'admin/scheduler/delete_job.html', context_data)


@never_cache
@staff_member_required
def requeue_job_view(request, queue_name, job_id):
    queue = get_queue(queue_name)
    job = JobExecution.fetch(job_id, connection=queue.connection)

    if request.method == 'POST':
        requeue_job(job_id, connection=queue.connection)
        messages.info(request, f'You have successfully re-queued {job.id}')
        return redirect('job_details', job_id)

    context_data = {
        **admin.site.each_context(request),
        'job': job,
        'queue': queue,
    }
    return render(request, 'admin/scheduler/delete_job.html', context_data)


@never_cache
@staff_member_required
def clear_queue(request, queue_name):
    queue = get_queue(queue_name)
    next_url = request.META.get('HTTP_REFERER') or reverse('queue_jobs', args=[queue_name])
    if request.method == 'POST':
        try:
            queue.empty()
            messages.info(request, f'You have successfully cleared the queue {queue.name}')
        except ResponseError as e:
            messages.error(request, f'error: {e}', )
            raise e
        return redirect('queue_jobs', queue_name)

    context_data = {
        **admin.site.each_context(request),
        'queue': queue,
        'total_jobs': len(queue),
        'action': 'empty',
        'jobs': queue.get_jobs(),
        'next_url': next_url,
        'action_url': reverse('queue_clear', args=[queue_name, ])
    }
    return render(request, 'admin/scheduler/confirm_action.html', context_data)


@never_cache
@staff_member_required
def requeue_all(request, queue_name):
    queue = get_queue(queue_name)
    registry = FailedJobRegistry(queue=queue)
    next_url = request.META.get('HTTP_REFERER') or reverse('queue_jobs', args=[queue_name])
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

        messages.info(request, f'You have successfully re-queued {count} jobs!')
        return redirect('queue_jobs', queue_name)

    context_data = {
        **admin.site.each_context(request),
        'queue': queue,
        'total_jobs': len(registry),
        'action': 'requeue',
        'jobs': [queue.fetch_job(job_id) for job_id in job_ids],
        'next_url': next_url,
        'action_url': reverse('queue_requeue_all', args=[queue_name, ])
    }

    return render(request, 'admin/scheduler/confirm_action.html', context_data)


@never_cache
@staff_member_required
def confirm_action(request, queue_name):
    queue = get_queue(queue_name)
    next_url = request.META.get('HTTP_REFERER') or reverse('queue_jobs', args=[queue_name])

    if request.method == 'POST' and request.POST.get('action', False):
        # confirm action
        if request.POST.get('_selected_action', False):
            job_id_list = request.POST.getlist('_selected_action')
            context_data = {
                **admin.site.each_context(request),
                'action': request.POST['action'],
                'jobs': [queue.fetch_job(job_id) for job_id in job_id_list],
                'total_jobs': len(job_id_list),
                'queue': queue,
                'next_url': next_url,
                'action_url': reverse('queue_actions', args=[queue_name, ]),
            }
            return render(request, 'admin/scheduler/confirm_action.html', context_data)

    return redirect(next_url)


@never_cache
@staff_member_required
def actions(request, queue_name):
    queue = get_queue(queue_name)
    next_url = request.POST.get('next_url') or reverse('queue_jobs', args=[queue_name])

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
                messages.info(request, f'You have successfully deleted {len(job_ids)} jobs!')
            elif request.POST['action'] == 'requeue':
                for job_id in job_ids:
                    requeue_job(job_id, connection=queue.connection)
                messages.info(request, f'You have successfully re-queued {len(job_ids)}  jobs!')
            elif request.POST['action'] == 'stop':
                cancelled_jobs = 0
                for job_id in job_ids:
                    try:
                        job = JobExecution.fetch(job_id, connection=queue.connection)
                        job.stop_execution(queue.connection)
                        job.cancel()
                        cancelled_jobs += 1
                    except Exception as e:
                        logger.warning(f'Could not stop job: {e}')
                        pass
                messages.info(request, f'You have successfully stopped {cancelled_jobs}  jobs!')

    return redirect(next_url)


@never_cache
@staff_member_required
def enqueue_job(request, queue_name, job_id):
    """Enqueue deferred jobs"""
    queue = get_queue(queue_name)
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
        'job': job,
        'queue': queue,
    }
    return render(request, 'admin/scheduler/delete_job.html', context_data)
