# Copyright (C) 2020 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>

"""This module contains integrations cron jobs."""

from ggrc.integrations import synchronization_jobs


HOURLY_CRON_JOBS = [
    synchronization_jobs.sync_assessment_attributes,
    synchronization_jobs.sync_issue_attributes,
    synchronization_jobs.sync_people,
]
