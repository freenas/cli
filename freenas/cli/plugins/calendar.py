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

import gettext
from freenas.cli.namespace import (
    EntityNamespace, ConfigNamespace, Command, RpcBasedLoadMixin, TaskBasedSaveMixin,
    description, CommandException
)
from freenas.cli.output import ValueType, format_value
from freenas.cli.utils import post_save, correct_disk_path


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


TASK_TYPES = {
    'scrub': 'volume.scrub',
    'smart': 'disk.parallel_test',
    'snapshot': 'volume.snapshot_dataset',
    'replication': 'replication.replicate_dataset',
    'check_updates': 'update.checkfetch',
    'command': 'calendar_task.command'
}


TASK_TYPES_REVERSE = {v: k for k, v in list(TASK_TYPES.items())}


TASK_ARG_MAPPING = {
    'volume.scrub': ['volume'],
    'disk.parallel_test': ['disks', 'test_type'],
    'update.checkfetch': ['send_email'],
    'calendar_task.command': ['username', 'command'],
    'volume.snapshot_dataset': ['dataset', 'recursive', 'lifetime', 'prefix', 'replicable']
}


REQUIRED_PROP_TABLE = {
    'scrub': ['volume'],
    'smart': ['disks', 'test_type'],
    'check_updates': ['send_email'],
    'command': ['username', 'command'],
    'snapshot': ['volume', 'dataset', 'recursive', 'lifetime']
}


SKELETON_TASK = {
    'volume.snapshot_dataset': [None, None, None, "auto", False]
}


