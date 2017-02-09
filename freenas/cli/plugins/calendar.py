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
from freenas.cli.complete import EntitySubscriberComplete
from freenas.cli.output import ValueType
from freenas.cli.utils import TaskPromise, objname2id, objid2name
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
            RsyncNamespace('rsync', self.context),
            SmartNamespace('smart', self.context),
            SnapshotNamespace('snapshot', self.context),
            ReplicationNamespace('replication', self.context),
            CheckUpdateNamespace('check_update', self.context),
            CommandNamespace('command', self.context),
            BackupNamespace('backup', self.context),
        ]


class CalendarTasksNamespaceBaseClass(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
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
            'enabled': True,
            'args': [],
        }
        self.primary_key_name = 'name'

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
        if not entity.get('schedule'):
            return {}
        sched = dict({k: v for k, v in entity.get('schedule', {}).items() if v != "*" and not isinstance(v, bool)})
        sched.pop('timezone')
        return sched

    @staticmethod
    def get_type(entity):
        try:
            return TASK_TYPES_REVERSE[entity['task']]
        except KeyError:
            return


class CalendarTasksScheduleNamespace(NestedEntityMixin, ItemNamespace):
    """
    The schedule namespaces provides commands for setting schedule of selected calendar task

    If a schedule is not set, all time values will be set to `*` - which is treated as
    empty schedule, and the task will be disabled.
    A task which is enabled and has it's schedule edited to 'empty' will also be
    silently disabled.
    The schedule property takes a key/value pair with keys of second, minute, hour,
    day_of_month, month, day_of_week, week, and year with values of `*`, `*/integer`, integer or
    a string representing comma separated integer values.

    Examples:
        set coalesce=no
        set hour="`*/2`"
        set minute="2,20,24"
    """
    def __init__(self, name, context, parent):
        super(CalendarTasksScheduleNamespace, self).__init__(name, context)
        self.context = context
        self.parent = parent
        self.parent_entity_path = 'schedule'
        self.skeleton_entity = {
            'schedule': {
                'coalesce': True,
                'timezone': None,
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
                      set minute="2,20,24"
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
            usersetable=False,
            createsetable=False,
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
        create myscrub volume=mypool schedule={"hour":2,"day_of_week":5}
        create myscrub volume=mypool schedule={"hour":"2,12","day_of_week":5}
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
                      create somescrub volume=somepool schedule={"hour":"2,12","day_of_week":5}

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

        self.add_property(
            descr='Volume',
            name='volume',
            get=lambda obj: self.get_task_args(obj, 'volume'),
            list=True,
            set=lambda obj, val: self.set_task_args(obj, val, 'volume'),
            complete=EntitySubscriberComplete('volume=', 'volume')
        )


class RsyncNamespace(CalendarTasksNamespaceBaseClass):
    """
    Rsync calendar namespace provides commands to create `rsync` type calendar tasks.
    An `rsync` task requires various parameters to be specified for the actual rsync push/pull
    operation.
    It also requires public keys to be exachged between hosts for ssh transport.

    Usage:
        create <name> user=<user> path=<path> direction=<PUSH|PULL> mode=<SSH|MODULE>
            remote_host=<remote_host> remote_user=<remote_user> remote_path=<remote_path>
            remote_module=<remote_module> remote_ssh_port=<remote_ssh_port_number>
            recursive=<yes|no> compress=<yes|no> times=<yes|no> archive=<yes|no>
            rsync_delete=<yes|no> preserve_permissions=<yes|no> preserve_attributes=<yes|no>
            delay_updates=<yes|no> extra=<string containing extra rsync options>
            <property>=<value>

    Examples:
        create myrsync user=myuser path=/mnt/mypool/sourcedir direction=PUSH mode=SSH remote_host=myremotehost
            remote_user=myremoteuser remote_path=/mnt/mypool/targetdir schedule={"day":"1,3,5"}
    """

    def get_rsync_args(self, entity, name):
        return q.get(entity['args'][0], name)

    def set_rsync_args(self, entity, name, value):
        q.set(entity['args'][0], name, value)

    def __init__(self, name, context):
        super(RsyncNamespace, self).__init__(name, context)
        self.extra_query_params = [('task', '=', 'rsync.copy')]
        self.required_props.extend(['user', 'path', 'remote_host', 'direction', 'mode'])
        self.skeleton_entity['task'] = 'rsync.copy'
        self.skeleton_entity['args'] = [{}]
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage:
                create <name> user=<user> path=<path> direction=<PUSH|PULL> mode=<SSH|MODULE>
                    remote_host=<remote_host> remote_user=<remote_user> remote_path=<remote_path>
                    remote_module=<remote_module> remote_ssh_port=<remote_ssh_port_number>
                    recursive=<yes|no> compress=<yes|no> times=<yes|no> archive=<yes|no>
                    rsync_delete=<yes|no> preserve_permissions=<yes|no> preserve_attributes=<yes|no>
                    delay_updates=<yes|no> extra=<string containing extra rsync options>
                    <property>=<value>

            Examples:
                create myrsync user=myuser path=/mnt/mypool/sourcedir direction=PUSH mode=SSH remote_host=myotherhost
                    remote_user=myremoteuser remote_path=/mnt/mypool/targetdir

        """)

        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage:
                set <preoperty>=<value> ...

            Examples:
                set user=testuser
        """)

        self.entity_localdoc['GetEntityCommand'] = ("""\
            Usage: get <field>

            Examples:
                get test_type
                get disks

            Display value of specified field.""")

        self.add_property(
            descr='User',
            name='user',
            get=lambda obj: self.get_rsync_args(obj, 'user'),
            set=lambda obj, val: self.set_rsync_args(obj, 'user', val),
            list=False,
            type=ValueType.STRING,
            usage=_('Username underwhich the rsync task should be executed')
        )

        self.add_property(
            descr='Remote Rsync User',
            name='remote_user',
            get=lambda obj: self.get_rsync_args(obj, 'remote_user'),
            set=lambda obj, val: self.set_rsync_args(obj, 'remote_user', val),
            type=ValueType.STRING,
            list=False,
            usage=_(
                'Username underwhich the rsync operation should be carried out'
                ' at the remote host (could very well be a local user if the'
                ' task is copying to/from local volumes)'
            )
        )

        self.add_property(
            descr='Direction',
            name='direction',
            get=lambda obj: self.get_rsync_args(obj, 'rsync_direction'),
            set=lambda obj, val: self.set_rsync_args(obj, 'rsync_direction', val),
            type=ValueType.STRING,
            list=True,
            enum=['PUSH', 'PULL'],
            usage=_('States and Controls whether this rsync task is a PUSH or a PULL')
        )

        self.add_property(
            descr='Rsync Mode',
            name='mode',
            get=lambda obj: self.get_rsync_args(obj, 'rsync_mode'),
            set=lambda obj, val: self.set_rsync_args(obj, 'rsync_mode', val),
            type=ValueType.STRING,
            list=False,
            enum=['MODULE', 'SSH'],
            usage=_('States and Controls the transport medium for this rsync task')
        )

        self.add_property(
            descr='Remote Host',
            name='remote_host',
            get=lambda obj: self.get_rsync_args(obj, 'remote_host'),
            set=lambda obj, val: self.set_rsync_args(obj, 'remote_host', val),
            type=ValueType.STRING,
            list=False,
            usage=_(
                'Specifies the remote host for this rsync task'
                ' (could very well be the localhost itself if'
                ' the task is copying to & from local volumes)'
            )
        )

        self.add_property(
            descr='Path',
            name='path',
            get=lambda obj: self.get_rsync_args(obj, 'path'),
            set=lambda obj, val: self.set_rsync_args(obj, 'path', val),
            type=ValueType.STRING,
            list=True,
            usage=_('Specifies the path on the localhost to copy to/from for this rsync task')
        )

        self.add_property(
            descr='Remote Path',
            name='remote_path',
            get=lambda obj: self.get_rsync_args(obj, 'remote_path'),
            set=lambda obj, val: self.set_rsync_args(obj, 'remote_path', val),
            type=ValueType.STRING,
            condition=lambda obj: q.get(obj['args'][0], 'rsync_mode') == 'SSH',
            list=False,
            usage=_(
                'Specifies the path on the Remote Host to copy'
                ' to/from for this rsync task (could very well '
                ' be the localhost itself if the task is copying '
                ' to/from local volumes). NOTE: This is only used'
                ' if the rsync mode is SSH'
            )
        )

        self.add_property(
            descr='Remote SSH Port',
            name='remote_ssh_port',
            get=lambda obj: self.get_rsync_args(obj, 'remote_ssh_port'),
            set=lambda obj, val: self.set_rsync_args(obj, 'remote_ssh_port', val),
            type=ValueType.NUMBER,
            condition=lambda obj: q.get(obj['args'][0], 'remote_ssh_port') == 'SSH',
            list=False,
            usage=_(
                '(Optional) Specifies Remote Host\'s rsync port.'
                ' Only needed in case the remote host has non-standard ssh port setup'
            )
        )

        self.add_property(
            descr='Remote Module',
            name='remote_module',
            get=lambda obj: self.get_rsync_args(obj, 'remote_module'),
            set=lambda obj, val: self.set_rsync_args(obj, 'remote_module', val),
            type=ValueType.STRING,
            condition=lambda obj: q.get(obj['args'][0], 'rsync_mode') == 'MODULE',
            list=False,
            usage=_(
                'Specifies the module on the Remote Host to copy'
                ' to/from for this rsync task (could very well '
                ' be the local rsync module itself if the task is copying '
                ' to/from local volumes). NOTE: This is only used'
                ' if the rsync mode is MODULE'
            )
        )

        self.add_property(
            descr='Recursive (rsync property)',
            name='recursive',
            get=lambda obj: self.get_rsync_args(obj, 'rsync_properties.recursive'),
            set=lambda obj, val: self.set_rsync_args(obj, 'rsync_properties.recursive', val),
            type=ValueType.BOOLEAN,
            list=False,
            usage=_('Specifies the boolean rsync property: recursive')
        )

        self.add_property(
            descr='Compress (rsync property)',
            name='compress',
            get=lambda obj: self.get_rsync_args(obj, 'rsync_properties.compress'),
            set=lambda obj, val: self.set_rsync_args(obj, 'rsync_properties.compress', val),
            type=ValueType.BOOLEAN,
            list=False,
            usage=_('Specifies the boolean rsync property: compress')
        )

        self.add_property(
            descr='Times (rsync property)',
            name='times',
            get=lambda obj: self.get_rsync_args(obj, 'rsync_properties.times'),
            set=lambda obj, val: self.set_rsync_args(obj, 'rsync_properties.times', val),
            type=ValueType.BOOLEAN,
            list=False,
            usage=_('Specifies the boolean rsync property: times')
        )

        self.add_property(
            descr='Archive (rsync property)',
            name='archive',
            get=lambda obj: self.get_rsync_args(obj, 'rsync_properties.archive'),
            set=lambda obj, val: self.set_rsync_args(obj, 'rsync_properties.archive', val),
            type=ValueType.BOOLEAN,
            list=False,
            usage=_('Specifies the boolean rsync property: archive')
        )

        self.add_property(
            descr='Delete (rsync property)',
            name='rsync_delete',
            get=lambda obj: self.get_rsync_args(obj, 'rsync_properties.delete'),
            set=lambda obj, val: self.set_rsync_args(obj, 'rsync_properties.delete', val),
            type=ValueType.BOOLEAN,
            list=False,
            usage=_('Specifies the boolean rsync property: delete')
        )

        self.add_property(
            descr='Preserve Permissions (rsync property)',
            name='preserve_permissions',
            get=lambda obj: self.get_rsync_args(obj, 'rsync_properties.preserve_permissions'),
            set=lambda obj, val: self.set_rsync_args(obj, 'rsync_properties.preserve_permissions', val),
            type=ValueType.BOOLEAN,
            list=False,
            usage=_('Specifies the boolean rsync property: preserve permissions')
        )

        self.add_property(
            descr='Preserve Attributes (rsync property)',
            name='preserve_attributes',
            get=lambda obj: self.get_rsync_args(obj, 'rsync_properties.preserve_attributes'),
            set=lambda obj, val: self.set_rsync_args(obj, 'rsync_properties.preserve_attributes', val),
            type=ValueType.BOOLEAN,
            list=False,
            usage=_('Specifies the boolean rsync property: preserve_attributes')
        )

        self.add_property(
            descr='Delay Updates (rsync property)',
            name='delay_updates',
            get=lambda obj: self.get_rsync_args(obj, 'rsync_properties.delay_updates'),
            set=lambda obj, val: self.set_rsync_args(obj, 'rsync_properties.delay_updates', val),
            type=ValueType.BOOLEAN,
            list=False,
            usage=_('Specifies the boolean rsync property: delay_updates')
        )

        self.add_property(
            descr='Extra Rsync args',
            name='extra',
            get=lambda obj: self.get_rsync_args(obj, 'rsync_properties.extra'),
            set=lambda obj, val: self.set_rsync_args(obj, 'rsync_properties.extra', val),
            type=ValueType.STRING,
            list=False,
            usage=_('Specifies any other custom arguments for this rsync task.')
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
              create somesmart disks=ada0,ada1,ada2 rest_type=LONG schedule={"hour":"3,20"}
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
                      create somesmart disks=ada0,ada1,ada2 test_type=LONG schedule={"hour":"3,20"}

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

        self.add_property(
            descr='Disks',
            name='disks',
            get=lambda obj: self.get_disks(obj),
            list=True,
            type=ValueType.SET,
            set=lambda obj, val: self.set_disks(obj, val),
            complete=EntitySubscriberComplete('disks=', 'disk', lambda i: i['name'])
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
        return self.context.entity_subscribers['disk'].query(
            ('id', 'in', self.get_task_args(obj, 'disks')),
            select='name'
        )

    def set_disks(self, obj, disk_names):
        all_disks = self.context.entity_subscribers['disk'].query(select='name')
        for d in disk_names:
            if d not in all_disks:
                raise CommandException(_("Invalid disk: {0}, see '/ disk show' for a list of disks".format(d)))

        self.set_task_args(
            obj,
            self.context.entity_subscribers['disk'].query(('name', 'in', list(disk_names)), select='id'),
            'disks'
        )


class SnapshotNamespace(CalendarTasksNamespaceBaseClass):
    """
    Snapshot namespaces provides commands to create 'snapshot' type calendar tasks
    A 'snapshot' task requires a valid dataset to snapshot, a boolean for the 'recursive' property,
    a string value of [0-9]+[hdmy] for lifetime and optionally a boolean for 'replicable' and a string for the 'prefix'.

    Usage: create <name> dataset=<dataset> <property>=<value>

    Examples:   create mysnapshot dataset=mypool schedule={"minute":"`*/30`"}
                create somesnapshot dataset=mypool/mydataset recursive=yes lifetime=1h schedule={"minute":"0"}
                create othersnapshot dataset=mypool/mydataset schedule={"minute":"1,30,50"}
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
                        create somesnapshot dataset=mypool/mydataset schedule={"minute":"1,30,50"}

            Creates a snapshot calendar task. For a list of properties, see 'help properties'.""")

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
    The calendar task is created by pointing to a replication object and assigning a schedule.
    The replication object defines the details of the given replication task
    and can be created in the 'replication' namespace.

    Usage: create <name> <property>=<value>

    Examples:
        create myrepl replication=my_replication schedule={"day": "`*/30`"}
    """
    def __init__(self, name, context):
        super(ReplicationNamespace, self).__init__(name, context)
        self.extra_query_params = [('task', '=', 'replication.sync')]
        self.required_props.extend(['replication'])
        self.skeleton_entity['task'] = 'replication.sync'
        self.task_args_helper = ['replication']

        self.add_property(
            descr='Replication',
            name='replication',
            get=lambda obj: self.get_task_args(obj, 'replication'),
            set=lambda obj, val: self.set_task_args(obj, val, 'replication'),
            list=True,
            complete=EntitySubscriberComplete('replication=', 'replication', lambda o: o['name']),
            usage=_('Name of the replication object to be used in the replication calendar task.')
        )


class CheckUpdateNamespace(CalendarTasksNamespaceBaseClass):
    """
    CheckUpdate namespaces provides commands to create 'check_update' type calendar tasks

    Usage: create <name> <property>=<value>

    Examples: create myupdate schedule={"hour":1}
    Examples: create myupdate schedule={"day":"1,4","hour":1}
    """
    def __init__(self, name, context):
        super(CheckUpdateNamespace, self).__init__(name, context)
        self.extra_query_params = [('task', '=', 'update.checkfetch')]
        self.skeleton_entity['task'] = 'update.checkfetch'
        self.skeleton_entity['args'] = []
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> <property>=<value>

            Examples: create myupdate schedule={"hour":1}
            Examples: create myupdate schedule={"day":"1,4","hour":1}

            Creates a update calendar task. For a list of properties, see 'help properties'.""")


class CommandNamespace(CalendarTasksNamespaceBaseClass):
    """
    Command namespaces provides commands to create 'command' type calendar tasks

    Usage: create <name> username=<username> command=<command> <property>=<value>

    Examples: create mycommand username=myuser command="ls -l" schedule={"minute":"`*/5`"}
              create mycommand username=myuser command="ls -l" schedule={"minute":"`*/5`","second":"10,30,50"}
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
                      create mycommand username=myuser command="ls -l" schedule={"minute":"*/5","second":"10,30,50"}

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


class BackupNamespace(CalendarTasksNamespaceBaseClass):
    """
    Backup namespace provides commands to create a periodic job executing 'sync' command
    of a previously defined 'backup' task.
    The 'backup' task must first be created in the '/backup' namespace.

    Usage:
        create <name> backup=<volume> <property>=<value>

    Examples:
        create my_periodic_backup backup=<backup_entity_name> schedule={"hour":2,"day_of_week":5}
        create my_periodic_backup backup=<backup_entity_name> schedule={"hour":2,"day_of_week":"1,5"}
    """
    def __init__(self, name, context):
        super(BackupNamespace, self).__init__(name, context)
        self.extra_query_params = [('task', '=', 'backup.sync')]
        self.required_props.extend(['backup'])
        self.skeleton_entity['task'] = 'backup.sync'
        self.task_args_helper = ['backup']
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> backup=<backup_name> <property>=<value>

            Examples: create sshbackup_job backup=mysshbackup
                      create s3backup_job backup=mys3backup schedule={"hour":2,"day_of_week":5}
                      create s3backup_job backup=mys3backup schedule={"hour":2,"day_of_week":"1,5"}

            Creates a backup calendar task. For a list of properties, see 'help properties'.""")

        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set name=otherbackup
                      set enabled=true

            Sets a backup calendar task property. For a list of properties, see 'help properties'.""")

        self.entity_localdoc['GetEntityCommand'] = ("""\
            Usage: get <field>

            Examples:
                get backup
                get name

            Display value of specified field.""")

        self.add_property(
            descr='Backup',
            name='backup',
            get=lambda obj: objid2name(self.context, 'backup', self.get_task_args(obj, 'backup')),
            list=True,
            set=lambda obj, val: self.set_task_args(
                obj, objname2id(self.context, 'backup', val), 'backup'
            ),
            complete=EntitySubscriberComplete('backup=', 'backup', lambda i: i['name'])
        )


TASK_TYPES = {
    'scrub': 'volume.scrub',
    'smart': 'disk.parallel_test',
    'rsync': 'rsync.copy',
    'snapshot': 'volume.snapshot_dataset',
    'replication': 'replication.sync',
    'check_update': 'update.checkfetch',
    'command': 'calendar_task.command',
    'backup': 'backup.sync'
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
        tid = context.submit_task('calendar_task.run', self.parent.entity['id'])
        return TaskPromise(context, tid)


def _init(context):
    context.attach_namespace('/', CalendarTasksNamespace('calendar', context))
