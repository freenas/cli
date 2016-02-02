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
from freenas.cli.namespace import Namespace, EntityNamespace, ConfigNamespace, Command, RpcBasedLoadMixin, TaskBasedSaveMixin, description, CommandException
from freenas.cli.output import ValueType, output_msg, output_table, read_value, format_value
from freenas.cli.utils import post_save, correct_disk_path


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


TASK_TYPES = {
    'scrub': 'zfs.pool.scrub',
    'smart': 'disk.test_parallel',
    'snapshot': 'volume.snapshot_dataset',
    'replication': 'replication.replicate_dataset',
    'check_updates': 'update.checkfetch'
}


TASK_TYPES_REVERSE = {v: k for k, v in list(TASK_TYPES.items())}


@description("Runs calendar task right now")
class RunCommand(Command):
    """
    The calendar namespace provides commands for listing and managing
    scheduled tasks. For a list of properties, see 'help properties'.
    """
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

        self.context = context
        self.query_call = 'calendar_task.query'
        self.create_task = 'calendar_task.create'
        self.update_task = 'calendar_task.update'
        self.delete_task = 'calendar_task.delete'
        self.required_props = ['name', 'type']
        self.localdoc["CreateEntityCommand"] = ("""\
            Usage: create <name> type=<type> <property>=<value>

            Examples: create myscrub type=scrub volume=mypool
                      create myscrub2 type=scrub volume=mypool schedule="0 0 3" enabled=true
                      create myupdate type=check_updates send_email=false
                      create mysmart type=smart disks=ada0,ada1,ada2

            Creates a calendar task.  Tasks are disabled by default, you must set enabled=true to turn it on.  If a schedule is not set then all values will be set to * (i.e. run all the time).
            The schedule property takes in values of * */integer and integer appropriate values in the following order: second minute hour day_of_month month day_of_week week year""")
        self.localdoc["DeleteEntityCommand"] = ("""\
            Usage: delete <name>

            Example: delete mytask

            Deletes a calendar task.""")
        self.entity_localdoc["SetEntityCommand"] = ("""\
            Usage: set <property>=<value>

            Examples: set enabled=true
                      set coalesce=false

            Sets a calendar task property.""")

        self.skeleton_entity = {
            'enabled': False,
            'schedule': { 'coalesce': True, 'year': None, 'month': None, 'day': None, 'week': None, 'hour': None, 'minute': None, 'second': None, 'day_of_week': None}
        }

        self.add_property(
            descr='Name',
            name='name',
            get='id',
            usage=_("""Alphanumeric name for the task which becomes
            read-only after the task is created."""),
            set='id',
            list=True)

        self.add_property(
            descr='Type',
            name='type',
            get=lambda row: TASK_TYPES_REVERSE[row['name']],
            usage=_("""Indicates the type of task. Allowable values
            are scrub, smart, snapshot, replication, and
            check_updates."""),
            set=self.set_type,
            list=True)

        self.add_property(
            descr='Arguments',
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
            get=self.get_schedule,
            set=self.set_schedule,
            list=True,
            type=ValueType.STRING)

        self.add_property(
            descr='Enabled',
            name='enabled',
            get='enabled',
            list=True,
            type=ValueType.BOOLEAN)

        self.add_property(
            descr='Volume',
            name='volume',
            get=None,
            list=False,
            set=self.set_volume,
        )

        self.add_property(
            descr='Send Email',
            name='send_email',
            get=None,
            list=False,
            set=self.set_email,
            type=ValueType.BOOLEAN,
        )

        self.add_property(
            descr='Disks',
            name='disks',
            get=None,
            list=False,
            type=ValueType.SET,
            set=self.set_disks,
        )

        self.primary_key = self.get_mapping('name')
        self.entity_namespaces = lambda this: [
            ScheduleNamespace('schedule', self.context, this)
        ]

        self.entity_commands = lambda this: {
            'run': RunCommand()
        }

    def set_schedule(self, entity, row):
        items = row.split(' ')
        i = 0
        sched = {}
        if len(items) > 8:
            raise CommandException("Invalid input: {0}".format(row))
        for item in items:
            if i == 0:
                sched['second'] = item
            elif i == 1:
                sched['minute'] = item
            elif i == 2:
                sched['hour'] = item
            elif i == 3:
                sched['day'] = item
            elif i == 4:
                sched['month'] = item
            elif i == 5:
                sched['day_of_week'] = item
            elif i == 6:
                sched['week'] = item
            elif i == 7:
                sched['year'] = item
            i = i + 1
        entity['schedule'] = sched

    def get_schedule(self, entity):
        row = entity['schedule']
        sched = "{0} {1} {2} {3} {4} {5} {6} {7}".format(
                    row['second'],
                    row['minute'],
                    row['hour'],
                    row['day'],
                    row['month'],
                    row['day_of_week'],
                    row['week'],
                    row['year'])
        return sched

    def set_type(self, entity, row):
        if row in TASK_TYPES:
            entity['name'] = TASK_TYPES[row]
        else:
            raise CommandException(_("Invalid type, please choose one of: {0}".format(TASK_TYPES.keys())))

    def set_email(self, entity, args):
        if args is None:
            args = True
        entity['args'] = [args]

    def set_disks(self, entity, args):
        if args is None:
            raise CommandException(_("Please specify one or more disks for the 'disks' property"))
        else:
            all_disks = [disk["path"] for disk in self.context.call_sync("disk.query")]
            #if not isinstance(args, list):
            #    args = [args]
            disks = []
            for disk in args:
                disk = correct_disk_path(disk)
                if disk not in all_disks:
                    raise CommandException(_("Invalid disk: {0}, see '/ disk show' for a list of disks".format(disk)))
            disks.append(disk)
            entity['args'] = disks

    def set_volume(self, entity, args):
        if args is None:
            raise CommandException(_("Please specify a volume for the 'volume' property"))
        else:
            all_volumes = [volume["name"] for volume in self.context.call_sync("volume.query")]
            if args not in all_volumes:
                raise CommandException(_("Invalid volume: {0}, see '/ volume show' for a list of volumes".format(volume)))
            entity['args'] = [args]
            

def _init(context):
    context.attach_namespace('/', CalendarTasksNamespace('calendar', context))
