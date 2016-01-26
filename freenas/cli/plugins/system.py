#+
# Copyright 2014 iXsystems, Inc.
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

from freenas.cli.namespace import (
    Namespace, ConfigNamespace, Command, CommandException, description,
    RpcBasedLoadMixin, EntityNamespace, IndexCommand
)
from freenas.cli.output import Table, Object, Sequence, ValueType, format_value
from freenas.cli.descriptions import events
from freenas.cli.utils import post_save
import gettext

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Shuts the system down")
class ShutdownCommand(Command):
    """
    Usage: shutdown

    Shuts the system down.
    """
    def run(self, context, args, kwargs, opargs):
        context.submit_task('system.shutdown')
        return _("System going for a shutdown...")


@description("Reboots the system")
class RebootCommand(Command):
    """
    Usage: reboot

    Reboots the system.
    """
    def run(self, context, args, kwargs, opargs):
        context.submit_task('system.reboot')
        return _("System going for a reboot...")


@description("Provides status information about the server")
class StatusCommand(Command):
    """
    Usage: status

    Displays status information about the server.
    """
    def run(self, context, args, kwargs, opargs):
        status_dict = context.call_sync('management.status')
        status_dict['up-since'] = format_value(status_dict['started-at'], vt=ValueType.TIME)
        return Object(
                Object.Item(
                    "Connected clients", 'connected-clients',
                    status_dict['connected-clients']
                ),
                Object.Item("Uptime", 'up-since', status_dict['up-since']),
                Object.Item("Started at", 'started-at', status_dict['started-at'])
        )


@description("Gets a list of valid timezones")
class TimezonesCommand(Command):
    """
    Usage: timezones

    Displays a list of valid timezones for the timezone setting.
    """

    def run(self, context, args, kwargs, opargs):
        return Sequence(*context.call_sync('system.general.timezones'))


@description("Provides information about running system")
class InfoCommand(Command):
    """
    Usage: info

    Displays information about the system.
    """
    def run(self, context, args, kwargs, opargs):
        root_namespaces = context.root_ns.namespaces()
        output_dict = {}
        output = Sequence()

        def get_show(obj):
            if isinstance(obj, ConfigNamespace):
                obj.load()
            commands = obj.commands()
            if 'show' in commands:
                instance = commands['show']
                return instance.run(context, '', '', '')
            else:
                raise CommandException(_("Namespace {0} does not have 'show' command".format(obj.name)))

        def append_out(key):
            if len(output_dict[key]) > 0:
                output.append("\nData about {0}:".format(key))
                output.append(output_dict[key])

        for namespace in root_namespaces:
            if namespace.name == 'system' or \
               namespace.name == 'service' or \
               namespace.name == 'vm' or \
               namespace.name == 'disk' or \
               namespace.name == 'share' or \
               namespace.name == 'volume':
                    output_dict[namespace.name] = get_show(namespace)

            elif namespace.name == 'directoryservice':
                for nested_namespace in namespace.namespaces():
                    if nested_namespace.name == 'activedirectory' or \
                       nested_namespace.name == 'ldap':
                            output_dict[nested_namespace.name] = get_show(nested_namespace)
            elif namespace.name == 'network':
                for nested_namespace in namespace.namespaces():
                    if nested_namespace.name == 'config' or \
                       nested_namespace.name == 'host' or \
                       nested_namespace.name == 'interface' or \
                       nested_namespace.name == 'route':
                            output_dict[nested_namespace.name] = get_show(nested_namespace)
            elif namespace.name == 'boot':
                for nested_namespace in namespace.namespaces():
                    if nested_namespace.name == 'environment':
                            output_dict[nested_namespace.name] = get_show(nested_namespace)

        hw_info_dict = context.call_sync('system.info.hardware')
        output_dict['hardware'] = Object(Object.Item("CPU Clockrate", 'cpu_clockrate', hw_info_dict['cpu_clockrate']),
                                         Object.Item("CPU Model", 'cpu_model', hw_info_dict['cpu_model']),
                                         Object.Item("CPU Cores", 'cpu_cores', hw_info_dict['cpu_cores']),
                                         Object.Item("Memory size", 'memory_size', hw_info_dict['memory_size'],
                                                     vt=ValueType.SIZE))

        ver_info = context.call_sync('system.info.version')

        output.append("System version: {0}".format(ver_info))
        output.append("\n\nStatus of machine:")
        append_out('system')
        append_out('hardware')
        output.append("\n\nStatus of boot environment:")
        append_out('environment')
        output.append("\n\nStatus of networking:")
        append_out('config')
        append_out('host')
        append_out('interface')
        append_out('route')
        output.append("\n\nStatus of storage:")
        append_out('volume')
        append_out('disk')
        append_out('share')
        if len(output_dict['vm']) > 0:
            output.append("\n\nStatus of VMs:")
            append_out('vm')
        output.append("\n\nStatus of services:")
        append_out('service')
        if len(output_dict['activedirectory']) > 0 or len(output_dict['ldap']) > 0:
            output.append("\n\nStatus of directory services:")
            append_out('activedirectory')
            append_out('ldap')

        return output


