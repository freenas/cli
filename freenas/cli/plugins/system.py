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

import gettext
from pathlib import Path
from freenas.cli.namespace import (
    Namespace, ConfigNamespace, Command, CommandException, description,
    RpcBasedLoadMixin, EntityNamespace, TaskBasedSaveMixin
)
from freenas.cli.output import Object, Table, Sequence, ValueType, format_value, output_msg
from freenas.cli.descriptions import events
from freenas.cli.utils import TaskPromise, post_save, parse_timedelta, set_related, get_related
from freenas.cli.complete import NullComplete, EntitySubscriberComplete, RpcComplete
from freenas.dispatcher.fd import FileDescriptor

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
        return _("The system will now shutdown...")


@description("Reboots the system")
class RebootCommand(Command):
    """
    Usage: reboot delay=<delay>

    Examples: reboot
              reboot delay=1:10.10 (1hour 10 minutes 10 seconds)
              reboot delay=0:10 (10 minutes)
              reboot delay=0:0.10 (10 seconds)

    Reboots the system.
    """

    def run(self, context, args, kwargs, opargs):
        delay = kwargs.get('delay', None)
        if delay:
            delay = parse_timedelta(delay).seconds
        context.submit_task('system.reboot', delay)
        return _("The system will now reboot...")


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
            Object.Item("Number of middleware connections", 'middleware-connections', status_dict['connected-clients']),
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
            Object.Item("Memory size", 'memory_size', hw_info_dict['memory_size'], vt=ValueType.SIZE),
            Object.Item("VM Guest", 'vm_guest', hw_info_dict['vm_guest'])
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


@description("Prints FreeNAS packages version information")
class PackagesCommand(Command):
    """
    Usage: packages

    Displays version information of packages installed in the system.
    """

    def run(self, context, args, kwargs, opargs):
        return Table(context.call_sync('software.package.query'), [
            Table.Column('Package name', 'name'),
            Table.Column('Version', 'version')
        ])


@description("Gets a list of valid timezones")
class TimezonesCommand(Command):
    """
    Usage: timezones

    Displays a list of valid timezones for the timezone setting.
    """

    def run(self, context, args, kwargs, opargs):
        return Sequence(*context.call_sync('system.general.timezones'))


@description("Restores FreeNAS factory config")
class FactoryRestoreCommand(Command):
    """
    Usage: factory_restore

    Resets the configuration database to the default FreeNAS base, deleting
    all configuration changes. Running this command will reboot the system.
    """

    def run(self, context, args, kwargs, opargs):
        context.call_task_sync('database.factory_restore')


@description("Stores FreeNAS config to a file")
class DownloadConfigCommand(Command):
    """
    Usage: download path=/abs/path/to/target/file

    Examples: / system config download path=/mnt/mypool/mydir/myconfig.db

    Stores FreeNAS configuration database to the selected file.
    """

    def run(self, context, args, kwargs, opargs):
        if not kwargs:
            raise CommandException(_("Download requires more arguments. For help see 'help download'"))
        if 'path' not in kwargs:
            raise CommandException(_("Please specify path to the target config file."
                                     "For help see 'help download'"))

        p = Path(kwargs['path'])
        with p.open('w') as fo:
            context.call_task_sync('database.dump', FileDescriptor(fd=fo.fileno(), close=False))

    def complete(self, context, **kwargs):
        return [
            NullComplete('path='),
        ]


@description("Restores FreeNAS config from a file")
class UploadConfigCommand(Command):
    """
    Usage: upload path=/abs/path/to/source/file

    Examples: / system config upload path=/mnt/mypool/mydir/myconfig.db

    Restores FreeNAS configuration database from the selected file.
    """

    def run(self, context, args, kwargs, opargs):
        if not kwargs:
            raise CommandException(_("Upload requires more arguments. For help see 'help upload'"))
        if 'path' not in kwargs:
            raise CommandException(_("Please specify path to the source config file."
                                     "For help see 'help upload'"))

        p = Path(kwargs['path'])
        with p.open('r') as fo:
            output_msg(_('Restoring the Database. Reboot will occur immediately after the restore operation.'))
            context.call_task_sync('database.restore', FileDescriptor(fd=fo.fileno(), close=False))

    def complete(self, context, **kwargs):
        return [
            NullComplete('path='),
        ]


