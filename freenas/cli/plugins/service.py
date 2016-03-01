# #+
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
import gettext
from freenas.cli.namespace import (
    Namespace, ItemNamespace, EntityNamespace, RpcBasedLoadMixin, TaskBasedSaveMixin,
    Command, description
)
from freenas.cli.output import ValueType
from freenas.cli.utils import post_save


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Start/stop/restart/reload a service")
class ServiceManageCommand(Command):
    """
    Usage: start, stop, restart, reload

    start - starts a service
    stop - stops a service
    restart - restarts a service
    reload - gracefully restarts a service
    """
    def __init__(self, parent, action):
        self.parent = parent
        self.action = action

    @property
    def description(self):
        return '{0}s service'.format(self.action.title())

    def run(self, context, args, kwargs, opargs):
        context.submit_task(
            'service.manage',
            self.parent.entity['id'],
            self.action,
            callback=lambda s: post_save(self.parent, s)
        )


@description("Configure and manage services")
class ServicesNamespace(TaskBasedSaveMixin, RpcBasedLoadMixin, EntityNamespace):
    """
    The service namespace is used to configure, start, and
    stop system services.
    """
    def __init__(self, name, context):
        super(ServicesNamespace, self).__init__(name, context)
        self.query_call = 'service.query'
        self.save_key_name = 'id'
        self.update_task = 'service.update'
        self.extra_query_params = [('builtin', '=', False)]

        self.primary_key_name = 'name'
        self.add_property(
            descr='Service name',
            name='name',
            get='name',
            usage=_("""
            Name of the service. Read-only value assigned by
            the operating system."""),
            set=None,
            list=True
        )

        self.add_property(
            descr='State',
            name='state',
            get='state',
            usage= _("""
            Indicates whether the service is RUNNING or STOPPED.
            Read-only value assigned by the operating system."""),
            set=None,
            list=True
        )

        self.add_property(
            descr='Process ID',
            name='pid',
            get='pid',
            usage= _("""
            Process ID of the RUNNING service. Read-only value assigned
            by the operating system."""),
            set=None,
            list=True
        )

        self.primary_key = self.get_mapping('name')
        self.allow_edit = False
        self.allow_create = False
        self.entity_namespaces = lambda this: [
            ServiceConfigNamespace('config', context, this)
        ]
        self.entity_serialize = self.child_serialize
        self.entity_commands = lambda this: {
            'start': ServiceManageCommand(this, 'start'),
            'stop': ServiceManageCommand(this, 'stop'),
            'restart': ServiceManageCommand(this, 'restart'),
            'reload': ServiceManageCommand(this, 'reload')
        }

    def child_serialize(self, this):
        return Namespace.serialize(this)


class ServiceConfigNamespace(ItemNamespace):
    def __init__(self, name, context, parent):
        super(ServiceConfigNamespace, self).__init__(name)
        self.context = context
        self.parent = parent

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.get_properties(parent.name)

    def load(self):
        self.entity = self.parent.entity['config']
        self.orig_entity = copy.deepcopy(self.entity)

    def save(self):
        return self.parent.save()

    def get_properties(self, name):
        svc_props = svc_cli_config.get(name)
        if svc_props:
            for item in svc_props:
                self.add_property(**item)


def _init(context):
    context.attach_namespace('/', ServicesNamespace('service', context))


