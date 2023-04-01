# Changelog

## v2023.5.0b1 🌈

### 🚀 Breaking changes

* Remove django-rq dependency
* Remove threaded scheduler support

### 🚀 Features

* Migrate all required features from django-rq:
    * management commands to create worker (rqworker), stats, etc.
    * admin view of queues
* admin view for workers
* admin views are significantly more informative
* job-ids and worker-ids are more informative

### 🚀 Roadmap

* Merge all scheduled jobs to one model
* job executions inline in each job

## v2023.4.0 🌈

### 🚀 Features

* Add management commands to export and import models.
* Add Run Now @gabriels1234 (#106)

### 🧰 Maintenance

* Bump poetry from 1.4.0 to 1.4.1 @dependabot (#107)
* Bump flake8-pyproject from 1.2.2 to 1.2.3 @dependabot (#110)
* Bump fakeredis from 2.10.1 to 2.10.2 @dependabot (#111)
* Bump coverage from 7.2.1 to 7.2.2 @dependabot (#104)

## v2023.3.2 🌈

* Add missing migration

## v2023.3.1 🌈

* Fix: error on django-admin when internal scheduler is off

## v2023.3.0 🌈

### 🐛 Bug Fixes

* fixed validation of callable field @mazhor90 (#93)

## v2023.2.0 🌈

### 🚀 Features

* Start working on documentation on https://django-rq-scheduler.readthedocs.io/en/latest/

### 🐛 Bug Fixes

* Hotfix new cron @gabriels1234 (#79)
* Make at_front nullable @cunla (#77)

## v2023.3.0 🌈

### 🚀 Breaking changes

* Remove rq-scheduler dependency

### 🚀 Features

* Add support for scheduling at front of the queue #65
