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
from namespace import Namespace, ConfigNamespace, Command, IndexCommand, description
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


@description("Logs in to the server")
class LoginCommand(Command):
    """
    Usage: login <username> <password>
    """
    def run(self, context, args, kwargs, opargs):
        context.connection.login_user(args[0], args[1])
        context.connection.subscribe_events('*')
        context.login_plugins()


@description("Prints session history")
class SessionsCommand(Command):
    """
    Usage: sessions [<field> <operator> <value> ...] [limit=<n>] [sort=<field>,-<field2>]
    """
    def run(self, context, args, kwargs, opargs):
        items = context.call_sync('sessions.query', *parse_query_args(args, kwargs))
        return Table(items, [
            Table.Column('Session ID', 'id', ValueType.NUMBER),
            Table.Column('IP address', 'address', ValueType.STRING),
            Table.Column('User name', 'username', ValueType.STRING),
            Table.Column('Started at', 'started-at', ValueType.TIME),
            Table.Column('Ended at', 'ended-at', ValueType.TIME)
        ])


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
        self.context.submit_task('system.time.configure', self.get_diff(), callback=lambda s: post_save(self, s))


@description("General configuration")
class GeneralNamespace(ConfigNamespace):
    def __init__(self, name, context):
        super(GeneralNamespace, self).__init__(name, context)
        self.config_call='system.general.get_config'

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

    def save(self):
        return self.context.submit_task('system.general.configure', self.entity, callback=lambda s: post_save(self, s))


@description("System info and configuration")
class SystemNamespace(Namespace):
    def __init__(self, name, context):
        super(SystemNamespace, self).__init__(name)
        self.context = context

    def commands(self):
        return {
            '?': IndexCommand(self),
            'login': LoginCommand(),
            'status': StatusCommand(),
            'version': VersionCommand(),
            'info': InfoCommand(),
            'events': EventsCommand(),
            'sessions': SessionsCommand()
        }

    def namespaces(self):
        return [
            GeneralNamespace('config', self.context),
            TimeNamespace('time', self.context)
        ]


def _init(context):
    context.attach_namespace('/', SystemNamespace('system', context))
