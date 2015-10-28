#+
# Copyright 2015 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################


import os
from namespace import Namespace, EntityNamespace, ConfigNamespace, Command, RpcBasedLoadMixin, TaskBasedSaveMixin, description
from output import ValueType, output_msg, output_table, read_value, format_value


TASK_TYPES = {
    'scrub': 'zfs.pool.scrub',
    'smart': 'disks.test_parallel',
    'snapshot': 'replication.snapshot_dataset',
    'replication': 'replication.replicate_dataset',
    'check_updates': 'update.checkfetch'
}


TASK_TYPES_REVERSE = {v: k for k, v in TASK_TYPES.items()}


@description("Runs calendar task right now")
class RunCommand(Command):
    def run(self, args, kwargs, opargs):
        pass


@description("Global network configuration")
class ScheduleNamespace(ConfigNamespace):
    def __init__(self, name, context, parent):
        super(ScheduleNamespace, self).__init__(name, context)
        self.parent = parent

        self.add_property(
            descr='Year',
            name='year',
            get='year',
            list=True
        )

        self.add_property(
            descr='Month',
            name='month',
            get='month',
            list=True
        )

        self.add_property(
            descr='Day',
            name='day',
            get='day',
            list=True
        )

        self.add_property(
            descr='Week',
            name='week',
            get='week',
            list=True
        )

        self.add_property(
            descr='Hour',
            name='hour',
            get='hour',
            list=True
        )

        self.add_property(
            descr='Minute',
            name='minute',
            get='minute',
            list=True
        )

    def load(self):
        self.entity = self.parent.entity['schedule']

    def save(self):
        self.parent.save()


@description("Provides access to task scheduled on a regular basis")
class CalendarTasksNamespace(RpcBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context):
        super(CalendarTasksNamespace, self).__init__(name, context)

        self.query_call = 'calendar_tasks.query'
        self.create_task = 'calendar_tasks.create'
        self.update_task = 'calendar_tasks.update'
        self.delete_task = 'calendar_tasks.delete'

        self.add_property(
            descr='Task id',
            name='id',
            get='id',
            set=None,
            list=True)

        self.add_property(
            descr='Task type',
            name='name',
            get=lambda row: TASK_TYPES_REVERSE[row['name']],
            set=self.set_type,
            list=True)

        self.add_property(
            descr='Task arguments',
            name='args',
            get=lambda row: [format_value(i) for i in row['args']],
            set=None,
            list=True
        )

        self.add_property(
            descr='Coalesce',
            name='coalesce',
            get='schedule.coalesce',
            list=True,
            type=ValueType.BOOLEAN)

        self.add_property(
            descr='Schedule',
            name='schedule',
            get=lambda row: ' '.join(filter(lambda v: isinstance(v, basestring), row['schedule'].values())),
            set=None,
            list=True,
            type=ValueType.STRING)

        self.primary_key = self.get_mapping('id')
        self.entity_namespaces = lambda this: [
            ScheduleNamespace('schedule', self.context, this)
        ]

        self.entity_commands = lambda this: {
            'run': RunCommand()
        }

    def set_type(self, row):
        pass


def _init(context):
    context.attach_namespace('/', CalendarTasksNamespace('calendar', context))
