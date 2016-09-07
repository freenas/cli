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
    RpcBasedLoadMixin, EntityNamespace
)
from freenas.cli.output import Object, Sequence, ValueType, format_value
from freenas.cli.descriptions import events
from freenas.cli.utils import post_save, parse_timedelta
import gettext

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("System info and configuration")
class DashboardNamespace(EntityNamespace):
    """
    The dashboard namespace provides overview of the system activity.
    """
    def __init__(self, name, context):
        super(DashboardNamespace, self).__init__(name, context)
        self.context = context
        self.allow_create = False

        self.extra_commands = {
            'status': StatusCommand(),
            'version': VersionCommand(),
            'info': InfoCommand()
        }

    def commands(self):
        cmds = super(DashboardNamespace, self).commands()
        del cmds['show']
        return cmds

    def namespaces(self):
        return [
            EventsNamespace('event', self.context)
        ]

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
            Object.Item("Connected clients", 'connected-clients', status_dict['connected-clients']),
            Object.Item("Uptime", 'up-since', status_dict['up-since']),
            Object.Item("Started at", 'started-at', status_dict['started-at'])
        )


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
                    if nested_namespace.name == 'directories':
                        output_dict[nested_namespace.name] = get_show(nested_namespace)
                    if nested_namespace.name == 'kerberos':
                        for kerberos_namespace in nested_namespace.namespaces():
                            if kerberos_namespace.name == 'keytab' or \
                               kerberos_namespace.name == 'realm':
                                output_dict[kerberos_namespace.name] = get_show(kerberos_namespace)

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
        output_dict['hardware'] = Object(
            Object.Item("CPU Clockrate", 'cpu_clockrate', hw_info_dict['cpu_clockrate']),
            Object.Item("CPU Model", 'cpu_model', hw_info_dict['cpu_model']),
            Object.Item("CPU Cores", 'cpu_cores', hw_info_dict['cpu_cores']),
            Object.Item("Memory size", 'memory_size', hw_info_dict['memory_size'], vt=ValueType.SIZE)
        )

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
        if len(output_dict['directories']) > 0:
            output.append("\n\nStatus of Active Directory:")
            append_out('directories')
        if len(output_dict['keytab']) > 0 or len(output_dict['realm']) > 0:
            output.append("\n\nStatus of Kerberos:")
            append_out('keytab')
            append_out('realm')

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
            get='created_at',
        )

        self.add_property(
            descr='Updated at',
            name='updated',
            get='updated_at',
        )

        self.primary_key = self.get_mapping('id')

    def serialize(self):
        raise NotImplementedError()

def _init(context):
    context.attach_namespace('/', DashboardNamespace('dashboard', context))
