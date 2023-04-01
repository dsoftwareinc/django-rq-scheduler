from django.urls import path

from . import views

urlpatterns = [
    path('queues/', views.stats, name='queues_home'),
    path('queues/stats.json', views.stats_json, name='queues_home_json'),
    path('queues/<int:queue_index>/', views.jobs, name='queue_jobs'),
    path('queues/<int:queue_index>/workers/', views.queue_workers, name='queue_workers'),
    path('queues/<int:queue_index>/finished/', views.finished_jobs, name='queue_finished_jobs'),
    path('queues/<int:queue_index>/failed/', views.failed_jobs, name='queue_failed_jobs'),
    path('queues/<int:queue_index>/scheduled/', views.scheduled_jobs, name='queue_scheduled_jobs'),
    path('queues/<int:queue_index>/started/', views.started_jobs, name='queue_started_jobs'),
    path('queues/<int:queue_index>/deferred/', views.deferred_jobs, name='queue_deferred_jobs'),
    path('queues/<int:queue_index>/empty/', views.clear_queue, name='queue_clear'),
    path('queues/<int:queue_index>/requeue-all/', views.requeue_all, name='queue_requeue_all'),
    path('queues/<int:queue_index>/<str:job_id>/delete/', views.delete_job, name='queue_delete_job'),
    path('queues/<int:queue_index>/confirm-action/', views.confirm_action, name='queue_confirm_action'),
    path('queues/<int:queue_index>/actions/', views.actions, name='queue_actions'),
    path('queues/<int:queue_index>/<str:job_id>/requeue/', views.requeue_job_view, name='queue_requeue_job', ),
    path('queues/<int:queue_index>/<str:job_id>/enqueue/', views.enqueue_job, name='queue_enqueue_job'),
]

urlpatterns += [
    path('workers/', views.workers, name='workers_home'),
    path('workers/<str:key>/', views.worker_details, name='worker_details'),
    path('jobs/<str:job_id>/', views.job_detail, name='job_details'),
]