@description("Prints FreeNAS version information")
class VersionCommand(Command):
    """
    Usage: version

    Displays FreeNAS version information.
    """
    def run(self, context, args, kwargs, opargs):
        return Object(
            Object.Item(
                'FreeNAS version', 'freenas_version', context.call_sync('system.info.version')
                ),
            Object.Item(
                'System version',
                'system_version',
                ' '.join(context.call_sync('system.info.uname_full'))
                )
        )


@description("Restores FreeNAS factory config")
class FactoryRestoreCommand(Command):
    """
    Usage: factory_restore
    """
    def run(self, context, args, kwargs, opargs):
        context.call_task_sync('database.restore_factory')


class ShowReplicationKeyCommand(Command):
    """
    Usage: show_key
    """
    def run(self, context, args, kwargs, opargs):
        return context.call_sync('replication.get_public_key')


@description("View sessions")
class SessionsNamespace(RpcBasedLoadMixin, EntityNamespace):
    """
    System sessions command, expands into commmands to show sessions.
    """
    def __init__(self, name, context):
        super(SessionsNamespace, self).__init__(name, context)

        self.allow_create = False
        self.allow_edit = False
        self.query_call = 'session.query'

        self.add_property(
            descr='Session ID',
            name='id',
            get='id',
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='IP Address',
            name='address',
            get='address',
        )

        self.add_property(
            descr='User name',
            name='username',
            get='username',
        )

        self.add_property(
            descr='Started at',
            name='started',
            get='started-at',
            type=ValueType.TIME
        )

        self.add_property(
            descr='Ended at',
            name='ended',
            get='ended-at',
            type=ValueType.TIME
        )

        self.primary_key = self.get_mapping('id')

    def serialize(self):
        raise NotImplementedError()


@description("View event history")
class EventsNamespace(RpcBasedLoadMixin, EntityNamespace):
    """
    System events command, expands into commands to show events.
    """
    def __init__(self, name, context):
        super(EventsNamespace, self).__init__(name, context)
        self.allow_create = False
        self.allow_edit = False
        self.query_call = 'event.query'

        self.add_property(
            descr='Event ID',
            name='id',
            get='id',
        )

        self.add_property(
            descr='Event Name',
            name='name',
            get=lambda t: events.translate(context, t['name'], t['args']),
        )

        self.add_property(
            descr='Timestamp',
            name='timestamp',
            get='timestamp',
            type=ValueType.TIME
        )

        self.add_property(
            descr='Created at',
            name='created',
            get='created-at',
        )

        self.add_property(
            descr='Updated at',
            name='updated',
            get='updated-at',
        )

        self.primary_key = self.get_mapping('id')

    def serialize(self):
        raise NotImplementedError()


@description("Time namespace")
class TimeNamespace(ConfigNamespace):
    """
    System time command, expands into commands for setting and getting time.
    """
    def __init__(self, name, context):
        super(TimeNamespace, self).__init__(name, context)
        self.config_call = 'system.info.time'

        self.add_property(
            descr='System time',
            name='system_time',
            get='system_time',
            list=True
        )

        self.add_property(
            descr='Bootup time',
            name='boot_time',
            get='boot_time',
            set=None,
            list=True
        )

        self.add_property(
            descr='Time zone',
            name='timezone',
            get='timezone',
            list=True
        )

    def save(self):
        self.context.submit_task(
            'system.time.configure',
            self.get_diff(),
            callback=lambda s: post_save(self, s)
        )


@description("Mail configuration")
class MailNamespace(ConfigNamespace):
    """
    System mail command, expands into commands for configuring email settings.
    """
    def __init__(self, name, context):
        super(MailNamespace, self).__init__(name, context)
        self.context = context
        self.config_call = 'mail.get_config'

        self.add_property(
            descr='Email address',
            name='email',
            get='from',
            set='from',
        )

        self.add_property(
            descr='Email server',
            name='server',
            get='server',
        )

        self.add_property(
            descr='SMTP port',
            name='port',
            get='port',
            type=ValueType.NUMBER,
        )

        self.add_property(
            descr='Authentication required',
            name='auth',
            get='auth',
            type=ValueType.BOOLEAN,
        )

        self.add_property(
            descr='Encryption type',
            name='encryption',
            get='encryption',
            enum=['PLAIN', 'TLS', 'SSL']
        )

        self.add_property(
            descr='Username for Authentication',
            name='username',
            get='user',
            set='user',
        )

        self.add_property(
            descr='Password for Authentication',
            name='password',
            get=None,
            set='pass',
        )

    def save(self):
        self.context.submit_task(
            'mail.configure',
            self.get_diff(),
            callback=lambda s: post_save(self, s)
        )