# This is not ideal (but better than an if-else ladder)
svc_cli_config = {
    'sshd': [
        {
            'descr': 'sftp log facility',
            'name': 'sftp_log_facility',
            'get': 'sftp_log_facility',
            'type': ValueType.STRING
        },
        {
            'descr': 'Allow public key authentication',
            'name': 'allow_pubkey_auth',
            'usage': _("""
            Can be set to yes. If set to yes, properly
            configured key-based authentication for all users
            is required."""),
            'get': 'allow_pubkey_auth',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Enable compression',
            'name': 'compression',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            compression may reduce latency over slow networks."""),
            'get': 'compression',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Allow password authentication',
            'name': 'allow_password_auth',
            'usage': _("""
            Can be set to yes or no. If set to yes,
            passoword logins are allowed."""),
            'get': 'allow_password_auth',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Allow port forwarding',
            'name': 'allow_port_forwarding',
            'usage': _("""
            Can be set to yes or no. If set to yes, users can
            bypass firewall restrictions using SSH’s port forwarding
            feature."""),
            'get': 'allow_port_forwarding',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Permit root login',
            'name': 'permit_root_login',
            'usage': _("""
            Can be set to yes or no. Setting to yes is discouraged
            for security reasons."""),
            'get': 'permit_root_login',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'sftp log level',
            'name': 'sftp_log_level',
            'get': 'sftp_log_level',
            'type': ValueType.STRING
        },
        {
            'descr': 'Port',
            'name': 'port',
            'usage': _("""
            Numeric port to open for SSH connection requests."""),
            'get': 'port',
            'type': ValueType.NUMBER
        }
    ],
    'nginx': [
        {
            'descr': 'Redirect http to https',
            'name': 'http.redirect_https',
            'get': 'http.redirect_https',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Enable http',
            'name': 'http.enable',
            'get': 'http.enable',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'http port',
            'name': 'http.port',
            'get': 'http.port',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Enable https',
            'name': 'https.enable',
            'get': 'https.enable',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'https port',
            'name': 'https.port',
            'get': 'https.port',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Https certificate',
            'name': 'https.certificate',
            'get': 'https.certificate',
            'type': ValueType.STRING
        }
    ],
    "ftp": [
        {
            'descr': 'ftp port',
            'name': 'port',
            'usage': _("""
            Numeric port the FTP service listens on."""),
            'get': 'port',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Maximum clients',
            'name': 'max_clients',
            'usage': _("""
            Number representing the maximum number of simultaneous
            clients."""),
            'get': 'max_clients',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Maximum connections per IP',
            'name': 'ip_connections',
            'usage': _("""
            Number representing the maximum number of connections
            per IP address, where 0 means unlimited."""),
            'get': 'ip_connections',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Maximum login attempts',
            'name': 'login_attempts',
            'usage': _("""
            Number representing the maximum number of failed login
            attempts before client is disconnected."""),
            'get': 'login_atempt',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Idle timeout',
            'name': 'timeout',
            'usage': _("""
            Number representing the maximum client idle time, in
            seconds, before client is disconnected."""),
            'get': 'timeout',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'root login',
            'name': 'root_login',
            'usage': _("""
            Can be set to yes or no and indicates whether or not
            root logins are allowed."""),
            'get': 'root_login',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Path for anonymous login',
            'name': 'anonymous_path',
            'usage': _("""
            Full path to the root directory for anonymous FTP
            connections."""),
            'get': 'anonymous_path',
            'type': ValueType.STRING
        },
        {
            'descr': 'Only allow anonymous login',
            'name': 'only_anonymous',
            'usage': _("""
            Can be set to yes or no and indicates whether or not
            only anonymous logins are allowed."""),
            'get': 'only_anonymous',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Only allow local user login',
            'name': 'only_local',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            anonymous logins are not allowed."""),
            'get': 'only_local',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Login message',
            'name': 'display_login',
            'usage': _("""
            Message displayed to local login users after authentication.
            It is not displayed to anonymous login users. Enclose the
            message between double quotes."""),
            'get': 'display_login',
            'type': ValueType.STRING
        },
        {
            'descr': 'File creation mask',
            'name': 'filemask',
            'get': 'filemask',
            'regex': '^\d{0,4}$',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Directory creation mask',
            'name': 'dirmask',
            'get': 'dirmask',
            'regex': '^\d{0,4}$',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Enable FXP protocol',
            'name': 'fxp',
            'get': 'fxp',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            it enables the File eXchange Protocol which is
            discouraged as it makes the server vulnerable to
            FTP bounce attacks."""),
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Automatic transfer resumption',
            'name': 'resume',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            FTP clients can resume interrupted transfers."""),
            'get': 'resume',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Chroot local users',
            'name': 'chroot',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            local users are restricted to their own home
            directory except for users which are members of
            the wheel group."""),
            'get': 'chroot',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Require identd authentication',
            'name': 'ident',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            timeouts will occur if the identd service is not
            running on the client."""),
            'get': 'ident',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Perform reverse DNS lookups',
            'name': 'reverse_dns',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            the system will perform reverse DNS lookups on client
            IPs. This can cause long delays if reverse DNS is not
            configured."""),
            'get': 'reverse_dns',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Masquerade address',
            'name': 'masquerade_address',
            'usage': _("""
            System's public IP address or hostname. Set this
            property if FTP clients can not connect through a
            NAT device."""),
            'get': 'masquerade_address',
            'type': ValueType.STRING
        },
        {
            'descr': 'Minimum passive ports',
            'name': 'passive_ports_min',
            'usage': _("""
            Numeric port number indicating the lowest port number
            available to FTP clients in PASV mode. Default of 0
            means any port above 1023."""),
            'get': 'passive_ports_min',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Maximum passive ports',
            'name': 'passive_ports_max',
            'usage': _("""
            Numeric port number indicating the highest port number
            available to FTP clients in PASV mode. Default of 0
            means any port above 1023."""),
            'get': 'passive_ports_max',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Local user upload bandwidth',
            'name': 'local_up_bandwidth',
            'usage': _("""
            Number representing the maximum upload bandwidth per local
            user in KB/s. Default of 0 means unlimited."""),
            'get': 'local_up_bandwidth',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Local user download bandwidth',
            'name': 'local_down_bandwidth',
            'usage': _("""
            Number representing the maximum download bandwidth per
            local user in KB/s. Default of 0 means unlimited."""),
            'get': 'local_down_bandwidth',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Anonymous upload bandwidth',
            'name': 'anon_up_bandwidth',
            'usage': _("""
            Number representing the maximum upload bandwidth per
            anonymous user in KB/s. Default of 0 means unlimited."""),
            'get': 'anon_up_bandwidth',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Anonymous download bandwidth',
            'name': 'anon_down_bandwidth',
            'usage': _("""
            Number representing the maximum download bandwidth per
            anonymous user in KB/s. Default of 0 means unlimited."""),
            'get': 'anon_down_bandwidth',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Enable TLS',
            'name': 'tls',
            'usage': _("""
            Can be set to yes or no. When set to yes, it
            enables encrypted connections and requires a certificate to
            be created or imported."""),
            'get': 'tls',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'TLS Policy',
            'name': 'tls_policy',
            'usage': _("""
            The specified policy defines whether the control
            channel, data channel, both channels, or neither
            channel of an FTP session must occur over SSL/TLS.
            Valid values are ON, OFF, DATA, !DATA, AUTH, CTRL,
            CTRL+DATA, CTRL+!DATA, AUTH+DATA, or AUTH+!DATA."""),
            'get': 'tls_policy',
            'enum': [
                'ON',
                'OFF',
                'DATA',
                '!DATA',
                'AUTH',
                'CTRL',
                'CTRL+DATA',
                'CTRL+!DATA',
                'AUTH+DATA',
                'AUTH+!DATA',
            ],
            'type': ValueType.STRING
        },
        {
            'descr': 'TLS Options',
            'name': 'tls_options',
            'usage': _("""
            The following options can be set:
            ALLOW_CLIENT_RENEGOTIATIONS, ALLOW_DOT_LOGIN,
            ALLOW_PER_USER, COMMON_NAME_REQUIRED,
            ENABLE_DIAGNOSTICS, EXPORT_CERTIFICATE_DATA,
            NO_CERTIFICATE_REQUEST, NO_EMPTY_FRAGMENTS,
            NO_SESSION_REUSE_REQUIRED, STANDARD_ENV_VARS,
            DNS_NAME_REQUIRED, IP_ADDRESS_REQUIRED. Separate
            mutiple options with a space and enclose between
            double quotes."""),
            'get': 'tls_options',
            'enum': [
                    'ALLOW_CLIENT_RENEGOTIATIONS',
                    'ALLOW_DOT_LOGIN',
                    'ALLOW_PER_USER',
                    'COMMON_NAME_REQUIRED',
                    'ENABLE_DIAGNOSTICS',
                    'EXPORT_CERTIFICATE_DATA',
                    'NO_CERTIFICATE_REQUEST',
                    'NO_EMPTY_FRAGMENTS',
                    'NO_SESSION_REUSE_REQUIRED',
                    'STANDARD_ENV_VARS',
                    'DNS_NAME_REQUIRED',
                    'IP_ADDRESS_REQUIRED',
            ],
            'type': ValueType.SET
        },
        {
            'descr': 'TLS SSL Certificate',
            'name': 'tls_ssl_certificate',
            'usage': _("""
            The SSL certificate to be used for TLS FTP
            connections. Enclose the certificate between double
            quotes"""),
            'get': 'tls_ssl_certificate',
            'type': ValueType.STRING
        },
        {
            'descr': 'Auxiliary parameters',
            'name': 'auxiliary',
            'usage': _("""
            Optional, additional proftpd(8) parameters not provided
            by other properties. Space delimited list of parameters
            enclosed between double quotes."""),
            'get': 'auxiliary',
            'type': ValueType.STRING
        },
    ],
    "afp": [
        {
            'descr': 'Share Home Directory',
            'name': 'homedir_enable',
            'get': 'homedir_enable',
            'usage': _("""
            Can be set to yes or no. When set to 'yes', user home
            directories located under 'homedir_path' will be available
            over AFP shares."""),
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Home Directory Path',
            'name': 'homedir_path',
            'get': 'homedir_path',
            'usage': _("""
            Enclose the path to the volume or dataset which contains the
            home directories between double quotes."""),
            'type': ValueType.STRING
        },
        {
            'descr': 'Home Directory Name',
            'name': 'homedir_name',
            'get': 'homedir_name',
            'usage': _("""
            Optional setting which overrides default home folder name
            with the specified value."""),
            'type': ValueType.STRING
        },
        {
            'descr': 'Auxiliary Parameters',
            'name': 'auxiliary',
            'get': 'auxiliary',
            'usage': _("""
            Optional, additional afp.conf(5) parameters not provided
            by other properties. Space delimited list of parameters
            enclosed between double quotes."""),
            'type': ValueType.STRING
        },
        {
            'descr': 'Connections limit',
            'name': 'connections_limit',
            'get': 'connections_limit',
            'usage': _("""
            Maximum number of simultaneous connections."""),
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Guest user',
            'name': 'guest_user',
            'get': 'guest_user',
            'usage': _("""
            The specified user account must exist and have permissions to the
            volume or dataset being shared."""),
            'type': ValueType.STRING
        },
        {
            'descr': 'Enable guest user',
            'name': 'guest_enable',
            'get': 'guest_enable',
            'usage': _("""
            Can be set to yes or no. When set to yes, clients will not be
            prompted to authenticate before accessing AFP shares."""),
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Bind Addresses',
            'name': 'bind_addresses',
            'get': 'bind_addresses',
            'usage': _("""
            IP address(es) to listen for FTP connections. Separate multiple
            IP addresses with a space and enclose between double quotes."""),
            'list': True,
            'type': ValueType.SET
        },
        {
            'descr': 'Database Path',
            'name': 'dbpath',
            'get': 'dbpath',
            'usage': _("""
            Optional. Specify the path to store the CNID databases used by AFP,
            where the default is the root of the volume. The path must be
            writable and enclosed between double quotes."""),
            'type': ValueType.STRING
        },
    ],
    "smb": [
        {
            'descr': 'NetBIOS Name',
            'name': 'netbiosname',
            'usage': _("""
            Must be different from the 'Workgroup'."""),
            'get': 'netbiosname',
            'type': ValueType.SET
        },
        {
            'descr': 'Workgroup',
            'name': 'workgroup',
            'usage': _("""
            Must match the Windows workgroup name. This setting is
            ignored if the Active Directory or LDAP service is
            running."""),
            'get': 'workgroup'
        },
        {
            'descr': 'description',
            'name': 'description',
            'usage': _("""
            Optional. Enclose between double quotes if it contains
            a space."""),
            'get': 'description',
        },
        {
            'descr': 'DOS Character Set',
            'name': 'dos_charset',
            'usage': _("""
            Must be different from the 'Workgroup'."""),
            'get': 'dos_charset'
        },
        {
            'descr': 'UNIX Character Set',
            'name': 'unix_charset',
            'get': 'unix_charset'
        },
        {
            'descr': 'Log level',
            'name': 'log_level',
            'get': 'log_level',
        },
        {
            'descr': 'Log in syslog',
            'name': 'syslog',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            authentication failures are logged to /var/log/messages
            instead of the default of /var/log/samba4/log.smbd."""),
            'get': 'syslog',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Local master',
            'name': 'local_master',
            'usage': _("""
            Can be set to yes or no. When set to yes, the system
            will participate in a browser election. Should be set
            to no when network contains an AD or LDAP server. Does
            not need to be set if Vista or Windows 7 machines are
            present."""),
            'get': 'local_master',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Domain logons',
            'name': 'domain_logons',
            'usage': _("""
            Can be set to yes or no. Only set to yes when
            if need to provide the netlogin service for older
            Windows clients."""),
            'get': 'domain_logons',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Time server',
            'name': 'time_server',
            'usage': _("""
            Can be set to yes or no and determines whether or not the
            system advertises itself as a time server to Windows
            clients. Do not set to yes if the network contains an AD
            or LDAP server."""),
            'get': 'time_server',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Guest User',
            'name': 'guest_user',
            'usage': _("""
            The specified user account must exist and have permissions to the
            volume or dataset being shared."""),
            'get': 'guest_user'
        },
        {
            'descr': 'File mask',
            'name': 'filemask',
            'get': 'filemask',
        },
        {
            'descr': 'Directory mask',
            'name': 'dirmask',
            'get': 'dirmask',
        },
        {
            'descr': 'Empty password logons',
            'name': 'empty_password',
            'usage': _("""
            Can be set to yes or no. If set to yes,
            users can just press Enter when prompted for a
            password. Requires that the username/password be the
            same as the Windows user account."""),
            'get': 'empty_password',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'UNIX Extensions',
            'name': 'unixext',
            'usage': _("""
            Can be set to yes or no. If set to yes,
            non-Windows clients can access symbolic links
            and hard links. This property has no effect on Windows
            clients."""),
            'get': 'unixext',
            'type': ValueType.BOOLEAN
        },

        {
            'descr': 'Zero Configuration',
            'name': 'zeroconf',
            'usage': _("""
            Can be set to yes or no. Set to yes if MAC
            clients will be connecting to the smb share."""),
            'get': 'zeroconf',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Host lookup',
            'name': 'hostlookup',
            'usage': _("""
            Can be set to yes or no. If set to yes, you can
            specify hostnames rather than IP addresses in the
            hosts_allow or hosts_deny properties of a smb share.
            Set to no if you only use IP addresses as it saves
            the time of a host lookup."""),
            'get': 'hostlookup',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Minimum Protocol',
            'name': 'min_protocol',
            'usage': _("""
            The minimum protocol version the server will support.
            Valid values, in order, are: CORE, COREPLUS, LANMAN1,
            LANMAN2, NT1, SMB2, SMB2_02, SMB2_10, SMB2_22,
            SMB2_24, SMB3,, or SMB3_00. The set value must be lower
            than the max_protocol."""),
            'get': 'min_protocol',
        },
        {
            'descr': 'Maximum Protocol',
            'name': 'max_protocol',
            'usage': _("""
            The maximum protocol version the server will support.
            Valid values, in order, are: CORE, COREPLUS, LANMAN1,
            LANMAN2, NT1, SMB2, SMB2_02, SMB2_10, SMB2_22,
            SMB2_24, SMB3,, or SMB3_00. The set value must be higher
            than the min_protocol."""),
            'get': 'max_protocol',
        },
        {
            'descr': 'Always Execute',
            'name': 'execute_always',
            'usage': _("""
            Can be set to yes or no. If set to yes, any user can
            execute a file, even if that user's permissions are
            not set to execute."""),
            'get': 'execute_always',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Obey PAM Restrictions',
            'name': 'obey_pam_restrictions',
            'usage': _("""
            Can be set to yes or no. If set to no, cross-domain
            authentication is allowed so that users and groups can
            be managed on another forest, and permissions can be
            delegated from AD users and groups to domain admins on
            another forest."""),
            'get': 'obey_pam_restrictions',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Bind addresses',
            'name': 'bind_addresses',
            'usage': _("""
            Space delimited list of IP address(es) that the smb service
            should listen on. Enclose the list between double quotes.
            If not set, the service will listen on all available
            addresses."""),
            'get': 'bind_addresses',
            'list': True,
            'type': ValueType.SET
        },
        {
            'descr': 'Auxiliary',
            'name': 'auxiliary',
            'usage': _("""
            Optional, additional smb.conf parameters. Separate multiple
            parameters by a space and enclose them between double quotes."""),
            'get': 'auxiliary'
        },
    ],
    "dyndns": [
        {
            'descr': 'DynDNS Provider',
            'name': 'provider',
            'usage': _("""
            Name of the DDNS provider."""),
            'get': 'provider'
        },
        {
            'descr': 'IP Server',
            'name': 'ipserver',
            'usage': _("""
            Can be used to specify the hostname and port of the IP
            check server."""),
            'get': 'ipserver'
        },
        {
            'descr': 'Domains',
            'name': 'domains',
            'get': 'domains',
            'usage': _("""
            Your system's fully qualified domain name in the format
            "yourname.dyndns.org"."""),
            'type': ValueType.SET
        },
        {
            'descr': 'Username',
            'name': 'username',
            'usage': _("""
            Username used to logon to the provider and update the
            record."""),
            'get': 'username'
        },
        {
            'descr': 'Password',
            'name': 'password',
            'usage': _("""
            Password used to logon to the provider and update the
            record."""),
            'get': None,
            'set': 'password'
        },
        {
            'descr': 'Update period',
            'name': 'update_period',
            'usage': _("""
            Number representing how often the IP is checked in seconds."""),
            'get': 'update_period',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Force update period',
            'name': 'force_update_period',
            'usage': _("""
            Number representing how often the IP should be updated, even it
            has not changed, in seconds."""),
            'get': 'force_update_period',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Auxiliary',
            'name': 'auxiliary',
            'usage': _("""
            Optional, additional parameters passed to the provider during
            record update. Separate multiple parameters by a space and
            enclose them between double quotes."""),
            'get': 'auxiliary'
        },
    ],
    "ipfs": [
        {
            'descr': 'IPFS PATH',
            'name': 'path',
            'get': 'path'
        },
    ],
    "nfs": [
        {
            'descr': 'Number of servers',
            'name': 'servers',
            'usage': _("""
            When setting this number, do not exceed the number
            of CPUS shown from running shell "sysctl -n
            kern.smp.cpus"."""),
            'get': 'update_period',
            'get': 'servers',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Enable UDP',
            'name': 'udp',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            older NFS clients that require UDP are supported."""),
            'get': 'update_period',
            'get': 'udp',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Enable NFSv4',
            'name': 'v4',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            both NFSv3 and NFSv4 are supported."""),
            'get': 'v4',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Enable NFSv4 Kerberos',
            'name': 'v4_kerberos',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            NFS shares will fail if the Kerberos ticket is
            unavailable."""),
            'get': 'v4_kerberos',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Bind addresses',
            'name': 'bind_addresses',
            'usage': _("""
            Space delimited list of IP addresses to listen for NFS
            requests, placed between double quotes. Unless specified,
            NFS will listen on all available addresses."""),
            'get': 'update_period',
            'get': 'bind_addresses',
            'type': ValueType.SET
        },
        {
            'descr': 'Mountd port',
            'name': 'mountd_port',
            'usage': _("""
            Number representing the port for mountd(8) to bind to."""),
            'get': 'update_period',
            'get': 'mountd_port',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'RPC statd port',
            'name': 'rpcstatd_port',
            'usage': _("""
            Number representing the port for rpcstatd(8) to bind to."""),
            'get': 'rpcstatd_port',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'RPC Lockd port',
            'name': 'rpclockd_port',
            'usage': _("""
            Number representing the port for rpclockd(8) to bind to."""),
            'get': 'rpclockd_port',
            'type': ValueType.NUMBER
        },
    ],
    "glusterd": [
        {
            'descr': 'Working directory',
            'name': 'working_directory',
            'get': 'working_directory',
            'type': ValueType.STRING
        },
    ],
    "haproxy": [
        {
            'descr': 'Global maximum connections',
            'name': 'global_maxconn',
            'get': 'global_maxconn',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Default maximum connections',
            'name': 'default_maxconn',
            'get': 'defaults_maxconn',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'HTTP IP address',
            'name': 'http_ip',
            'get': 'http_ip',
            'type': ValueType.STRING
        },
        {
            'descr': 'HTTP port',
            'name': 'http_port',
            'get': 'http_port',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'HTTPS IP address',
            'name': 'https_ip',
            'get': 'https_ip',
            'type': ValueType.STRING
        },
        {
            'descr': 'HTTPS port',
            'name': 'https_port',
            'get': 'https_port',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Frontend mode',
            'name': 'frontend_mode',
            'get': 'frontend_mode',
            'enum': ['HTTP', 'TCP'],
            'type': ValueType.STRING
        },
        {
            'descr': 'Backend mode',
            'name': 'backend_mode',
            'get': 'backend_mode',
            'enum': ['HTTP', 'TCP'],
            'type': ValueType.STRING
        },
    ],
    "iscsi": [
        {
            'descr': 'Base name',
            'name': 'base_name',
            'usage': _("""
            Name in IQN format as described by RFC 3721. Enclose
            name between double quotes."""),
            'get': 'base_name',
            'type': ValueType.STRING
        },
        {
            'descr': 'Pool space threshold',
            'name': 'pool_space_threshold',
            'usage': _("""
            Number representing the percentage of free space that should
            remain in the pool. When this percentage is reached, the
            system will issue an alert, but only if zvols are used."""),
            'get': 'pool_space_threshold',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'ISNS servers',
            'name': 'isns_servers',
            'usage': _("""
            Space delimited list of hostnames or IP addresses of ISNS server(s)
            to register the system’s iSCSI targets and portals with. Enclose
            the list between double quotes."""),
            'get': 'isns_servers',
            'type': ValueType.SET
        },
    ],
    "lldp": [
        {
            'descr': 'Save description',
            'name': 'save_description',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            receive mode is enabled and received peer information
            is saved in interface descriptions."""),
            'get': 'save_description',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Country code',
            'name': 'country_code',
            'usage': _("""
            Required for LLDP location support. Input 2 letter ISO 3166
            country code."""),
            'get': 'country_code',
            'type': ValueType.STRING
        },
        {
            'descr': 'Location',
            'name': 'location',
            'usage': _("""
            Optional, physical location of the host enclosed within
            double quotes."""),
            'get': 'location',
            'type': ValueType.STRING
        },
    ],
    "snmp": [
        {
            'descr': 'Location',
            'name': 'location',
            'usage': _("""
            Optional, physical location of the host enclosed within
            double quotes."""),
            'get': 'location',
            'type': ValueType.STRING
        },
        {
            'descr': 'Contact',
            'name': 'contact',
            'usage': _("""
            Optional, email address of administrator enclosed within
            double quotes."""),
            'get': 'contact',
            'type': ValueType.STRING
        },
        {
            'descr': 'Enable SNMPv3',
            'name': 'v3',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            support for SNMP version 3 is enabled."""),
            'get': 'v3',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'SNMPv3 Username',
            'name': 'v3_username',
            'usage': _("""
            Only set if 'v3' is set. Specify the username to
            register with the SNMPv3 service."""),
            'get': 'v3_username',
            'type': ValueType.STRING
        },
        {
            'descr': 'SNMPv3 Password',
            'name': 'v3_password',
            'usage': _("""
            Only set if 'v3' is set. Specify a password of
            at least 8 characters."""),
            'set': 'v3_password',
            'get': None,
            'list': False,
            'type': ValueType.STRING
        },
        {
            'descr': 'SNMPv3 Auth Type',
            'name': 'v3_auth_type',
            'usage': _("""
            Only set if 'v3' is set. Specify either
            MD5 or SHA."""),
            'get': 'v3_auth_type',
            'enum': ['MD5', 'SHA'],
            'type': ValueType.STRING
        },
        {
            'descr': 'SNMPv3 Privacy Protocol',
            'name': 'v3_privacy_protocol',
            'usage': _("""
            Only set if 'v3' is set. Specify either
            AES or DES."""),
            'get': 'v3_privacy_protocol',
            'enum': ['AES', 'DES'],
            'type': ValueType.STRING
        },
        {
            'descr': 'SNMPv3 Privacy Passphrase',
            'name': 'v3_privacy_passphrase',
            'usage': _("""
            Only set if 'v3' is set and 'v3_password' is not
            set. Specify a passphrase of at least 8
            characters."""),
            'get': None,
            'set': 'v3_privacy_passphrase',
            'list': False,
            'type': ValueType.STRING
        },
        {
            'descr': 'Auxiliary parameters',
            'name': 'auxiliary',
            'usage': _("""
            Optional, additional snmpd.conf(5) parameters. Separate
            multiple parameters by a space and enclose them between
            double quotes."""),
            'get': 'auxiliary',
            'type': ValueType.STRING
        },
    ],
    "smartd": [
        {
            'descr': 'Interval',
            'name': 'interval',
            'usage': _("""
            Number representing how often, in minutes, to wake
            up smartd to check to see if any tests have been
            configured to run."""),
            'get': 'interval',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Power mode',
            'name': 'power_mode',
            'usage': _("""
            Configured tests are not performed if the system enters
            the specified power mode. Values are: NEVER, SLEEP,
            STANDBY, or IDLE."""),
            'get': 'power_mode',
            'enum': [
                'NEVER',
                'SLEEP',
                'STANDBY',
                'IDLE',
            ],
            'type': ValueType.STRING
        },
        {
            'descr': 'Temperature difference',
            'name': 'temp_difference',
            'usage': _("""
            Default of 0 disables this check. Otherwise, reports if
            the temperature of a drive has changed by the specified
            number of degrees Celsius since last report."""),
            'get': 'temp_difference',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Temperature informational',
            'name': 'temp_informational',
            'usage': _("""
            By default, this check is disabled. If set, will log
            an entry of LOG_INFO if the temperature is higher than
            the specified number of degrees Celsius since the last
            report."""),
            'get': 'temp_informational',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Temperature critical',
            'name': 'temp_critical',
            'usage': _("""
            By default, this check is disabled. If set, will log
            an entry of LOG_CRIT and will send an email if the
            temperature is higher than the specified number of degrees
            Celsius since the last report."""),
            'get': 'temp_critical',
            'type': ValueType.NUMBER
        },
    ],
    "webdav": [
        {
            'descr': 'Protocol',
            'name': 'protocol',
            'usage': _("""
            Set to HTTP (connection always unencrypted), HTTPS
            (connection always encrypted), or HTTP+HTTPS (both
            types of connections allowed)."""),
            'get': 'protocol',
            'type': ValueType.SET,
            'list': True,
        },
        {
            'descr': 'HTTP Port',
            'name': 'http_port',
            'usage': _("""
            Only set if 'protocol' is HTTP or HTTP+HTTPS. Numeric
            port to be used for unencrypted connections. Do not set a
            port number already being used by another service."""),
            'get': 'http_port',
            'type': ValueType.NUMBER,
        },
        {
            'descr': 'HTTPS Port',
            'name': 'https_port',
            'usage': _("""
            Only set if 'protocol' is HTTPS or HTTP+HTTPS. Numeric
            port to be used for encrypted connections. Do not set a
            port number already being used by another service."""),
            'get': 'https_port',
            'type': ValueType.NUMBER,
        },
        {
            'descr': 'Password',
            'name': 'password',
            'usage': _("""
            Set a secure password to be used by the webdav user."""),
            'get': None,
            'set': 'password',
            'type': ValueType.STRING
        },
        {
            'descr': 'Authentication mode',
            'name': 'authentication',
            'usage': _("""
            Determines whether or not authentication occurs over
            an encrypted channel. Set either BASIC (unencrypted)
            or DIGEST (encrypted)."""),
            'get': 'authentication',
            'enum': [
                'BASIC',
                'DIGEST',
            ],
            'type': ValueType.STRING
        },
    ],
    "rsyncd": [
        {
            'descr': 'Port',
            'name': 'port',
            'usage': _("""Number representing the port for rsyncd to
            listen on."""),
            'get': 'port',
            'type': ValueType.NUMBER,
        },
        {
            'descr': 'Auxiliary',
            'name': 'auxiliary',
            'usage': _("""
                Optional, additional rsyncd.conf(5) parameters not provided
                by other properties. Space delimited list of parameters
                enclosed between double quotes.
            """),
            'get': 'auxiliary',
            'type': ValueType.STRING,
        },
    ],
    "tftpd": [
        {
            'descr': 'Port',
            'name': 'port',
            'usage': _("""Number representing the port for tftpd to
            listen on."""),
            'get': 'port',
            'type': ValueType.NUMBER,
        },
        {
            'descr': 'Path',
            'name': 'path',
            'usage': _(""" """),
            'get': 'path',
            'type': ValueType.STRING
        },
        {
            'descr': 'Allow New Files',
            'name': 'alllow_new_files',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            network devices can save files on the system."""),
            'get': 'alllow_new_files',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'UMASK',
            'name': 'umask',
            'usage': _("""
            Number representing the umask for newly created files, default
            is 022 (everyone can read, nobody can write). Some devices
            require a less strict umask."""),
            'get': 'umask',
            'type': ValueType.STRING
        },
        {
            'descr': 'Auxiliary',
            'name': 'auxiliary',
            'usage': _("""
            Optional, additional tftpd(8) parameters not provided
            by other properties. Space delimited list of parameters
            enclosed between double quotes."""),
            'get': 'auxiliary',
            'type': ValueType.STRING
        }
    ],
    "ups": [
        {
            'descr': 'Mode',
            'name': 'mode',
            'usage': _("""
            Can be set to MASTER or SLAVE."""),
            'get': 'mode',
            'type': ValueType.STRING,
            'enum': ['MASTER', 'SLAVE'],
        },
        {
            'descr': 'Identifier',
            'name': 'identifier',
            'usage': _("""
            Can be set to an alphanumeric description."""),
            'get': 'identifier',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Remote Host',
            'name': 'remote_host',
            'usage': _(""""""),
            'get': 'remote_host',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Remote Port',
            'name': 'remote_port',
            'usage': _(""""""),
            'get': 'remote_port',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Driver',
            'name': 'driver',
            'usage': _(""""""),
            'get': 'driver',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Driver Port',
            'name': 'driver_port',
            'usage': _(""""""),
            'get': 'Driver_port',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Description',
            'name': 'description',
            'usage': _("""
            Optional description. If it contains any spaces,
            enclose it between double quotes."""),
            'get': 'description',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Shutdown Mode',
            'name': 'shutdown_mode',
            'usage': _("""
            Indicates when the UPS should shutdown. Can be set
            to BATT (UPS goes on battery) or LOWBATT (UPS
            reaches low battery)."""),
            'get': 'shutdown_mode',
            'type': ValueType.STRING,
            'enum': ['BATT', 'LOWBATT'],
        },
        {
            'descr': 'Shutdown Timer',
            'name': 'shutdown_timer',
            'usage': _("""
            Number in seconds. UPS will initiate shutdown this many
            seconds after UPS enters BATT 'shutdown_mode', unless power
            is restored"""),
            'get': 'shutdown_timer',
            'type': ValueType.NUMBER,
        },
        {
            'descr': 'Monitor User',
            'name': 'monitor_user',
            'usage': _(""""""),
            'get': 'monitor_user',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Monitor Password',
            'name': 'monitor_password',
            'usage': _(""""""),
            'get': None,
            'set': 'monitor_password',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Monitor Remote',
            'name': 'monitor_remote',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            the default is to listen on all interfaces and to use
            the known values upsmon for 'monitor_user' and
            fixmepass for 'monitor_password'."""),
            'get': 'monitor_remote',
            'type': ValueType.BOOLEAN,
        },
        {
            'descr': 'Auxiliary Users',
            'name': 'auxiliary_users',
            'usage': _(""""""),
            'get': 'auxiliary_users',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Email Notify',
            'name': 'email_notify',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            status updates will be emailed to
            'email_recipients'."""),
            'get': 'email_notify',
            'type': ValueType.BOOLEAN,
        },
        {
            'descr': 'Email Recipients',
            'name': 'email_recipients',
            'usage': _("""
            Space delimited list, enclosed between double
            quotes, of email addresses to receive status
            updates. This requires 'email_notify' to be set
            to yes."""),
            'get': 'email_recipients',
            'type': ValueType.SET,
        },
        {
            'descr': 'Email Subject',
            'name': 'email_subject',
            'usage': _("""
            Subject to use in status emails. Enclose between
            double quotes if it contains a space. Requires
            'email_notify' to be set to yes."""),
            'get': 'email_subject',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Powerdown',
            'name': 'powerdown',
            'usage': _("""
            Can be set to yes or no. When set to yes,
            the UPS will also power off after shutting down the
            FreeNAS system"""),
            'get': 'powerdown',
            'type': ValueType.BOOLEAN,
        },
        {
            'descr': 'Auxiliary',
            'name': 'auxiliary',
            'usage': _("""
            Optional, additional ups.conf(5) parameters not provided
            by other properties. Space delimited list of parameters
            enclosed between double quotes."""),
            'get': 'auxiliary',
            'type': ValueType.STRING,
        },
    ],
    'stanchion': [
        {
            'descr': 'Listener IP',
            'name': 'listener_ip',
            'usage': _(""" """),
            'get': 'listener_ip',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Listener Port',
            'name': 'listener_port',
            'usage': _(""" """),
            'get': 'listener_port',
            'type': ValueType.NUMBER,
        },
        {
            'descr': 'Riak Host IP',
            'name': 'riak_host_ip',
            'usage': _(""" """),
            'get': 'riak_host_ip',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Riak Host Port',
            'name': 'riak_host_port',
            'usage': _(""" """),
            'get': 'riak_host_port',
            'type': ValueType.NUMBER,
        },
        {
            'descr': 'Node name',
            'name': 'nodename',
            'usage': _(""" """),
            'get': 'nodename',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Node IP',
            'name': 'node_ip',
            'usage': _(""" """),
            'get': 'node_ip',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Log console level',
            'name': 'log_console_level',
            'usage': _(""" """),
            'get': 'log_console_level',
            'type': ValueType.STRING,
            'enum': ['NONE', 'DEBUG', 'INFO', 'WARNING', 'CRITICAL', 'ALERT', 'EMERGENCY', 'ERROR'],
        },
        {
            'descr': 'Admin Key',
            'name': 'admin_key',
            'usage': _(""" """),
            'get': 'admin_key',
            'type': ValueType.STRING,
        },       {
            'descr': 'Admin Secret',
            'name': 'admin_secret',
            'usage': _(""" """),
            'get': 'admin_secret',
            'type': ValueType.STRING,
        },
    ],
    'riak': [
        {
            'descr': 'Save Description',
            'name': 'save_description',
            'usage': _(""" """),
            'get': 'save_description',
            'type': ValueType.BOOLEAN,
        },
        {
            'descr': 'Node name',
            'name': 'nodename',
            'usage': _(""" """),
            'get': 'nodename',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Node IP',
            'name': 'node_ip',
            'usage': _(""" """),
            'get': 'node_ip',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Log Console Level',
            'name': 'log_console_level',
            'usage': _(""" """),
            'get': 'log_console_level',
            'type': ValueType.STRING,
            'enum': ['NONE', 'DEBUG', 'INFO', 'WARNING', 'CRITICAL', 'ALERT',  'EMERGENCY', 'ERROR']
        },
        {
            'descr': 'Storage Backend',
            'name': 'storage_backend',
            'usage': _(""" """),
            'get': 'storage_backend',
            'type': ValueType.STRING,
            'enum': ['BITCASK', 'LEVELDB', 'MEMORY', 'MULTI', 'PREFIX_MULTI']
        },
        {
            'descr': 'Buckets Default Allow Multi',
            'name': 'buckets_default_allow_multi',
            'usage': _(""" """),
            'get': 'buckets_default_allow_multi',
            'type': ValueType.BOOLEAN,
        },
        {
            'descr': 'Riak control',
            'name': 'riak_control',
            'usage': _(""" """),
            'get': 'riak_control',
            'type': ValueType.BOOLEAN,
        },
        {
            'descr': 'Listener HTTP Internal',
            'name': 'listener_http_internal',
            'usage': _(""" """),
            'get': 'listener_http_internal',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Listener HTTP Internal Port',
            'name': 'listener_http_internal_port',
            'usage': _(""" """),
            'get': 'listener_http_internal_port',
            'type': ValueType.NUMBER,
        },
        {
            'descr': 'Listener Protobuf Internal',
            'name': 'listener_protobuf_internal',
            'usage': _(""" """),
            'get': 'listener_protobuf_internal',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Listener Protobuf Internal Port',
            'name': 'listener_protobuf_internal_port',
            'usage': _(""" """),
            'get': 'listener_protobuf_internal_port',
            'type': ValueType.NUMBER,
        },
        {
            'descr': 'Listener HTTPS Internal',
            'name': 'listener_https_internal',
            'usage': _(""" """),
            'get': 'listener_https_internal',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Listener HTTPS Internal Port',
            'name': 'listener_https_internal_port',
            'usage': _(""" """),
            'get': 'listener_https_internal_port',
            'type': ValueType.NUMBER,
        },
        {
            'descr': 'Object Size Warning Threshold',
            'name': 'object_size_warning_threshold',
            'usage': _(""" """),
            'get': 'object_size_warning_threshold',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Object Size Maximum',
            'name': 'object_size_maximum',
            'usage': _(""" """),
            'get': 'object_size_maximum',
            'type': ValueType.STRING,
        },
    ],
    "swift": [
        {
            'descr': 'Hash Path Prefix',
            'name': 'hash_path_prefix',
            'usage': _("""String to be prefixed to Swift Hash Path"""),
            'get': 'swift_hash_path_prefix',
            'type': ValueType.STRING,
        },
        {
            'descr': 'Hash Path Suffix',
            'name': 'hash_path_suffix',
            'usage': _("""String to be suffixed to Swift Hash Path"""),
            'get': 'swift_hash_path_suffix',
            'type': ValueType.STRING,
        },
    ],
}

# A lot of riack_cs properties are stanchion repeats thus doing it in the following way:
svc_cli_config['riak_cs'] = svc_cli_config['stanchion'].copy()
svc_cli_config['riak_cs'].extend([
    {
        'descr': 'Stanchion Host IP',
        'name': 'stanchion_host_ip',
        'usage': _("""Stanchion Host IP"""),
        'get': 'stanchion_host_ip',
        'type': ValueType.STRING,
    },
    {
        'descr': 'Stanchion Host Port',
        'name': 'stanchion_host_port',
        'usage': _("""Stanchion Host Port"""),
        'get': 'stanchion_host_port',
        'type': ValueType.NUMBER,
    },
    {
        'descr': 'Anonymous User Creation',
        'name': 'anonymous_user_creation',
        'usage': _("""Boolean flag to allow/disallow anonymous user creation"""),
        'get': 'anonymous_user_creation',
        'type': ValueType.BOOLEAN,
    },
    {
        'descr': 'Max buckets per User',
        'name': 'max_buckets_per_user',
        'usage': _("""Specify the maximum number of buckets per user"""),
        'get': 'max_buckets_per_user',
        'type': ValueType.NUMBER,
    },
])
