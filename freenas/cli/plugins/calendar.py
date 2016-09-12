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

import copy
import gettext
from freenas.cli.namespace import (
    EntityNamespace, Command, TaskBasedSaveMixin, description,
    CommandException, NestedEntityMixin, ItemNamespace, EntitySubscriberBasedLoadMixin
)
from freenas.cli.output import ValueType, format_value
from freenas.utils import first_or_default
from freenas.utils import query as q


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


class CalendarTasksNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The calendar namespace provides commands for listing and creating
    calendar tasks.
    """
    def __init__(self, name, context):
        super(CalendarTasksNamespace, self).__init__(name, context)
        self.context = context
        self.entity_subscriber_name = 'calendar_task'
        self.allow_create = False
        self.primary_key_name = 'name'
        self.has_entities_in_subnamespaces_only = True

        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all smart tasks. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == somename
                show | search enabled == yes""")

        self.add_property(
            descr='Type',
            name='type',
            get=CalendarTasksNamespaceBaseClass.get_type,
            usage=_("""\
            Indicates the type of task."""),
            set=None,
            list=True
        )

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            usage=_("""\
            Alphanumeric name for the task which becomes read-only after the task
            is created."""),
            set='name',
            list=True
        )

        self.add_property(
            descr='Schedule',
            name='schedule',
            get=CalendarTasksNamespaceBaseClass.get_schedule,
            set='schedule',
            list=True,
            type=ValueType.DICT
        )

        self.add_property(
            descr='Enabled',
            name='enabled',
            usage=_("""\
            Can be set to yes or no. By default, new tasks are disabled
            until set to yes."""),
            get='enabled',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.primary_key = self.get_mapping('name')

    def namespaces(self):
        return [
            ScrubNamespace('scrub', self.context),
            SmartNamespace('smart', self.context),
            SnapshotNamespace('snapshot', self.context),
            ReplicationNamespace('replication', self.context),
            CheckUpdateNamespace('check_update', self.context),
            CommandNamespace('command', self.context),
        ]


class CalendarTasksNamespaceBaseClass(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    local_timezone = False
    def __init__(self, name, context):
        super(CalendarTasksNamespaceBaseClass, self).__init__(name, context)
        self.context = context
        self.entity_subscriber_name = 'calendar_task'
        self.create_task = 'calendar_task.create'
        self.update_task = 'calendar_task.update'
        self.delete_task = 'calendar_task.delete'
        self.required_props = ['name']
        self.task_args_helper = []
        self.skeleton_entity = {
            'enabled': False,
            'args': [],
        }
        self.primary_key_name = 'name'

        if not CalendarTasksNamespaceBaseClass.local_timezone:
            CalendarTasksNamespaceBaseClass.local_timezone = self.context.call_sync(
                'system.general.get_config').get('timezone', "UTC")

        self.entity_localdoc["DeleteEntityCommand"] = ("""\
            Usage: delete

            Example: delete

            Deletes a calendar task.""")

        self.entity_localdoc["SetEntityCommand"] = ("""\
            Usage: set <property>=<value>

            Examples: set enabled=true

            Sets a calendar task property.""")

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            usage=_("""\
            Alphanumeric name for the task which becomes read-only after the task
            is created."""),
            set='name',
            list=True
        )

        self.add_property(
            descr='Schedule',
            name='schedule',
            get=self.get_schedule,
            set='schedule',
            list=True,
            type=ValueType.DICT
        )

        self.add_property(
            descr='Enabled',
            name='enabled',
            usage=_("""\
            Can be set to yes or no. By default, new tasks are disabled
            until set to yes."""),
            get='enabled',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.primary_key = self.get_mapping('name')

        self.entity_namespaces = lambda this: [
            CalendarTasksScheduleNamespace('schedule', self.context, this),
            CalendarTasksStatusNamespace('status', self.context, this),
        ]

        self.entity_commands = lambda this: {
            'run': RunCommand(this)
        }

        self._load_nested_skeleton_entities()

    def set_task_args(self, entity, args, name):
        idx = self._get_args_index(name)
        if not entity['args']:
            entity['args'] = self.task_args_helper[:]
        entity['args'].pop(idx)
        entity['args'].insert(idx, args)

    def get_task_args(self, entity, name):
        idx = self._get_args_index(name)
        return entity['args'][idx]

    def _load_nested_skeleton_entities(self):
        for n in self.entity_namespaces(self):
            self.skeleton_entity.update(n.skeleton_entity) if hasattr(n, 'skeleton_entity') else None

    def _get_args_index(self, arg_name):
        return self.task_args_helper.index(arg_name)

    @staticmethod
    def get_schedule(entity):
        row = entity['schedule']
        sched = dict({k: v for k, v in row.items() if v != "*" and not isinstance(v, bool)})
        sched.pop('timezone')
        return sched

    @staticmethod
    def get_type(entity):
        return TASK_TYPES_REVERSE[entity['task']]


class CalendarTasksScheduleNamespace(NestedEntityMixin, ItemNamespace):
    """
    The schedule namespaces provides commands for setting schedule of selected calendar task

    If a schedule is not set, all time values will be set to `*` (run all the time).
    The schedule property takes a key/value pair with keys of second, minute, hour,
    day_of_month, month, day_of_week, week, and year with values of `*`, `*/integer`, or
    integer.

    Examples:
        set coalesce=no
        set hour="`*/2`"
    """
    def __init__(self, name, context, parent):
        super(CalendarTasksScheduleNamespace, self).__init__(name, context)
        self.context = context
        self.parent = parent
        self.parent_entity_path = 'schedule'
        self.skeleton_entity = {
            'schedule': {
                'coalesce': True,
                'timezone': CalendarTasksNamespaceBaseClass.local_timezone,
                'year': None,
                'month': None,
                'day': None,
                'week': None,
                'hour': None,
                'minute': None,
                'second': None,
                'day_of_week': None,
            }
        }

        self.localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set coalesce=no
                      set month="*/2"
                      set day=5
                      set timezone=America/New_York

            Sets a schedule property. For a list of properties, see 'help properties'.""")


        self.add_property(
            descr='Coalesce',
            name='coalesce',
            get='coalesce',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Timezone',
            name='timezone',
            get='timezone',
            list=True
        )

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


class CalendarTasksStatusNamespace(NestedEntityMixin, ItemNamespace):
    def __init__(self, name, context, parent):
        super(CalendarTasksStatusNamespace, self).__init__(name, context)
        self.context = context
        self.parent = parent
        self.parent_entity_path = 'status'
        #self.skeleton_entity = {
        #    'status': {'next_run_time': "",
        #               'last_run_time': "",
        #               'last_run_status': "",
        #               'current_run_status': None,
        #               'current_run_progress': None}
        #}

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


class ScrubNamespace(CalendarTasksNamespaceBaseClass):
    """
    Scrub namespaces provides commands to create 'scrub' type calendar tasks
    A 'scrub' task requires a valid volume passed with the 'volume' property.

    Usage:
        create <name> volume=<volume> <property>=<value>

    Examples:
        create myscrub volume=mypool
    """
    def __init__(self, name, context):
        super(ScrubNamespace, self).__init__(name, context)
        self.extra_query_params = [('task', '=', 'volume.scrub')]
        self.required_props.extend(['volume'])
        self.skeleton_entity['task'] = 'volume.scrub'
        self.task_args_helper = ['volume']
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> disks=<disks> volume=<volume> <property>=<value>

            Examples: create myscrub volume=mypool
                      create somescrub volume=somepool schedule={"hour":2,"day_of_week":5}
            
            Creates a scrub calendar task. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set name=otherscrub
                      set enabled=true

            Sets a scrub calendar task property. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['GetEntityCommand'] = ("""\
            Usage: get <field>

            Examples:
                get volume
                get name

            Display value of specified field.""")
        self.entity_localdoc['EditEntityCommand'] = ("""\
            Usage: edit <field>

            Examples: edit name

            Opens the default editor for the specified property. The default editor
            is inherited from the shell's $EDITOR which can be set from the shell.
            For a list of properties for the current namespace, see 'help properties'.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all smart tasks. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == somename""")

        self.add_property(
            descr='Volume',
            name='volume',
            get=lambda obj: self.get_task_args(obj, 'volume'),
            list=True,
            set=lambda obj, val: self.set_task_args(obj, val, 'volume'),
            enum=[v for v in self.query([], {'subscriber': 'volume', 'select': 'id'})]
        )


class SmartNamespace(CalendarTasksNamespaceBaseClass):
    """
    SMART namespaces provides commands to create 'smart' type calendar tasks
    A 'smart' task requires a list of valid disks for the 'disks' property and
    a test type for the 'test_type' property that is one of short, long, conveyance
    or offline.

    Usage: create <name> disks=<disks> test_type=<test_type>

    Examples: create mysmart disks=ada0,ada1,ada2 test_type=SHORT
              create somesmart disks=ada0,ada1,ada2 rest_type=LONG schedule={"hour":3}
    """
    def __init__(self, name, context):
        super(SmartNamespace, self).__init__(name, context)
        self.extra_query_params = [('task', '=', 'disk.parallel_test')]
        self.required_props.extend(['disks', 'test_type'])
        self.skeleton_entity['task'] = 'disk.parallel_test'
        self.task_args_helper = ['disks', 'test_type']
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> disks=<disks> test_type=<test_type> <property>=<value>

            Examples: create mysmart disks=ada0,ada1,ada2 test_type=SHORT
                      create somesmart disks=ada0,ada1,ada2 test_type=LONG schedule={"hour":"*/4"}
            
            Creates a SMART calendar task. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set test_type=LONG
                      set disks=ada1,ada2
                      set enabled=true

            Sets a SMART calendar task property. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['GetEntityCommand'] = ("""\
            Usage: get <field>

            Examples:
                get test_type
                get disks

            Display value of specified field.""")
        self.entity_localdoc['EditEntityCommand'] = ("""\
            Usage: edit <field>

            Examples: edit name

            Opens the default editor for the specified property. The default editor
            is inherited from the shell's $EDITOR which can be set from the shell.
            For a list of properties for the current namespace, see 'help properties'.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all smart tasks. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == somename""")

        self.add_property(
            descr='Disks',
            name='disks',
            get=lambda obj: self.get_disks(obj),
            list=True,
            type=ValueType.SET,
            set=lambda obj, val: self.set_disks(obj, val),
            enum=[d for d in self.query([], {'subscriber': 'disk', 'select': 'name'})]
        )

        self.add_property(
            descr='SMART Test Type',
            name='test_type',
            get=lambda obj: self.get_task_args(obj, 'test_type'),
            list=True,
            set=lambda obj, val: self.set_task_args(obj, val, 'test_type'),
            enum=['SHORT', 'LONG', 'CONVEYANCE', 'OFFLINE']
        )

    def get_disks(self, obj):
        disks_ids = self.get_task_args(obj, 'disks')
        disks_names = []
        for i in disks_ids:
            disks_names.append(self.query([('id', '=', i)], {'subscriber': 'disk', 'select': 'name', 'single': True}))
        return disks_names

    def set_disks(self, obj, disks_names):
        all_disks = [d for d in self.query([], {'subscriber': 'disk', 'select': 'name'})]
        disk_ids = []
        for d in disks_names:
            if d not in all_disks:
                raise CommandException(_("Invalid disk: {0}, see '/ disk show' for a list of disks".format(d)))
            disk_ids.append(self.context.call_sync('disk.path_to_id', d))
        self.set_task_args(obj, disk_ids, 'disks')


class SnapshotNamespace(CalendarTasksNamespaceBaseClass):
    """
    Snapshot namespaces provides commands to create 'snapshot' type calendar tasks
    A 'snapshot' task requires a valid dataset to snapshot, a boolean for the 'recursive' property,
    a string value of [0-9]+[hdmy] for lifetime and optionally a boolean for 'replicable' and a string for the 'prefix'.

    Usage: create <name> dataset=<dataset> <property>=<value>

    Examples:   create mysnapshot dataset=mypool schedule={"minute":"`*/30`"}
                create somesnapshot dataset=mypool/mydataset recursive=yes lifetime=1h schedule={"minute":"0"}
    """
    def __init__(self, name, context):
        super(SnapshotNamespace, self).__init__(name, context)
        self.extra_query_params = [('task', '=', 'volume.snapshot_dataset')]
        self.required_props.extend(['dataset'])
        self.skeleton_entity['task'] = 'volume.snapshot_dataset'
        self.skeleton_entity['args'] = ["", False, None, 'auto', False]
        self.task_args_helper = ['dataset', 'recursive', 'lifetime', 'prefix', 'replicable']
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> dataset=<dataset> <property>=<value>

            Examples:   create mysnapshot dataset=mypool
                        create somesnapshot dataset=mypool/mydataset recursive=yes lifetime=1h schedule={"minute":"0"}

            Creates a snapshot calendar task. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set lifetime=2h
                      set name=newname
                      set enabled=true

            Sets a snapshot calendar task property. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['GetEntityCommand'] = ("""\
            Usage: get <field>

            Examples:
                get lifetime
                get dataset

            Display value of specified field.""")
        self.entity_localdoc['EditEntityCommand'] = ("""\
            Usage: edit <field>

            Examples: edit name

            Opens the default editor for the specified property. The default editor
            is inherited from the shell's $EDITOR which can be set from the shell.
            For a list of properties for the current namespace, see 'help properties'.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all snapshot tasks. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == somename""")

        self.add_property(
            descr='Dataset',
            name='dataset',
            get=lambda obj: self.get_task_args(obj, 'dataset'),
            list=True,
            set=lambda obj, val: self.set_task_args(obj, val, 'dataset'),
        )

        self.add_property(
            descr='Lifetime',
            name='lifetime',
            get=lambda obj: self.get_task_args(obj, 'lifetime'),
            list=True,
            set=lambda obj, val: self.set_task_args(obj, val, 'lifetime'),
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Recursive',
            name='recursive',
            get=lambda obj: self.get_task_args(obj, 'recursive'),
            list=True,
            set=lambda obj, val: self.set_task_args(obj, val, 'recursive'),
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Prefix',
            name='prefix',
            get=lambda obj: self.get_task_args(obj, 'prefix'),
            list=True,
            set=lambda obj, val: self.set_task_args(obj, val, 'prefix'),
        )

        self.add_property(
            descr='Replicable',
            name='replicable',
            get=lambda obj: self.get_task_args(obj, 'replicable'),
            list=True,
            set=lambda obj, val: self.set_task_args(obj, val, 'replicable'),
            type=ValueType.BOOLEAN
        )


class ReplicationNamespace(CalendarTasksNamespaceBaseClass):
    """
    Replication namespaces provides commands to create 'replication' type calendar tasks

    Usage: create <name> <property>=<value>

    Examples:
        create myrepl dataset=mypool/dataset remote_dataset=otherpool/bak peer=mypeer recursive=yes schedule={"minute": "`*/30`"}
    """
    def __init__(self, name, context):
        super(ReplicationNamespace, self).__init__(name, context)
        self.extra_query_params = [('task', '=', 'replication.replicate_dataset')]
        self.required_props.extend([])
        self.task_args_helper = ['dataset', 'options', 'transport_options']
        self.skeleton_entity['task'] = 'replication.replicate_dataset'
        self.skeleton_entity['args'] = [
            None,
            {
                'remote_dataset': None,
                'peer': None,
                'recursive': False,
                'followdelete': False
            },
            []
        ]

        def get_peer_name(id):
            peer = self.context.entity_subscribers['peer'].query(('id', '=', id), single=True)
            return peer['name'] if peer else None

        def set_peer_id(name):
            peer = self.context.entity_subscribers['peer'].query(('name', '=', name), single=True)
            if not peer:
                raise CommandException('Peer {0} not found'.format(name))

            return peer['id']

        def get_transport_option(obj, type, property):
            opt = first_or_default(lambda i: i['name'] == type, obj['args'][2])
            return opt[property] if opt else None

        def set_transport_option(obj, type, property, value):
            opt = first_or_default(lambda i: i['name'] == type, obj['args'][2])

            if value:
                if opt:
                    opt[property] = value
                else:
                    obj['args'][2].append({
                        'name': type,
                        property: value
                    })
            else:
                obj['args'][2].remove(opt)

            obj['args'] = copy.copy(obj['args'])

        self.add_property(
            descr='Local dataset',
            name='dataset',
            get=lambda obj: self.get_task_args(obj, 'dataset'),
            list=True,
            set=lambda obj, val: self.set_task_args(obj, val, 'dataset'),
        )

        self.add_property(
            descr='Remote dataset',
            name='remote_dataset',
            get=lambda obj: q.get(self.get_task_args(obj, 'options'), 'remote_dataset'),
            list=True,
            set=lambda obj, val: q.set(self.get_task_args(obj, 'options'), 'remote_dataset', val),
        )

        self.add_property(
            descr='Peer name',
            name='peer',
            get=lambda obj: get_peer_name(q.get(self.get_task_args(obj, 'options'), 'peer')),
            list=True,
            set=lambda obj, val: q.set(self.get_task_args(obj, 'options'), 'peer', set_peer_id(val)),
        )

        self.add_property(
            descr='Recursive',
            name='recursive',
            get=lambda obj: q.get(self.get_task_args(obj, 'options'), 'recursive'),
            list=True,
            set=lambda obj, val: q.set(self.get_task_args(obj, 'options'), 'recursive', val),
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Follow delete',
            name='followdelete',
            get=lambda obj: q.get(self.get_task_args(obj, 'options'), 'followdelete'),
            list=False,
            set=lambda obj, val: q.set(self.get_task_args(obj, 'options'), 'followdelete', val),
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Compression',
            name='compression',
            get=lambda obj: get_transport_option(obj, 'compress', 'level'),
            list=False,
            set=lambda obj, val: set_transport_option(obj, 'compress', 'level', val),
            enum=['FAST', 'DEFAULT', 'BEST', None]
        )

        self.add_property(
            descr='Encryption',
            name='encryption',
            get=lambda obj: get_transport_option(obj, 'encryption', 'type'),
            list=False,
            set=lambda obj, val: set_transport_option(obj, 'encryption', 'type', val),
            enum=['AES128', 'AES192', 'AES256', None]
        )

        self.add_property(
            descr='Throttle',
            name='throttle',
            get=lambda obj: get_transport_option(obj, 'throttle', 'buffer_size'),
            list=False,
            set=lambda obj, val: set_transport_option(obj, 'throttle', 'buffer_size', val),
            type=ValueType.SIZE
        )


class CheckUpdateNamespace(CalendarTasksNamespaceBaseClass):
    """
    CheckUpdate namespaces provides commands to create 'check_update' type calendar tasks

    Usage: create <name> <property>=<value>

    Examples: create myupdate schedule={"hour":1}
    """
    def __init__(self, name, context):
        super(CheckUpdateNamespace, self).__init__(name, context)
        self.extra_query_params = [('task', '=', 'update.checkfetch')]
        self.skeleton_entity['task'] = 'update.checkfetch'
        self.skeleton_entity['args'] = []
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> <property>=<value>

            Examples: create myupdate schedule={"hour":1}
            
            Creates a update calendar task. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set name=newname
                      set enabled=true

            Sets a update calendar task property. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['GetEntityCommand'] = ("""\
            Usage: get <field>

            Examples:
                get name

            Display value of specified field.""")
        self.entity_localdoc['EditEntityCommand'] = ("""\
            Usage: edit <field>

            Examples: edit name

            Opens the default editor for the specified property. The default editor
            is inherited from the shell's $EDITOR which can be set from the shell.
            For a list of properties for the current namespace, see 'help properties'.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all smart tasks. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == somename""")


class CommandNamespace(CalendarTasksNamespaceBaseClass):
    """
    Command namespaces provides commands to create 'command' type calendar tasks

    Usage: create <name> username=<username> command=<command> <property>=<value>

    Examples: create mycommand username=myuser command="ls -l" schedule={"minute":"`*/5`"}
    """
    def __init__(self, name, context):
        super(CommandNamespace, self).__init__(name, context)
        self.extra_query_params = [('task', '=', 'calendar_task.command')]
        self.required_props.extend(['username', 'command'])
        self.skeleton_entity['task'] = 'calendar_task.command'
        self.task_args_helper = ['username', 'command']
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> username=<username> command=<command> <property>=<value>

            Examples: create mycommand username=myuser command="ls -l" schedule={"minute":"*/5"}
            
            Creates a command calendar task. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set command="cowsay moo"
                      set username=someuser
                      set enabled=true

            Sets a command calendar task property. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['GetEntityCommand'] = ("""\
            Usage: get <field>

            Examples:
                get command
                get username

            Display value of specified field.""")
        self.entity_localdoc['EditEntityCommand'] = ("""\
            Usage: edit <field>

            Examples: edit name

            Opens the default editor for the specified property. The default editor
            is inherited from the shell's $EDITOR which can be set from the shell.
            For a list of properties for the current namespace, see 'help properties'.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all smart tasks. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == somename""")

        self.add_property(
            descr='Username',
            name='username',
            get=lambda obj: self.get_task_args(obj, 'username'),
            list=True,
            set=lambda obj, val: self.set_task_args(obj, val, 'username'),
        )

        self.add_property(
            descr='Command',
            name='command',
            get=lambda obj: self.get_task_args(obj, 'command'),
            list=True,
            set=lambda obj, val: self.set_task_args(obj, val, 'command'),
        )


TASK_TYPES = {
    'scrub': 'volume.scrub',
    'smart': 'disk.parallel_test',
    'snapshot': 'volume.snapshot_dataset',
    'replication': 'replication.replicate_dataset',
    'check_update': 'update.checkfetch',
    'command': 'calendar_task.command'
}


TASK_TYPES_REVERSE = {v: k for k, v in list(TASK_TYPES.items())}


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


def _init(context):
    context.attach_namespace('/', CalendarTasksNamespace('calendar', context))