@description("Advanced system configuration")
class AdvancedNamespace(ConfigNamespace):
    """
    Advanced system configuration command, expands into commands for settings
    for advanced users.
    """
    def __init__(self, name, context):
        super(AdvancedNamespace, self).__init__(name, context)
        self.context = context
        self.config_call = 'system.advanced.get_config'

        self.add_property(
            descr='Enable Console CLI',
            name='console_cli',
            get='console_cli',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Enable Console Screensaver',
            name='console_screensaver',
            get='console_screensaver',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Enable Serial Console',
            name='serial_console',
            get='serial_console',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Serial Console Port',
            name='serial_port',
            get='serial_port',
        )

        self.add_property(
            descr='Serial Port Speed',
            name='serial_speed',
            get='serial_speed',
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Enable powerd',
            name='powerd',
            get='powerd',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Default swap on drives',
            name='swapondrive',
            get='swapondrive',
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Enable Debug Kernel',
            name='debugkernel',
            get='debugkernel',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Automatically upload crash dumps to iXsystems',
            name='uploadcrash',
            get='uploadcrash',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Message of the day',
            name='motd',
            get='motd',
        )

        self.add_property(
            descr='Periodic Notify User UID',
            name='periodic_notify_user',
            get='periodic_notify_user',
            type=ValueType.NUMBER
        )

    def save(self):
        self.context.submit_task(
            'system.advanced.configure',
            self.get_diff(),
            callback=lambda s: post_save(self, s)
        )


@description("Configuration database operations")
class ConfigDbNamespace(Namespace):
    def commands(self):
        return {
            'factory_restore': FactoryRestoreCommand(),
            '?': IndexCommand(self)
        }


class SystemDatasetNamespace(ConfigNamespace):
    def __init__(self, name, context):
        super(SystemDatasetNamespace, self).__init__(name, context)
        self.config_call = 'system_dataset.status'

        self.add_property(
            descr='Identifier',
            name='id',
            get='id',
            set=None
        )

        self.add_property(
            descr='Volume',
            name='volume',
            get='pool'
        )

    def save(self):
        self.context.submit_task(
            'system_dataset.configure',
            self.entity['pool'],
            callback=lambda s: post_save(self, s)
        )


class ReplicationNamespace(Namespace):
    def commands(self):
        return {
            'show_key': ShowReplicationKeyCommand(),
            '?': IndexCommand(self)
        }


@description("System info and configuration")
class SystemNamespace(ConfigNamespace):
    """
    System top level command, expands into commands for configuring system
    settings and getting system information.
    """
    def __init__(self, name, context):
        super(SystemNamespace, self).__init__(name, context)
        self.context = context
        self.config_call = 'system.general.get_config'

        self.add_property(
            descr='Time zone',
            name='timezone',
            get='timezone',
        )

        self.add_property(
            descr='Hostname',
            name='hostname',
            get='hostname'
        )

        self.add_property(
            descr='Syslog Server',
            name='syslog_server',
            get='syslog_server'
        )

        self.add_property(
            descr='Language',
            name='language',
            get='language'
        )

        self.add_property(
            descr='Console Keymap',
            name='console_keymap',
            get='console_keymap'
        )

        self.extra_commands = {
            'status': StatusCommand(),
            'version': VersionCommand(),
            'timezones': TimezonesCommand(),
            'info': InfoCommand(),
            'reboot': RebootCommand(),
            'shutdown': ShutdownCommand()
        }

    def save(self):
        return self.context.submit_task(
            'system.general.configure',
            self.entity,
            callback=lambda s: post_save(self, s)
        )

    def namespaces(self):
        return [
            AdvancedNamespace('advanced', self.context),
            TimeNamespace('time', self.context),
            MailNamespace('mail', self.context),
            SessionsNamespace('session', self.context),
            EventsNamespace('event', self.context),
            SystemDatasetNamespace('system_dataset', self.context),
            ConfigDbNamespace('config'),
            ReplicationNamespace('replication')
        ]


def _init(context):
    context.attach_namespace('/', SystemNamespace('system', context))
