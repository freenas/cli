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
        context.submit_task('system_dataset.import', vol, callback=lambda s: post_save(self.parent, s))


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
            list=True
        )

        self.add_property(
            descr='Bootup time',
            name='boot_time',
            get='boot_time',
            set=None,
            list=True
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
            get='webui_https_certificate',
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
            enum=[e['name'] for e in self.context.call_sync('system.device.get_devices', "serial_port")]
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


@description("Configuration database operations")
class ConfigDbNamespace(Namespace):
    def commands(self):
        return {
            'factory_restore': FactoryRestoreCommand(),
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
        self.context.submit_task(
            'system_dataset.migrate',
            self.entity['pool'],
            callback=lambda s, t: post_save(self, s, t)
        )


@description("System info and configuration")
class SettingsNamespace(ConfigNamespace):
    """
    The system namespace provides commands for configuring system
    settings and listing system information.
    """

    def __init__(self, name, context):
        super(SettingsNamespace, self).__init__(name, context)
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
            'timezones': TimezonesCommand(),
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
            MailNamespace('mail', self.context),
            SystemDatasetNamespace('system_dataset', self.context),
            ConfigDbNamespace('config'),
        ]


def _init(context):
    context.attach_namespace('/', SettingsNamespace('settings', context))
    context.map_tasks('system.general.*', SettingsNamespace)
    context.map_tasks('system.advanced.*', AdvancedNamespace)
    context.map_tasks('system.ui.*', SystemUINamespace)
    context.map_tasks('mail.*', MailNamespace)
