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


import copy
from namespace import (
    Namespace, ConfigNamespace, Command, IndexCommand, description,
    CommandException, RpcBasedLoadMixin, EntityNamespace
)
from output import Table, Object, ValueType, output_dict, output_table
from descriptions import events
from utils import parse_query_args, post_save


@description("Provides status information about the server")
class StatusCommand(Command):
    """
    Usage: status

    Displays status information about the server.
    """
    def run(self, context, args, kwargs, opargs):
        output_dict(context.call_sync('management.status'))


@description("Provides information about running system")
class InfoCommand(Command):
    """
    Usage: info

    Displays information about the system's hardware.
    """
    def run(self, context, args, kwargs, opargs):
        output_dict(context.call_sync('system.info.hardware'))


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


@description("View sessions")
class SessionsNamespace(RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(SessionsNamespace, self).__init__(name, context)

        self.allow_create = False
        self.allow_edit = False
        self.query_call = 'sessions.query'

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


@description("Prints event history")
class EventsCommand(Command):
    """
    Usage: events [<field> <operator> <value> ...] [limit=<n>] [sort=<field>,-<field2>]
    """
    def run(self, context, args, kwargs, opargs):
        items = context.call_sync('event.query', *parse_query_args(args, kwargs))
        return Table(items, [
            Table.Column('Event name', lambda t: events.translate(context, t['name'], t['args'])),
            Table.Column('Time', 'timestamp', ValueType.TIME)
        ])


@description("View event history")
class EventsNamespace(RpcBasedLoadMixin, EntityNamespace):
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


@description("Time namespace")
class TimeNamespace(ConfigNamespace):
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


@description("System info and configuration")
class SystemNamespace(ConfigNamespace):
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
            'info': InfoCommand(),
            'events': EventsCommand(),
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
        ]


def _init(context):
    context.attach_namespace('/', SystemNamespace('system', context))