@description("Runs calendar task right now")
class RunCommand(Command):
    """
    The calendar namespace provides commands for listing and configuring
    tasks that run on a schedule.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.submit_task('calendar_task.run', self.parent.entity['id'])


@description("Task status")
class StatusNamespace(ConfigNamespace):
    def __init__(self, name, context, parent):
        super(StatusNamespace, self).__init__(name, context)
        self.parent = parent

        self.add_property(
            descr='Next run time',
            name='next_run_time',
            get='next_run_time',
            set=None,
            list=True
        )

        self.add_property(
            descr='Last run time',
            name='last_run_time',
            get='last_run_time',
            set=None,
            list=True,
            type=ValueType.TIME
        )

        self.add_property(
            descr='Last run status',
            name='last_run_status',
            get='last_run_status',
            set=None,
            list=True
        )

        self.add_property(
            descr='Current run status',
            name='current_run_status',
            get='current_run_status',
            set=None,
            list=True
        )

        self.add_property(
            descr='Current run progress',
            name='current_run_progress',
            get='current_run_progress',
            set=None,
            list=True
        )

    def load(self):
        self.entity = self.parent.entity['status']


@description("Schedule configuration")
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

        self.add_property(
            descr='Second',
            name='second',
            get='second',
            list=True
        )

        self.add_property(
            descr='Day of Week',
            name='day_of_week',
            get='day_of_week',
            list=True
        )

    def load(self):
        self.entity = self.parent.entity['schedule']

    def save(self):
        self.parent.save()


@description("List and create regularly scheduled tasks")
class CalendarTasksNamespace(RpcBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    """
    The calendar namespace provides commands for listing and creating
    calendar tasks.
    """
    def __init__(self, name, context):
        super(CalendarTasksNamespace, self).__init__(name, context)

        self.context = context
        self.query_call = 'calendar_task.query'
        self.create_task = 'calendar_task.create'
        self.update_task = 'calendar_task.update'
        self.delete_task = 'calendar_task.delete'
        self.required_props = ['name', 'type']
        self.localdoc["CreateEntityCommand"] = ("""\
            Usage: create <name> type=<type> <property>=<value>

            Examples: create myscrub type=scrub volume=mypool
                      create myscrub2 type=scrub volume=mypool schedule={"second":0, "minute":0, "hour":3} enabled=true
                      create myupdate type=check_updates send_email=false
                      create mysmart type=smart disks=ada0,ada1,ada2 test_type=short
                      create mycommand type=command username=myuser command="some useful unix command"
                      create mysnapshot type=snapshot volume=mypool dataset=mypool/mydataset recursive=true lifetime=1h

            Create a calendar task.  
    
            If a schedule is not set, all time values will be set to * (run all the time).
            The schedule property takes a key/value pair with keys of second, minute, hour,
            day_of_month, month, day_of_week, week, and year with values of *, */integer, or
            integer.

            Valid types for calendar task creation include: scrub, smart, snapshot, replication and check_updates.
            - A 'scrub' task requires a valid volume passed with the 'volume' property.
            - A 'smart' task requires a list of valid disks for the 'disks' property and a test type for the 'test_type' property that is one of short, long, conveyance or offline.
            - A 'check_updates' task requires a boolean for the 'send_email' property which tells the task whether or not to send an alert by email when a new update is available.
            - A 'snapshot' task requires a valid volume and dataset to snapshot, a boolean for the 'recursive' property, a string value of [0-9]+[hdmy] for lifetime and optionally a boolean for 'replicable' and a string for the 'prefix'.  """)
        self.localdoc["DeleteEntityCommand"] = ("""\
            Usage: delete <name>

            Example: delete mytask

            Deletes a calendar task.""")
        self.entity_localdoc["SetEntityCommand"] = ("""\
            Usage: set <property>=<value>

            Examples: set enabled=true
                      set coalesce=false
                      set schedule={"month":"*/2","day":5}

            Sets a calendar task property.""")

        self.skeleton_entity = {
            'enabled': False,
            'schedule': { 'coalesce': True, 'year': None, 'month': None, 'day': None, 'week': None, 'hour': None, 'minute': None, 'second': None, 'day_of_week': None}
        }

        self.add_property(
            descr='Name',
            name='name',
            get='id',
            usage=_("""\
            Alphanumeric name for the task which becomes read-only after the task
            is created."""),
            set='id',
            list=True)

        self.add_property(
            descr='Type',
            name='type',
            get='type',
            usage=_("""\
            Indicates the type of task. Allowable values are scrub, smart,
            snapshot, replication, and check_updates."""),
            set=self.set_type,
            list=True)

        self.add_property(
            descr='Arguments',
            name='args',
            get=lambda row: [format_value(i) for i in row['args']],
            set=None,
            list=False
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
            get=self.get_schedule,
            set='schedule',
            list=True,
            type=ValueType.DICT)

        self.add_property(
            descr='Timezone',
            name='timezone',
            get='schedule.timezone',
            list=True)

        self.add_property(
            descr='Enabled',
            name='enabled',
            usage=_("""\
            Can be set to yes or no. By default, new tasks are disabled
            until set to yes."""),
            get='enabled',
            list=True,
            type=ValueType.BOOLEAN)

        self.add_property(
            descr='Volume',
            name='volume',
            get='volume',
            list=False,
            set=self.set_volume,
            condition=lambda e: self.meets_condition(e, 'volume')
        )

        self.add_property(
            descr='Send Email',
            name='send_email',
            get='send_email',
            list=False,
            set=lambda obj, value: self.set_args(obj, value, 'send_email'),
            type=ValueType.BOOLEAN,
            condition=lambda e: self.meets_condition(e, 'send_email')
        )

        self.add_property(
            descr='Disks',
            name='disks',
            get='disks',
            list=False,
            type=ValueType.SET,
            set=self.set_disks,
            condition=lambda e: self.meets_condition(e, 'disks')
        )

        self.add_property(
            descr='SMART Test Type',
            name='test_type',
            get='test_type',
            list=False,
            enum=['short', 'long', 'conveyance', 'offline'],
            set=lambda obj, value: self.set_args(obj, value, 'test_type'),
            condition=lambda e: self.meets_condition(e, 'test_type')
        )

        self.add_property(
            descr='Username',
            name='username',
            get='username',
            list=False,
            set=self.set_username,
            condition=lambda e: self.meets_condition(e, 'username')
        )

        self.add_property(
            descr='Command',
            name='command',
            get='command',
            list=False,
            set=lambda obj, value: self.set_args(obj, value, 'command'),
            condition=lambda e: self.meets_condition(e, 'command')
        )

        self.add_property(
            descr='Dataset',
            name='dataset',
            get='dataset',
            list=False,
            set=lambda obj, value: self.set_args(obj, value, 'dataset'),
            condition=lambda e: self.meets_condition(e, 'dataset')
        )
        
        self.add_property(
            descr='Lifetime',
            name='lifetime',
            get='lifetime',
            list=False,
            set=lambda obj, value: self.set_args(obj, value, 'lifetime'),
            condition=lambda e: self.meets_condition(e, 'lifetime'),
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Recursive',
            name='recursive',
            get='recursive',
            list=False,
            set=lambda obj, value: self.set_args(obj, value, 'recursive'),
            condition=lambda e: self.meets_condition(e, 'recursive'),
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Prefix',
            name='prefix',
            get='prefix',
            list=False,
            set=lambda obj, value: self.set_args(obj, value, 'prefix'),
            condition=lambda e: self.meets_condition(e, 'prefix')
        )

        self.add_property(
            descr='Replicable',
            name='replicable',
            get='replicable',
            list=False,
            set=lambda obj, value: self.set_args(obj, value, 'replicable'),
            condition=lambda e: self.meets_condition(e, 'replicable'),
            type=ValueType.BOOLEAN
        )

        self.primary_key = self.get_mapping('name')
        self.entity_namespaces = lambda this: [
            StatusNamespace('status', self.context, this),
            ScheduleNamespace('schedule', self.context, this)
        ]

        self.entity_commands = lambda this: {
            'run': RunCommand(this)
        }

    def save(self, this, new=False):
        if new:
            if 'timezone' not in this.entity['schedule']:
                this.entity['schedule']['timezone'] = self.context.call_sync('system.general.get_config')['timezone']
            self.context.submit_task(
                self.create_task,
                this.entity,
                callback=lambda s, t: post_save(this, s, t))
            return

        self.context.submit_task(
            self.update_task,
            this.orig_entity[self.save_key_name],
            this.get_diff(),
            callback=lambda s, t: post_save(this, s, t))

    def conditional_required_props(self, kwargs):

        missing_args = []
        if kwargs['type'] in REQUIRED_PROP_TABLE:
            for prop in REQUIRED_PROP_TABLE[kwargs['type']]:
                missing_args.append(prop)
        return missing_args

    def get_schedule(self, entity):
        row = entity['schedule']
        sched = dict({k: v for k, v in row.items() if v != "*" and not isinstance(v, bool)})
        sched.pop('timezone')

        return sched

    def meets_condition(self, entity, prop):
        if prop in TASK_ARG_MAPPING[entity['name']]:
            return True
        else:
            return False

    def set_args(self, entity, args, name):
        if 'args' not in entity:
            entity['args'] = []
            if entity['name'] in SKELETON_TASK and len(entity['args']) < len(TASK_ARG_MAPPING[entity['name']]):
                entity['args'] = SKELETON_TASK[entity['name']]
            else:
                while len(entity['args']) < len(TASK_ARG_MAPPING[entity['name']]):
                    entity['args'].append(None)
        entity['args'][TASK_ARG_MAPPING[entity['name']].index(name)] = args

    def set_type(self, entity, row):
        if row in TASK_TYPES:
            entity['name'] = TASK_TYPES[row]
        else:
            raise CommandException(_("Invalid type, please choose one of: {0}".format([key for key in TASK_TYPES.keys()])))

    def set_username(self, entity, args):
        all_users = [user["username"] for user in self.context.call_sync("user.query")]
        if args not in all_users:
            raise CommandException(_("Invalid user: {0}, see '/ account user show' for a list of users".format(args)))
        self.set_args(entity, args, 'username')

    def set_disks(self, entity, args):
        all_disks = [disk["path"] for disk in self.context.call_sync("disk.query")]
        disks = []
        for disk in args:
            disk = correct_disk_path(disk)
            if disk not in all_disks:
                raise CommandException(_("Invalid disk: {0}, see '/ disk show' for a list of disks".format(disk)))
            disks.append(disk)
        self.set_args(entity, disks, 'disks')

    def set_volume(self, entity, args):
        all_volumes = [volume["id"] for volume in self.context.call_sync("volume.query")]
        if args not in all_volumes:
            raise CommandException(_("Invalid volume: {0}, see '/ volume show' for a list of volumes".format(args)))
        self.set_args(entity, args, 'volume')


def _init(context):
    context.attach_namespace('/', CalendarTasksNamespace('calendar', context))
