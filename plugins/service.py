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


from namespace import ConfigNamespace, EntityNamespace, RpcBasedLoadMixin, Command, description
from output import ValueType
from utils import post_save


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
            self.parent.primary_key,
            self.action,
            callback=lambda s: post_save(self.parent, s)
        )


@description("Configure and manage services")
class ServicesNamespace(RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(ServicesNamespace, self).__init__(name, context)
        self.query_call = 'services.query'
        self.extra_query_params = [('builtin', '=', False)]

        self.primary_key_name = 'name'
        self.add_property(
            descr='Service name',
            name='name',
            get='name',
            set=None,
            list=True
        )

        self.add_property(
            descr='State',
            name='state',
            get='state',
            set=None,
            list=True
        )

        self.add_property(
            descr='Process ID',
            name='pid',
            get='pid',
            set=None,
            list=True
        )

        self.primary_key = self.get_mapping('name')
        self.allow_edit = False
        self.allow_create = False
        self.entity_namespaces = lambda this: [
            ServiceConfigNamespace('config', context, this)
        ]
        self.entity_commands = lambda this: {
            'start': ServiceManageCommand(this, 'start'),
            'stop': ServiceManageCommand(this, 'stop'),
            'restart': ServiceManageCommand(this, 'restart'),
            'reload': ServiceManageCommand(this, 'reload')
        }


class ServiceConfigNamespace(ConfigNamespace):
    def __init__(self, name, context, parent):
        super(ServiceConfigNamespace, self).__init__(name, context)
        self.parent = parent
        self.config_call = 'services.get_service_config'
        self.config_extra_params = parent.name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.get_properties(parent.name)

    def save(self):
        return self.context.submit_task(
            'service.configure',
            self.parent.entity['name'],
            self.get_diff(),
            callback=lambda s: post_save(self, s))

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
            'get': 'allow_pubkey_auth',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Enable compression',
            'name': 'compression',
            'get': 'compression',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Allow password authentication',
            'name': 'allow_password_auth',
            'get': 'allow_password_auth',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Allow port forwarding',
            'name': 'allow_port_forwarding',
            'get': 'allow_port_forwarding',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Permit root login',
            'name': 'permit_root_login',
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
            'get': 'port',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Maximum clients',
            'name': 'max_clients',
            'get': 'max_clients',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Maximum connections per IP',
            'name': 'ip_connections',
            'get': 'ip_connections',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Maximum login attempts',
            'name': 'login_attempts',
            'get': 'login_atempt',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Idle timeout',
            'name': 'timeout',
            'get': 'timeout',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'root login',
            'name': 'root_login',
            'get': 'root_login',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Path for anonymous login',
            'name': 'anonymous_path',
            'get': 'anonymous_path',
            'type': ValueType.STRING
        },
        {
            'descr': 'Only allow anonymous login',
            'name': 'only_anonymous',
            'get': 'only_anonymous',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Only allow local user login',
            'name': 'only_local',
            'get': 'only_local',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Login message',
            'name': 'display_login',
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
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Automatic transfer resumption',
            'name': 'resume',
            'get': 'resume',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Chroot local users',
            'name': 'chroot',
            'get': 'chroot',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Require identd authentication',
            'name': 'ident',
            'get': 'ident',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Perform reverse DNS lookups',
            'name': 'reverse_dns',
            'get': 'reverse_dns',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Masquerade address',
            'name': 'masquerade_address',
            'get': 'masquerade_address',
            'type': ValueType.STRING
        },
        {
            'descr': 'Minimum passive ports',
            'name': 'passive_ports_min',
            'get': 'passive_ports_min',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Maximum passive ports',
            'name': 'passive_ports_max',
            'get': 'passive_ports_max',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Local user upload bandwidth',
            'name': 'local_up_bandwidth',
            'get': 'local_up_bandwidth',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Local user download bandwidth',
            'name': 'local_down_bandwidth',
            'get': 'local_down_bandwidth',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Anonymous upload bandwidth',
            'name': 'anon_up_bandwidth',
            'get': 'anon_up_bandwidth',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Anonymous download bandwidth',
            'name': 'anon_down_bandwidth',
            'get': 'anon_down_bandwidth',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Enable TLS',
            'name': 'tls',
            'get': 'tls',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'TLS Policy',
            'name': 'tls_policy',
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
            'get': 'tls_ssl_certificate',
            'type': ValueType.STRING
        },
        {
            'descr': 'Auxiliary parameters',
            'name': 'auxiliary',
            'get': 'auxiliary',
            'type': ValueType.STRING
        },
    ],
    "afp": [
        {
            'descr': 'Share Home Directory',
            'name': 'homedir_enable',
            'get': 'homedir_enable',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Home Directory Path',
            'name': 'homedir_path',
            'get': 'homedir_path',
            'type': ValueType.STRING
        },
        {
            'descr': 'Home Directory Name',
            'name': 'homedir_name',
            'get': 'homedir_name',
            'type': ValueType.STRING
        },
        {
            'descr': 'Auxiliary Parameters',
            'name': 'auxiliary',
            'get': 'auxiliary',
            'type': ValueType.STRING
        },
        {
            'descr': 'Connections limit',
            'name': 'connections_limit',
            'get': 'connections_limit',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Guest user',
            'name': 'guest_user',
            'get': 'guest_user',
            'type': ValueType.STRING
        },
        {
            'descr': 'Enable guest user',
            'name': 'guest_enable',
            'get': 'guest_enable',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Bind Addresses',
            'name': 'bind_addresses',
            'get': 'bind_addresses',
            'list': True,
            'type': ValueType.SET
        },
        {
            'descr': 'Database Path',
            'name': 'dbpath',
            'get': 'dbpath',
            'type': ValueType.STRING
        },
    ],
    "cifs": [
        {
            'descr': 'NetBIOS Name',
            'name': 'netbiosname',
            'get': 'netbiosname',
            'type': ValueType.SET
        },
        {
            'descr': 'Workgroup',
            'name': 'workgroup',
            'get': 'workgroup'
        },
        {
            'descr': 'description',
            'name': 'description',
            'get': 'description',
        },
        {
            'descr': 'DOS Character Set',
            'name': 'dos_charset',
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
            'get': 'syslog',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Local master',
            'name': 'local_master',
            'get': 'local_master',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Domain logons',
            'name': 'domain_logons',
            'get': 'domain_logons',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Time server',
            'name': 'time_server',
            'get': 'time_server',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Guest User',
            'name': 'guest_user',
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
            'get': 'empty_password',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'UNIX Extensions',
            'name': 'unixext',
            'get': 'unixext',
            'type': ValueType.BOOLEAN
        },

        {
            'descr': 'Zero Configuration',
            'name': 'zeroconf',
            'get': 'zeroconf',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Host lookup',
            'name': 'hostlookup',
            'get': 'hostlookup',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Minimum Protocol',
            'name': 'min_protocol',
            'get': 'min_protocol',
        },
        {
            'descr': 'Maximum Protocol',
            'name': 'max_protocol',
            'get': 'max_protocol',
        },
        {
            'descr': 'Always Execute',
            'name': 'execute_always',
            'get': 'execute_always',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Obey PAM Restrictions',
            'name': 'obey_pam_restrictions',
            'get': 'obey_pam_restrictions',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Bind addresses',
            'name': 'bind_addresses',
            'get': 'bind_addresses',
            'list': True,
            'type': ValueType.SET
        },
        {
            'descr': 'Auxiliary',
            'name': 'auxiliary',
            'get': 'auxiliary'
        },
    ],
    "dyndns": [
        {
            'descr': 'DynDNS Provider',
            'name': 'provider',
            'get': 'provider'
        },
        {
            'descr': 'IP Server',
            'name': 'ipserver',
            'get': 'ipserver'
        },
        {
            'descr': 'Domains',
            'name': 'domains',
            'get': 'domains',
            'type': ValueType.SET
        },
        {
            'descr': 'Username',
            'name': 'username',
            'get': 'username'
        },
        {
            'descr': 'Password',
            'name': 'password',
            'get': 'password'
        },
        {
            'descr': 'Update period',
            'name': 'update_period',
            'get': 'update_period',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Force update period',
            'name': 'force_update_period',
            'get': 'force_update_period',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'Auxiliary',
            'name': 'auxiliary',
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
            'get': 'servers',
            'type': ValueType.NUMBER
        },        
        {
            'descr': 'Enable UDP',
            'name': 'udp',
            'get': 'udp',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Enable NFSv4',
            'name': 'v4',
            'get': 'v4',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Enable NFSv4 Kerberos',
            'name': 'v4_kerberos',
            'get': 'v4_kerberos',
            'type': ValueType.BOOLEAN
        },
        {
            'descr': 'Bind addresses',
            'name': 'bind_addresses',
            'get': 'bind_addresses',
            'type': ValueType.SET
        },
        {
            'descr': 'Mountd port',
            'name': 'mountd_port',
            'get': 'mountd_port',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'RPC statd port',
            'name': 'rpcstatd_port',
            'get': 'rpcstatd_port',
            'type': ValueType.NUMBER
        },
        {
            'descr': 'RPC Lockd port',
            'name': 'rpclockd_port',
            'get': 'rpclockd_port',
            'type': ValueType.NUMBER
        },
    ]
}