@description("Downloads freenas debug file to the path specified")
class DownloadDebugCommand(Command):
    """
    Usage: download path=/abs/path/to/target/file

    Examples: / system debug download path=/mnt/mypool/mydir/freenasdebug.tar.gz

    Downloads freenas debug file to the path specified.
    """

    def run(self, context, args, kwargs, opargs):
        if not kwargs:
            raise CommandException(_("Download requires more arguments. For help see 'help download'"))
        if 'path' not in kwargs:
            raise CommandException(_("Please specify path to the target debug file."
                                     "For help see 'help download'"))

        p = Path(kwargs['path'])
        with p.open('w') as fo:
            context.call_task_sync('debug.collect', FileDescriptor(fd=fo.fileno(), close=False))

    def complete(self, context, **kwargs):
        return [
            NullComplete('path='),
        ]


class SystemDatasetImportCommand(Command):
    """
    Usage: import volume=<volume>
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        vol = kwargs.get('volume', None)
        if not vol:
            raise CommandException(_('Please specify a volume name'))

        tid = context.submit_task('system_dataset.import', vol, callback=lambda s, t: post_save(self.parent, s, t))
        return TaskPromise(context, tid)


@description(_("Manage NTP servers"))
class NTPServersNamespace(RpcBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    """ The NTP server namespace provides commands for managing NTP servers """
    def __init__(self, name, context):
        super(NTPServersNamespace, self).__init__(name, context)

        self.context = context
        self.query_call = 'ntp_server.query'
        self.create_task = 'ntp_server.create'
        self.update_task = 'ntp_server.update'
        self.delete_task = 'ntp_server.delete'
        self.primary_key_name = 'address'
        self.required_props = ['address']
        self.localdoc['CreateEntityCommand'] = _("""\
            Usage: create <address> <property>=<value> ...

            Examples: create utcnist.colorado.edu
                      create "3.freebsd.pool.ntp.org" pool=true

            Adds an NTP server for syncing with. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = _("""\
            Usage: set <property>=<value> ...

            Examples: set address=utcnist2.colorado.edu
                      set burst=True
                      set preferred=yes
                      set minpoll=6
                      set maxpoll=15

            Sets a user property. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['DeleteEntityCommand'] = _("""\
            Usage: delete

            Examples: delete

            Deletes the specified NTP server.""")
        self.entity_localdoc['EditEntityCommand'] = ("""\
            Usage: edit <field>

            Examples: edit address

            Opens the default editor for the specified property. The default editor
            is inherited from the shell's $EDITOR which can be set from the shell.
            For a list of properties for the current namespace, see 'help properties'.""")
        self.entity_localdoc['ShowEntityCommand'] = ("""\
            Usage: show

            Examples: show

            Display the property values for the current NTP server.""")
        self.entity_localdoc['GetEntityCommand'] = ("""\
            Usage: get <field>

            Examples:
                get address

            Display value of specified field.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all NTP servers. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search address ~= utcnist """)

        self.add_property(
            descr='Address',
            name='address',
            get='address',
            set='address',
            list=True,
            usage=_("Must be a valid hostname for an NTP server"),
            type=ValueType.STRING
        )

        self.add_property(
            descr='Burst',
            name='burst',
            get='burst',
            set='burst',
            list=True,
            usage=_("""\
                    Can be set to true or false, if true this option will send 8 packets
                    instead of 1 on each poll interval to the server while the server is
                    reachable for improved timekeeping."""),
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Initial Burst',
            name='iburst',
            get='iburst',
            set='iburst',
            list=True,
            usage=_("""\
                    Can be set to true or false, if true this option will send 8 packets
                    instead of 1 on each poll interval to the server while the server is
                    not reachable for improved synchronization."""),
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Preferred',
            name='prefer',
            get='prefer',
            set='prefer',
            list=True,
            usage=_("""\
                    Can be set to yes or no, if true then this will be the preferred server."""),
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Min Poll',
            name='minpoll',
            get='minpoll',
            set='minpoll',
            list=True,
            usage=_("""\
                    An integer value that ranges between 4 and 1 minus the max poll value."""),
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Max Poll',
            name='maxpoll',
            get='maxpoll',
            set='maxpoll',
            usage=_("""\
                    An integer value that ranges between 17 and 1 plus the min poll value."""),
            list=True,
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Pool',
            name='pool',
            get='pool',
            set='pool',
            usage=_("""Can be yes or no, determines whether or not the server is a member of an NTP pool."""),
            list=True,
            type=ValueType.BOOLEAN
        )

        self.primary_key = self.get_mapping('address')

        self.entity_commands = lambda this: {
            'sync_now': SyncNowCommand(this)
        }

@description("Synchronizes with an NTP server")
class SyncNowCommand(Command):
    """
    Usage: sync_now

    Synchronizes the time with the specified NTP server
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        tid = context.submit_task('ntp_server.sync_now', self.parent.entity['address'])
        return TaskPromise(context, tid)


@description("Time namespace")
class TimeNamespace(ConfigNamespace):
    """
    System time command, expands into commands for setting and getting time.
    """

    def __init__(self, name, context):
        super(TimeNamespace, self).__init__(name, context)
        self.config_call = 'system.time.get_config'
        self.update_task = 'system.time.update'

        self.add_property(
            descr='System time',
            name='system_time',
            get='system_time',
            list=True,
            type=ValueType.DATE
        )

        self.add_property(
            descr='Bootup time',
            name='boot_time',
            get='boot_time',
            set=None,
            list=True,
            type=ValueType.TIME
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
        self.update_task = 'mail.update'

        self.add_property(
            descr='Email address',
            name='email',
            usage=_("""\
            Use set or edit to set the from email address to be
            used when sending email notifications. When using set,
            enclose the email address between double quotes."""),
            get='from',
            set='from',
        )

        self.add_property(
            descr='Email server',
            name='server',
            usage=_("""\
            Use set or edit to set the hostname or IP address of
            the SMTP server. When using set, enclose the value
            between double quotes."""),
            get='server',
        )

        self.add_property(
            descr='SMTP port',
            name='port',
            usage=_("""\
            Use set or edit to set the number of the SMTP port.
            Typically set to 25, 465 (secure SMTP), or 587
            (submission)."""),
            get='port',
            type=ValueType.NUMBER,
        )

        self.add_property(
            descr='Authentication required',
            name='auth',
            usage=_("""\
            Can be set to yes or no. When set to yes,
            enables SMTP AUTH using PLAIN SASL and requires both
            'username' and 'password' to be set."""),
            get='auth',
            type=ValueType.BOOLEAN,
        )

        self.add_property(
            descr='Encryption type',
            name='encryption',
            usage=_("""\
            Use set or edit to set to PLAIN (no encryption),
            TLS, or SSL.."""),
            get='encryption',
            enum=['PLAIN', 'TLS', 'SSL']
        )

        self.add_property(
            descr='Username for Authentication',
            name='username',
            usage=_("""\
            Use set or edit to set the username used by
            SMTP authentication. Requires 'auth' to be set
            to yes."""),
            get='user',
            set='user',
        )

        self.add_property(
            descr='Password for Authentication',
            name='password',
            usage=_("""\
            Use set to set the password used by
            SMTP authentication. Requires 'auth' to be set
            to yes. For security reasons, the password is
            not displayed by get or edit."""),
            get=None,
            set='pass',
        )


@description("System GUI settings and information")
class SystemUINamespace(ConfigNamespace):
    """
    The System UI Namespace provides users with
    GUI port certificate settings to view and/or edit
    """

    def __init__(self, name, context):
        super(SystemUINamespace, self).__init__(name, context)
        self.context = context
        self.config_call = 'system.ui.get_config'
        self.update_task = 'system.ui.update'

        self.add_property(
            descr='Redirect http to https',
            name='redirect_https',
            get='webui_http_redirect_https',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Web GUI Protocols in use',
            name='protocols',
            get='webui_protocol',
            type=ValueType.SET,
            enum=['HTTP', 'HTTPS']
        )

        self.add_property(
            descr='Web GUI IP Address (IPv4 and/or IPv6)',
            name='ip_addresses',
            get='webui_listen',
            type=ValueType.SET
        )

        self.add_property(
            descr='HTTP port',
            name='http_port',
            get='webui_http_port',
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='HTTPS port',
            name='https_port',
            get='webui_https_port',
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='HTTPS certificate',
            name='https_certificate',
            get=lambda o: get_related(self.context, 'crypto.certificate', o, 'webui_https_certificate'),
            set=lambda o, v: set_related(self.context, 'crypto.certificate', o, 'webui_https_certificate', v),
            usage=_("""\
            Name of the certificate
            """),
            complete=EntitySubscriberComplete(
                'https_certificate=',
                'crypto.certificate',
                lambda o: o['name'] if o['type'] != 'CERT_CSR' else None
            ),
            type=ValueType.STRING
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
        self.update_task = 'system.advanced.update'

        def set_periodic_notify_user(obj, v):
            if v in range(1, 1000):
                raise ValueError(_('Invalid value, please specify value outside of range (1..999)'))
            else:
                obj['periodic_notify_user'] = v

        self.add_property(
            descr='Enable Console CLI',
            name='console_cli',
            usage=_("""\
            Can be set to yes or no. When set to yes,
            the system will boot into a login prompt instead
            of the CLI. You can still start the CLI by
            typing cli after a successful login."""),
            get='console_cli',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Enable Console Screensaver',
            name='console_screensaver',
            usage=_("""\
            Can be set to yes or no. When set to yes,
            a screensaver will start after a period of
            CLI inactivity."""),
            get='console_screensaver',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Enable Serial Console',
            name='serial_console',
            usage=_("""\
            Can be set to yes or no. Only set to yes,
            if the system has an active serial port and
            you want to access the system using that serial
            port."""),
            get='serial_console',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Serial Console Port',
            name='serial_port',
            usage=_("""\
            Use set or edit to specify the serial port
            to use for console access."""),
            get='serial_port',
            set='serial_port',
            complete=RpcComplete(
                'serial_port=',
                'system.device.get_devices',
                lambda o: o['name'],
                call_args=('serial_port',)
            )
        )

        self.add_property(
            descr='Serial Port Speed',
            name='serial_speed',
            usage=_("""\
            Use set to specify the speed of the serial port
            used for console access."""),
            get='serial_speed',
            set='serial_speed',
            enum=['110', '300', '600', '1200', '2400', '4800',
                  '9600', '14400', '19200', '38400', '57600', '115200'],
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Enable powerd',
            name='powerd',
            usage=_("""\
            Can be set to yes or no. When set to yes,
            enables powerd(8) which monitors the system state and
            sets the CPU frequency accordingly."""),
            get='powerd',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Default swap on drives',
            name='swapondrive',
            usage=_("""\
            Non-zero number representing the default swap size, for each
            formatted disk, in GiB."""),
            get='swapondrive',
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Enable Debug Kernel',
            name='debugkernel',
            usage=_("""\
            Can be set to yes or no. When set to yes, the
            next boot will boot into a debug version of the kernel which
            can be useful when troubleshooting."""),
            get='debugkernel',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Automatically upload crash dumps to iXsystems',
            name='uploadcrash',
            usage=_("""\
            Can be set to yes or no. When set to yes, kernel
            crash dumps and telemetry (some system statatistics and syslog
            messages) are automatically sent to the FreeNAS development
            team for diagnosis."""),
            get='uploadcrash',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Message of the day',
            name='motd',
            usage=_("""\
            Use set or edit to modify the message to be seen when a user
            logs in over SSH. When using set, enclose the message between
            double quotes"""),
            get='motd',
        )

        self.add_property(
            descr='Periodic Notify User UID',
            name='periodic_notify_user',
            usage=_("""\
            Set to the number representing the UID of the user to
            receive security output emails. This output runs nightly,
            but only sends an email when the system reboots or
            encounters an error."""),
            get='periodic_notify_user',
            set=set_periodic_notify_user,
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Remote Graphite servers',
            name='graphite_servers',
            get='graphite_servers',
            type=ValueType.SET
        )

        self.add_property(
            descr='FreeNAS peer token lifetime',
            name='freenas_token_lifetime',
            get='freenas_token_lifetime',
            type=ValueType.NUMBER,
            usage=_("""\
            Period of validity of one time authentication tokens
            used by peers of a type 'freenas'.
            This value is expressed in seconds."""),
        )


@description("Configuration database operations")
class ConfigDbNamespace(Namespace):
    def commands(self):
        return {
            'factory_restore': FactoryRestoreCommand(),
            'download': DownloadConfigCommand(),
            'upload': UploadConfigCommand(),
        }


@description("FreeNAS Debug Namespace")
class DebugNamespace(Namespace):
    def commands(self):
        return {
            'download': DownloadDebugCommand()
        }


class SystemDatasetNamespace(ConfigNamespace):
    def __init__(self, name, context):
        super(SystemDatasetNamespace, self).__init__(name, context)
        self.config_call = 'system_dataset.status'
        self.update_task = 'system_dataset.migrate'

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

        self.extra_commands = {
            'import': SystemDatasetImportCommand(self)
        }

    def save(self):
        return self.context.submit_task(
            'system_dataset.migrate',
            self.entity['pool'],
            callback=lambda s, t: post_save(self, s, t)
        )


@description("System power management options")
class SystemNamespace(ConfigNamespace):
    """
    The system namespace provides commands for configuring system
    settings and listing system information.
    """
    def __init__(self, name, context):
        super(SystemNamespace, self).__init__(name, context)
        self.context = context
        self.config_call = 'system.general.get_config'
        self.update_task = 'system.general.update'

        self.add_property(
            descr='Time zone',
            name='timezone',
            usage=_("""\
                Use set or edit to change the timezone. Type
                timezones to see the list of valid timezones."""),
            get='timezone',
        )

        self.add_property(
            descr='Hostname',
            name='hostname',
            usage=_("""\
                Use set or edit to change the system's hostname. The
                hostname must include the domain name. If the network does
                not use a domain name add .local to the end of the
                hostname.."""),
            get='hostname'
        )

        self.add_property(
            descr='Description',
            name='description',
            get='description'
        )

        self.add_property(
            descr='Tags',
            name='tags',
            get='tags',
            type=ValueType.SET
        )

        self.add_property(
            descr='Syslog Server',
            name='syslog_server',
            usage=_("""\
                Use set or edit to set the IP address or
                hostname:optional_port_number of remote syslog server to
                send logs to. If set, log entries will be written to both
                the log namespace and the remote server."""),
            get='syslog_server'
        )

        self.add_property(
            descr='Language',
            name='language',
            usage=_("""\
                Use set or edit to change the localization to the
                two-letter ISO 3166 country code."""),
            get='language'
        )

        self.add_property(
            descr='Console Keymap',
            name='console_keymap',
            usage=_("""\
                Use set or edit to change the console keyboard
                layout."""),
            get='console_keymap'
        )

        self.extra_commands = {
            'status': StatusCommand(),
            'version': VersionCommand(),
            'packages': PackagesCommand(),
            'timezones': TimezonesCommand(),
            'info': InfoCommand(),
            'reboot': RebootCommand(),
            'shutdown': ShutdownCommand()
        }

    def save(self):
        return self.context.submit_task(
            'system.general.update',
            self.entity,
            callback=lambda s, t: post_save(self, s, t)
        )

    def namespaces(self):
        return [
            SystemUINamespace('ui', self.context),
            AdvancedNamespace('advanced', self.context),
            TimeNamespace('time', self.context),
            NTPServersNamespace('ntp', self.context),
            MailNamespace('mail', self.context),
            SystemDatasetNamespace('system_dataset', self.context),
            ConfigDbNamespace('config'),
            DebugNamespace('debug')
        ]


def _init(context):
    context.attach_namespace('/', SystemNamespace('system', context))
    context.map_tasks('system.general.*', SystemNamespace)
    context.map_tasks('system.advanced.*', AdvancedNamespace)
    context.map_tasks('system.ui.*', SystemUINamespace)
    context.map_tasks('mail.*', MailNamespace)
