#
# Copyright 2016 iXsystems, Inc.
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
from freenas.cli.namespace import (
    Namespace, ItemNamespace, EntityNamespace, EntitySubscriberBasedLoadMixin,
    Command, description, ConfigNamespace
)

from freenas.cli.output import Sequence, ValueType, Table
from freenas.cli.utils import TaskPromise

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


class ServiceManageMixIn(object):
    def __init__(self, name, context):
        super(ServiceManageMixIn, self).__init__(name, context)
        self.extra_commands = {
            'start': ServiceManageCommand(self, 'start'),
            'stop': ServiceManageCommand(self, 'stop'),
            'restart': ServiceManageCommand(self, 'restart'),
            'reload': ServiceManageCommand(self, 'reload'),
            'status': ServiceStatusCommand(self)
        }


@description("Configure OpenVPN general settings")
class OpenVPNNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The OpenVPN config namespace provides commands for listing,
    and managing OpenVPN settings.
    It also provides ability to generate corresponding client config and
    static key.
    """
    def __init__(self, name, context):
        super(OpenVPNNamespace, self).__init__(name, context)
        self.config_call = "service.openvpn.get_readable_config"
        self.update_task = 'service.openvpn.update'
        self.name = name

        self.extra_commands.update({
            'bridge': OpenVPNBridgeCommand(),
            'generate_crypto': OpenVPNCryptoCommand(),
            'provide_client_config': OpenVPNClientConfigCommand(),
            'provide_static_key': OpenVPNStaticKeyCommand()
        })
        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Device type for VPN server',
            name='dev',
            get='dev',
            set='dev',
            type=ValueType.STRING,
            usage=_('''\
            Device type for openvpn server. tap/tun''')
        )
        self.add_property(
            descr='Enables OpenVPN server',
            name='enable',
            get='enable',
            set='enable',
            type=ValueType.BOOLEAN,
            usage=_('''\
            Allows to start OpenVPN server at boot time''')
        )
        self.add_property(
            descr='OpenVPN server user',
            name='user',
            get='user',
            set='user',
            type=ValueType.STRING,
            usage=_('''\
            User for OpenVPN daemon privilege drop''')
        )
        self.add_property(
            descr='OpenVPN server group',
            name='group',
            get='group',
            set='group',
            type=ValueType.STRING,
            usage=_('''\
            User for OpenVPN daemon privilege drop''')
        )
        self.add_property(
            descr='Persist-key option',
            name='persist_key',
            get='persist_key',
            set='persist_key',
            type=ValueType.BOOLEAN,
            usage=_('''\
             Don't re-read key files across service restart.
             Without this option service can't re-read needed keys
             after dropping root privilges''')
        )
        self.add_property(
            descr='Persist-tun option',
            name='persist-tun',
            get='persist-tun',
            set='persist-tun',
            type=ValueType.BOOLEAN,
            usage=_('''\
             Don't close and reopen tap/tun device across restart.''')

        )
        self.add_property(
            descr='Symmetric cipher used by OpenVPN',
            name='cipher',
            get='cipher',
            set='cipher',
            enum=['BF-CBC', 'AES-128-CBC', 'DES-EDE3-CBC'],
            usage=_('''\
                You can choose between BF-CBC, AES-128-CBC, DES-EDE3-CBC ''')
        )
        self.add_property(
            descr='Maximum vpn clients',
            name='max_clients',
            get='max_clients',
            set='max_clients',
            type=ValueType.NUMBER,
            usage=_('''\
            A maximum nuber of clients to connect simultaneously''')
        )
        self.add_property(
            descr='Keepalive ping interval',
            name='keepalive_ping_interval',
            get='keepalive_ping_interval',
            set='keepalive_ping_interval',
            type=ValueType.NUMBER,
            usage=_('''\
            Ping interval of keepalive directive''')
        )
        self.add_property(
            descr='Keepalive peer down',
            name='keepalive_peer_down',
            get='keepalive_peer_down',
            set='keepalive_peer_down',
            type=ValueType.NUMBER,
            usage=_('''\
                Peer down argument of keepalive directive ''')
        )
        self.add_property(
            descr='Server Bridge',
            name='server_bridge',
            get='server_bridge',
            set='server_bridge',
            type=ValueType.BOOLEAN,
            usage=_('''\
            True/False - allows to enable bridge like behaviour
            on the OpenVPN interface''')
        )
        self.add_property(
            descr='Starting address of user defined ip range',
            name='server_bridge_range_begin',
            get='server_bridge_range_begin',
            set='server_bridge_range_begin',
            type=ValueType.STRING,
            usage=_('''\
            User defined ip range cannot interfere
            with bridge IP or existing local network''')
        )
        self.add_property(
            descr='Ending address of user defined ip range',
            name='server_bridge_range_end',
            get='server_bridge_range_end',
            set='server_bridge_range_end',
            type=ValueType.STRING,
            usage=_('''\
            User defined ip range cannot interfere
            with bridge IP or existing local network''')
        )
        self.add_property(
            descr='Netmask for user defined ip range',
            name='server_bridge_netmask',
            get='server_bridge_netmask',
            set='server_bridge_netmask',
            type=ValueType.STRING,
            usage=_('''\
            User defined ip range cannot interfere
            with bridge IP or existing local network''')
        )
        self.add_property(
            descr='Server Bridge extend',
            name='server_bridge_extended',
            get='server_bridge_extended',
            set='server_bridge_extended',
            type=ValueType.BOOLEAN,
            usage=_('''\
            True/False - allows to enable user defined ip range''')
        )
        self.add_property(
            descr='IP Address for VPN bridge ',
            name='server_bridge_ip',
            get='server_bridge_ip',
            set='server_bridge_ip',
            type=ValueType.STRING,
            usage=_('''\
             User defined bridge ip cannot interfere
             with user defined range or existing local network'''),
        )
        self.add_property(
            descr='OpenVPN port',
            name='port',
            get='port',
            set='port',
            type=ValueType.NUMBER,
            usage=_('''\
            Default: 1194'''),
        )
        self.add_property(
            descr='OpenVPN protocol',
            name='protocol',
            get='proto',
            set='proto',
            enum=['udp', 'tcp'],
            type=ValueType.STRING,
            usage=_('''\
            Protocol used by OpenVPN server - tcp/udp.
            Default:udp'''),
        )
        self.add_property(
            descr='OpenVPN compression',
            name='compression',
            get='comp_lzo',
            set='comp_lzo',
            type=ValueType.BOOLEAN,
            usage=_('''\
            Enable compression : True/False''')
        )
        self.add_property(
            descr='OpenVPN logging verbosity',
            name='verbosity',
            get='verb',
            set='verb',
            type=ValueType.NUMBER,
            usage=_('''\
            Logging verbosity range : 0-15'''),
        )
        self.add_property(
            descr='Auxiliary parameters',
            name='auxiliary',
            get='auxiliary',
            set='auxiliary',
            type=ValueType.STRING,
            usage=_('''\
             Optional, additional openvpn parameters not provided
             by other properties. Space delimited list of parameters
             enclosed between double quotes.'''),
        )
        self.add_property(
            descr='OpenVPN mode',
            name='mode',
            get='mode',
            set='mode',
            type=ValueType.STRING,
            usage=_('''\
            OpenVPN mode: pki or psk'''),
        )
        self.add_property(
            descr='PSK mode server ip address',
            name='psk_server_ip',
            get='psk_server_ip',
            set='psk_server_ip',
            type=ValueType.STRING,
            usage=_('''\
            PSK mode server ip address.'''),
        )
        self.add_property(
            descr='PSK mode client ip address',
            name='psk_remote_ip',
            get='psk_remote_ip',
            set='psk_remote_ip',
            type=ValueType.STRING,
            usage=_('''\
            PSK mode client ip address.'''),
        )
        self.add_property(
            descr='Certificate for OpenVPN server',
            name='certificate',
            get='cert',
            set='cert',
            type=ValueType.STRING,
            usage=_('''\
            PKI mode server certificate.'''),
        )
        self.add_property(
            descr='CA for OpenVPN server',
            name='certificate_authority',
            get='ca',
            set='ca',
            type=ValueType.STRING,
            usage=_('''\
            PKI mode server CA'''),
        )


@description("Allows to bridge openvpn interface to the main interface")
class OpenVPNBridgeCommand(Command):
    """
    Usage: bridge

    Allows to bridge openvpn interface to the main interface.
    This property is only allowed in pki mode.

    """
    def run(self, context, args, kwargs, opargs):
        vpn_confg = context.call_sync('service.openvpn.get_config')
        if vpn_confg['mode'] == 'psk':
            raise CommandException(_('Bridging to main interface is possible only in pki mode.'))

        tid = context.submit_task('service.openvpn.bridge')
        return TaskPromise(context, tid)


@description("Allows to generate OpenVPN cryptographic properties")
class OpenVPNCryptoCommand(Command):
    """
    Usage: generate_crypto key_type=[tls-auth-key or dh-parameters] key_length=[1024 or 2048] bits
    Example: generate_crypto key_type=tls-auth-key
             generate_crypto key_type=dh-parameters key_length=2048

    Creates OpenVPN cryptographic Values.
    dh-parameters can be either 1024 or 2048 bits long
    tls-auth-key is always generated as 2048 bit value
    """
    def run(self, context, args, kwargs, opargs):
        if len(kwargs) < 1:
            raise CommandException(_("generate_cryto requires more arguments, see 'help generate_cryto' for more information"))

        if not kwargs['key_type'] or kwargs['key_type'] not in ['dh-parameters', 'tls-auth-key']:
            raise CommandException(_("wrong arguments, see 'help generate_cryto' for more information"))

        if kwargs['key_type'] == 'dh-parameters' and kwargs['key_length'] not in [1024, 2048]:
            raise CommandException(_("wrong key_length value, see 'help generate_cryto' for more information"))

        tid = context.submit_task('service.openvpn.gen_key', kwargs['key_type'], kwargs.get('key_length'))
        return TaskPromise(context, tid)


@description("Provides corresponding OpenVPN client configuration")
class OpenVPNClientConfigCommand(Command):
    """
    Usage: provide_client_config

    Provides corresponding OpenVPN client configuration.
    It needs to be copied to the OpenVPN client machine.
    """
    def run(self, context, args, kwargs, opargs):
        vpn_client_confg = context.call_sync('service.openvpn.client_config.provide_config')
        return Sequence(vpn_client_confg)


@description("Provides OpenVPN static key")
class OpenVPNStaticKeyCommand(Command):
    """
    Usage: provide_static_key

    Provides static OpenVPN key that needs to be copied to the client machine
    """
    def run(self, context, args, kwargs, opargs):
        vpn_client_confg = context.call_sync('service.openvpn.get_config')
        return Sequence(vpn_client_confg['tls_auth'])



@description("Configure Domain Controller vm general settings")
class DomainControllerNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The DC service namespace allows to configure and manage DC virtual appliance.
    Please be advice that underneath this service is an virtual machine.
    """
    def __init__(self, name, context):
        super(DomainControllerNamespace, self).__init__(name, context)
        self.config_call = "service.dc.get_config"
        self.update_task = 'service.dc.update'
        self.name = name

        self.extra_commands.update({
            'get_url': DomainControllerUrlCommand(),
        })

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='DC vm volume',
            name='vm_volume',
            get='volume',
            set='volume',
            type=ValueType.STRING,
            usage=_('''\
            Volume name for the DC virtual machine appliance'''),
        )


@description("Provides the URL for the Domain Controller virtual appliance")
class DomainControllerUrlCommand(Command):
    """
    Usage: get_url

    Provides URL that allows to access the virtual Domain Controller appliance.
    """
    def run(self, context, args, kwargs, opargs):
        dc_url = context.call_sync('service.dc.provide_dc_url')
        return Sequence(dc_url)


@description("Configure and manage UPS service")
class UPSNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The UPS service namespace allows to configure and manage UPS service.
    """
    def __init__(self, name, context):
        super(UPSNamespace, self).__init__(name, context)
        self.config_call = "service.ups.get_config"
        self.update_task = 'service.ups.update'
        self.name = name

        self.extra_commands.update({
            'get_usb_devices': UPSDevicesCommand(),
        })

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Mode',
            name='mode',
            usage=_("""
            Can be set to MASTER or SLAVE."""),
            get='mode',
            type=ValueType.STRING,
            enum=['MASTER', 'SLAVE'],
        )
        self.add_property(
            descr='Identifier',
            name='identifier',
            usage=_("""
            Can be set to an alphanumeric description."""),
            get='identifier',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Remote Host',
            name='remote_host',
            usage=_(""""""),
            get='remote_host',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Remote Port',
            name='remote_port',
            usage=_(""""""),
            get='remote_port',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Driver',
            name='driver',
            usage=_(""""""),
            get='driver',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Driver Port',
            name='driver_port',
            usage=_(""""""),
            get='driver_port',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Description',
            name='description',
            usage=_("""
            Optional description. If it contains any spaces,
            enclose it between double quotes."""),
            get='description',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Shutdown Mode',
            name='shutdown_mode',
            usage=_("""
            Indicates when the UPS should shutdown. Can be set
            to BATT (UPS goes on battery) or LOWBATT (UPS
            reaches low battery)."""),
            get='shutdown_mode',
            type=ValueType.STRING,
            enum=['BATT', 'LOWBATT'],
        )
        self.add_property(
            descr='Shutdown Timer',
            name='shutdown_timer',
            usage=_("""
            Number in seconds. UPS will initiate shutdown this many
            seconds after UPS enters BATT 'shutdown_mode', unless power
            is restored"""),
            get='shutdown_timer',
            type=ValueType.NUMBER,
        )
        self.add_property(
            descr='Monitor User',
            name='monitor_user',
            usage=_(""""""),
            get='monitor_user',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Monitor Password',
            name='monitor_password',
            usage=_(""""""),
            get=None,
            set='monitor_password',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Monitor Remote',
            name='monitor_remote',
            usage=_("""
            Can be set to yes or no. When set to yes,
            the default is to listen on all interfaces and to use
            the known values upsmon for 'monitor_user' and
            fixmepass for 'monitor_password'."""),
            get='monitor_remote',
            type=ValueType.BOOLEAN,
        )
        self.add_property(
            descr='Auxiliary Users',
            name='auxiliary_users',
            usage=_(""""""),
            get='auxiliary_users',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Email Notify',
            name='email_notify',
            usage=_("""
            Can be set to yes or no. When set to yes,
            status updates will be emailed to
            'email_recipients'."""),
            get='email_notify',
            type=ValueType.BOOLEAN,
        )
        self.add_property(
            descr='Email Recipients',
            name='email_recipients',
            usage=_("""
            Space delimited list, enclosed between double
            quotes, of email addresses to receive status
            updates. This requires 'email_notify' to be set
            to yes."""),
            get='email_recipients',
            type=ValueType.SET,
        )
        self.add_property(
            descr='Email Subject',
            name='email_subject',
            usage=_("""
            Subject to use in status emails. Enclose between
            double quotes if it contains a space. Requires
            'email_notify' to be set to yes."""),
            get='email_subject',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Powerdown',
            name='powerdown',
            usage=_("""
            Can be set to yes or no. When set to yes,
            the UPS will also power off after shutting down the
            FreeNAS system"""),
            get='powerdown',
            type=ValueType.BOOLEAN,
        )
        self.add_property(
            descr='Auxiliary',
            name='auxiliary',
            usage=_("""
            Optional, additional ups.conf(5) parameters not provided
            by other properties. Space delimited list of parameters
            enclosed between double quotes."""),
            get='auxiliary',
            type=ValueType.STRING,
        )


@description("Provides a list of attached USB devices")
class UPSDevicesCommand(Command):
    """
    Usage: get_usb_devices

    Provides a list of attached USB devices.
    """
    def run(self, context, args, kwargs, opargs):
        usb_devices = context.call_sync('service.ups.get_usb_devices')

        return Table(usb_devices, [
            Table.Column('Device', 'device'),
            Table.Column('Description', 'description'),

        ])


@description("Configure and manage Consul service")
class ConsulNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The Consul service namespace allows to configure and manage Consul service.
    """
    def __init__(self, name, context):
        super(ConsulNamespace, self).__init__(name, context)
        self.config_call = "service.consul.get_config"
        self.update_task = 'service.consul.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Bind address',
            name='bind_address',
            get='bind_address',
            type=ValueType.STRING
        )
        self.add_property(
            descr='Server mode',
            name='server',
            get='server',
            type=ValueType.BOOLEAN,
        )
        self.add_property(
            descr='Datacenter',
            name='datacenter',
            get='datacenter',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Nodename',
            name='nodename',
            get='nodename',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Join addresses',
            name='join_addresses',
            get='start_join',
            type=ValueType.SET,
        )
        self.add_property(
            descr='WAN join addresses',
            name='wan_join_addresses',
            get='start_join_wan',
            type=ValueType.SET,
        )

@description("Configure and manage tftpd service")
class TFTPDNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The tftpd service namespace allows to configure and manage tftpd service.
    """
    def __init__(self, name, context):
        super(TFTPDNamespace, self).__init__(name, context)
        self.config_call = "service.tftpd.get_config"
        self.update_task = 'service.tftpd.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Port',
            name='port',
            usage=_("""Number representing the port for tftpd to
            listen on."""),
            get='port',
            type=ValueType.NUMBER,
        )
        self.add_property(
            descr='Path',
            name='path',
            usage=_(""" """),
            get='path',
            type=ValueType.STRING
        )
        self.add_property(
            descr='Allow New Files',
            name='alllow_new_files',
            usage=_("""
            Can be set to yes or no. When set to yes,
            network devices can save files on the system."""),
            get='alllow_new_files',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='UMASK',
            name='umask',
            usage=_("""
            Number representing the umask for newly created files, default
            is 022 (everyone can read, nobody can write). Some devices
            require a less strict umask."""),
            get='umask',
            type=ValueType.PERMISSIONS
        )
        self.add_property(
            descr='Auxiliary',
            name='auxiliary',
            usage=_("""
            Optional, additional tftpd(8) parameters not provided
            by other properties. Space delimited list of parameters
            enclosed between double quotes."""),
            get='auxiliary',
            type=ValueType.STRING
        )


@description("Configure and manage sshd service")
class SSHDNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The sshd service namespace allows to configure and manage sshd service.
    """
    def __init__(self, name, context):
        super(SSHDNamespace, self).__init__(name, context)
        self.config_call = "service.sshd.get_config"
        self.update_task = 'service.sshd.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='sftp log facility',
            name='sftp_log_facility',
            get='sftp_log_facility',
            type=ValueType.STRING
        )
        self.add_property(
            descr='Allow public key authentication',
            name='allow_pubkey_auth',
            usage=_("""
            Can be set to yes. If set to yes, properly
            configured key-based authentication for all users
            is possible."""),
            get='allow_pubkey_auth',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Allow GSSAPI authentication',
            name='allow_gssapi_auth',
            usage=_(""""""),
            get='allow_gssapi_auth',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Enable compression',
            name='compression',
            usage=_("""
            Can be set to yes or no. When set to yes,
            compression may reduce latency over slow networks."""),
            get='compression',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Allow password authentication',
            name='allow_password_auth',
            usage=_("""
            Can be set to yes or no. If set to yes,
            passoword logins are allowed."""),
            get='allow_password_auth',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Allow port forwarding',
            name='allow_port_forwarding',
            usage=_("""
            Can be set to yes or no. If set to yes, users can
            bypass firewall restrictions using SSH's port forwarding
            feature."""),
            get='allow_port_forwarding',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Permit root login',
            name='permit_root_login',
            usage=_("""
            Can be set to yes or no. Setting to yes is discouraged
            for security reasons."""),
            get='permit_root_login',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='sftp log level',
            name='sftp_log_level',
            get='sftp_log_level',
            type=ValueType.STRING
        )
        self.add_property(
            descr='Port',
            name='port',
            usage=_("""
            Numeric port to open for SSH connection requests."""),
            get='port',
            type=ValueType.NUMBER
        )

@description("Configure and manage ftp service")
class FTPNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The ftp service namespace allows to configure and manage ftp service.
    """
    def __init__(self, name, context):
        super(FTPNamespace, self).__init__(name, context)
        self.config_call = "service.ftp.get_config"
        self.update_task = 'service.ftp.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Idle timeout',
            name='timeout',
            usage=_("""
            Number representing the maximum client idle time, in
            seconds, before client is disconnected."""),
            get='timeout',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='root login',
            name='root_login',
            usage=_("""
            Can be set to yes or no and indicates whether or not
            root logins are allowed."""),
            get='root_login',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Path for anonymous login',
            name='anonymous_path',
            usage=_("""
            Full path to the root directory for anonymous FTP
            connections."""),
            get='anonymous_path',
            type=ValueType.STRING
        )
        self.add_property(
            descr='Only allow anonymous login',
            name='only_anonymous',
            usage=_("""
            Can be set to yes or no and indicates whether or not
            only anonymous logins are allowed."""),
            get='only_anonymous',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Only allow local user login',
            name='only_local',
            usage=_("""
            Can be set to yes or no. When set to yes,
            anonymous logins are not allowed."""),
            get='only_local',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Login message',
            name='display_login',
            usage=_("""
            Message displayed to local login users after authentication.
            It is not displayed to anonymous login users. Enclose the
            message between double quotes."""),
            get='display_login',
            type=ValueType.STRING
        )
        self.add_property(
            descr='File creation mask',
            name='filemask',
            get='filemask',
            type=ValueType.PERMISSIONS
        )
        self.add_property(
            descr='Directory creation mask',
            name='dirmask',
            get='dirmask',
            type=ValueType.PERMISSIONS
        )
        self.add_property(
            descr='Enable FXP protocol',
            name='fxp',
            get='fxp',
            usage=_("""
            Can be set to yes or no. When set to yes,
            it enables the File eXchange Protocol which is
            discouraged as it makes the server vulnerable to
            FTP bounce attacks."""),
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Automatic transfer resumption',
            name='resume',
            usage=_("""
            Can be set to yes or no. When set to yes,
            FTP clients can resume interrupted transfers."""),
            get='resume',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Chroot local users',
            name='chroot',
            usage=_("""
            Can be set to yes or no. When set to yes,
            local users are restricted to their own home
            directory except for users which are members of
            the wheel group."""),
            get='chroot',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Require identd authentication',
            name='ident',
            usage=_("""
            Can be set to yes or no. When set to yes,
            timeouts will occur if the identd service is not
            running on the client."""),
            get='ident',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Perform reverse DNS lookups',
            name='reverse_dns',
            usage=_("""
            Can be set to yes or no. When set to yes,
            the system will perform reverse DNS lookups on client
            IPs. This can cause long delays if reverse DNS is not
            configured."""),
            get='reverse_dns',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Masquerade address',
            name='masquerade_address',
            usage=_("""
            System's public IP address or hosname=Set this
            property if FTP clients can not connect through a
            NAT device."""),
            get='masquerade_address',
            type=ValueType.STRING
        )
        self.add_property(
            descr='Minimum passive ports',
            name='passive_ports_min',
            usage=_("""
            Numeric port number indicating the lowest port number
            available to FTP clients in PASV mode. Default of 0
            means any port above 1023."""),
            get='passive_ports_min',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='Maximum passive ports',
            name='passive_ports_max',
            usage=_("""
            Numeric port number indicating the highest port number
            available to FTP clients in PASV mode. Default of 0
            means any port above 1023."""),
            get='passive_ports_max',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='Local user upload bandwidth',
            name='local_up_bandwidth',
            usage=_("""
            Number representing the maximum upload bandwidth per local
            user in KB/s. Default of 0 means unlimited."""),
            get='local_up_bandwidth',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='Local user download bandwidth',
            name='local_down_bandwidth',
            usage=_("""
            Number representing the maximum download bandwidth per
            local user in KB/s. Default of 0 means unlimited."""),
            get='local_down_bandwidth',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='Anonymous upload bandwidth',
            name='anon_up_bandwidth',
            usage=_("""
            Number representing the maximum upload bandwidth per
            anonymous user in KB/s. Default of 0 means unlimited."""),
            get='anon_up_bandwidth',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='Anonymous download bandwidth',
            name='anon_down_bandwidth',
            usage=_("""
            Number representing the maximum download bandwidth per
            anonymous user in KB/s. Default of 0 means unlimited."""),
            get='anon_down_bandwidth',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='Enable TLS',
            name='tls',
            usage=_("""
            Can be set to yes or no. When set to yes, it
            enables encrypted connections and requires a certificate to
            be created or imported."""),
            get='tls',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='TLS Policy',
            name='tls_policy',
            usage=_("""
            The specified policy defines whether the control
            channel, data channel, both channels, or neither
            channel of an FTP session must occur over SSL/TLS.
            Valid values are ON, OFF, DATA, !DATA, AUTH, CTRL,
            CTRL+DATA, CTRL+!DATA, AUTH+DATA, or AUTH+!DATA."""),
            get='tls_policy',
            enum=[
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
            type=ValueType.STRING
        )
        self.add_property(
            descr='TLS Options',
            name='tls_options',
            usage=_("""
            The following options can be set:
            ALLOW_CLIENT_RENEGOTIATIONS, ALLOW_DOT_LOGIN,
            ALLOW_PER_USER, COMMONname=EQUIRED,
            ENABLE_DIAGNOSTICS, EXPORT_CERTIFICATE_DATA,
            NO_CERTIFICATE_REQUEST, NO_EMPTY_FRAGMENTS,
            NO_SESSION_REUSE_REQUIRED, STANDARD_ENV_VARS,
            DNSname=EQUIRED, IP_ADDRESS_REQUIRED. Separate
            mutiple options with a space and enclose between
            double quotes."""),
            get='tls_options',
            enum=[
                    'ALLOW_CLIENT_RENEGOTIATIONS',
                    'ALLOW_DOT_LOGIN',
                    'ALLOW_PER_USER',
                    'COMMONname=EQUIRED',
                    'ENABLE_DIAGNOSTICS',
                    'EXPORT_CERTIFICATE_DATA',
                    'NO_CERTIFICATE_REQUEST',
                    'NO_EMPTY_FRAGMENTS',
                    'NO_SESSION_REUSE_REQUIRED',
                    'STANDARD_ENV_VARS',
                    'DNSname=EQUIRED',
                    'IP_ADDRESS_REQUIRED',
            ],
            type=ValueType.SET
        )
        self.add_property(
            descr='TLS SSL Certificate',
            name='tls_ssl_certificate',
            usage=_("""
            The SSL certificate to be used for TLS FTP
            connections. Enclose the certificate between double
            quotes"""),
            get='tls_ssl_certificate',
            type=ValueType.STRING
        )
        self.add_property(
            descr='Auxiliary parameters',
            name='auxiliary',
            usage=_("""
            Optional, additional proftpd(8) parameters not provided
            by other properties. Space delimited list of parameters
            enclosed between double quotes."""),
            get='auxiliary',
            type=ValueType.STRING
        )

@description("Configure and manage afp service")
class AFPNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The afp service namespace allows to configure and manage afp service.
    """
    def __init__(self, name, context):
        super(AFPNamespace, self).__init__(name, context)
        self.config_call = "service.afp.get_config"
        self.update_task = 'service.afp.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Share Home Directory',
            name='homedir_enable',
            get='homedir_enable',
            usage= _("""
            Can be set to yes or no. When set to 'yes', user home
            directories located under 'homedir_path' will be available
            over AFP shares."""),
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Home Directory Path',
            name='homedir_path',
            get='homedir_path',
            usage= _("""
            Enclose the path to the volume or dataset which contains the
            home directories between double quotes."""),
            type=ValueType.STRING
        )
        self.add_property(
            descr='Home Directory Name',
            name='homedir_name',
            get='homedir_name',
            usage= _("""
            Optional setting which overrides default home folder name
            with the specified value."""),
            type=ValueType.STRING
        )
        self.add_property(
            descr='Auxiliary Parameters',
            name='auxiliary',
            get='auxiliary',
            usage= _("""
            Optional, additional afp.conf(5) parameters not provided
            by other properties. Space delimited list of parameters
            enclosed between double quotes."""),
            type=ValueType.STRING
        )
        self.add_property(
            descr='Connections limit',
            name='connections_limit',
            get='connections_limit',
            usage= _("""
            Maximum number of simultaneous connections."""),
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='Guest user',
            name='guest_user',
            get='guest_user',
            usage= _("""
            The specified user account must exist and have permissions to the
            volume or dataset being shared."""),
            type=ValueType.STRING
        )
        self.add_property(
            descr='Enable guest user',
            name='guest_enable',
            get='guest_enable',
            usage= _("""
            Can be set to yes or no. When set to yes, clients will not be
            prompted to authenticate before accessing AFP shares."""),
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Bind Addresses',
            name='bind_addresses',
            get='bind_addresses',
            usage= _("""
            IP address(es) to listen for FTP connections. Separate multiple
            IP addresses with a space and enclose between double quotes."""),
            list=True,
            type=ValueType.SET
        )
        self.add_property(
            descr='Database Path',
            name='dbpath',
            get='dbpath',
            usage= _("""
            Optional. Specify the path to store the CNID databases used by AFP,
            where the default is the root of the volume. The path must be
            writable and enclosed between double quotes."""),
            type=ValueType.STRING
        )


@description("Configure and manage smb service")
class SMBNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The smb service namespace allows to configure and manage smb service.
    """
    def __init__(self, name, context):
        super(SMBNamespace, self).__init__(name, context)
        self.config_call = "service.smb.get_config"
        self.update_task = 'service.smb.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='NetBIOS name',
            name='netbiosname',
            usage= _("""
            Must be different from the 'Workgroup'."""),
            get='netbiosname',
            type=ValueType.SET
        )
        self.add_property(
            descr='Workgroup',
            name='workgroup',
            usage= _("""
            Must match the Windows workgroupname=This setting is
            ignored if the Active Directory or LDAP service is
            running."""),
            get='workgroup'
        )
        self.add_property(
            descr='description',
            name='description',
            usage= _("""
            Optional. Enclose between double quotes if it contains
            a space."""),
            get='description',
        )
        self.add_property(
            descr='DOS Character Set',
            name='dos_charset',
            usage= _("""
            Must be different from the 'Workgroup'."""),
            enum=['CP437', 'CP850', 'CP852', 'CP866', 'CP932', 'CP949',
                     'CP950', 'CP1029', 'CP1251', 'ASCII'],
            get='dos_charset'
        )
        self.add_property(
            descr='UNIX Character Set',
            name='unix_charset',
            enum=['UTF-8', 'iso-8859-1', 'iso-8859-15', 'gb2312', 'EUC-JP', 'ASCII'],
            get='unix_charset'
        )
        self.add_property(
            descr='Log level',
            name='log_level',
            usage= _("""
            Can be set to NONE, MINIMUM, NORMAL, FULL, or DEBUG."""),
            get='log_level',
            enum=[ 'NONE', 'MINIMUM', 'NORMAL', 'FULL', 'DEBUG' ]
        )
        self.add_property(
            descr='Log in syslog',
            name='syslog',
            usage= _("""
            Can be set to yes or no. When set to yes,
            authentication failures are logged to /var/log/messages
            instead of the default of /var/log/samba4/log.smbd."""),
            get='syslog',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Local master',
            name='local_master',
            usage= _("""
            Can be set to yes or no. When set to yes, the system
            will participate in a browser election. Should be set
            to no when network contains an AD or LDAP server. Does
            not need to be set if Vista or Windows 7 machines are
            present."""),
            get='local_master',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Domain logons',
            name='domain_logons',
            usage= _("""
            Can be set to yes or no. Only set to yes when
            if need to provide the netlogin service for older
            Windows clients."""),
            get='domain_logons',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Time server',
            name='time_server',
            usage= _("""
            Can be set to yes or no and determines whether or not the
            system advertises itself as a time server to Windows
            clients. Do not set to yes if the network contains an AD
            or LDAP server."""),
            get='time_server',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Guest User',
            name='guest_user',
            usage= _("""
            The specified user account must exist and have permissions to the
            volume or dataset being shared."""),
            get='guest_user'
        )
        self.add_property(
            descr='File mask',
            name='filemask',
            get='filemask',
            type=ValueType.PERMISSIONS
        )
        self.add_property(
            descr='Directory mask',
            name='dirmask',
            get='dirmask',
            type=ValueType.PERMISSIONS
        )
        self.add_property(
            descr='Empty password logons',
            name='empty_password',
            usage= _("""
            Can be set to yes or no. If set to yes,
            users can just press Enter when prompted for a
            password. Requires that the usename=assword be the
            same as the Windows user account."""),
            get='empty_password',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='UNIX Extensions',
            name='unixext',
            usage= _("""
            Can be set to yes or no. If set to yes,
            non-Windows clients can access symbolic links
            and hard links. This property has no effect on Windows
            clients."""),
            get='unixext',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Zero Configuration',
            name='zeroconf',
            usage= _("""
            Can be set to yes or no. Set to yes if MAC
            clients will be connecting to the smb share."""),
            get='zeroconf',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Host lookup',
            name='hostlookup',
            usage= _("""
            Can be set to yes or no. If set to yes, you can
            specify hosname=rather than IP addresses in the
            hosts_allow or hosts_deny properties of a smb share.
            Set to no if you only use IP addresses as it saves
            the time of a host lookup."""),
            get='hostlookup',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Minimum Protocol',
            name='min_protocol',
            usage= _("""
            The minimum protocol version the server will support.
            Valid values, in order, are: CORE, COREPLUS, LANMAN1,
            LANMAN2, NT1, SMB2, SMB2_02, SMB2_10, SMB2_22,
            SMB2_24, SMB3,, or SMB3_00. The set value must be lower
            than the max_protocol."""),
            get='min_protocol',
        )
        self.add_property(
            descr='Maximum Protocol',
            name='max_protocol',
            usage= _("""
            The maximum protocol version the server will support.
            Valid values, in order, are: CORE, COREPLUS, LANMAN1,
            LANMAN2, NT1, SMB2, SMB2_02, SMB2_10, SMB2_22,
            SMB2_24, SMB3,, or SMB3_00. The set value must be higher
            than the min_protocol."""),
            get='max_protocol',
        )
        self.add_property(
            descr='Always Execute',
            name='execute_always',
            usage= _("""
            Can be set to yes or no. If set to yes, any user can
            execute a file, even if that user's permissions are
            not set to execute."""),
            get='execute_always',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Obey PAM Restrictions',
            name='obey_pam_restrictions',
            usage= _("""
            Can be set to yes or no. If set to no, cross-domain
            authentication is allowed so that users and groups can
            be managed on another forest, and permissions can be
            delegated from AD users and groups to domain admins on
            another forest."""),
            get='obey_pam_restrictions',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Bind addresses',
            name='bind_addresses',
            usage= _("""
            Space delimited list of IP address(es) that the smb service
            should listen on. Enclose the list between double quotes.
            If not set, the service will listen on all available
            addresses."""),
            get='bind_addresses',
            list=True,
            type=ValueType.SET
        )
        self.add_property(
            descr='Auxiliary',
            name='auxiliary',
            usage= _("""
            Optional, additional smb.conf parameters. Separate multiple
            parameters by a space and enclose them between double quotes."""),
            get='auxiliary'
        )


@description("Configure and manage dyndns service")
class DynDnsNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The dyndns service namespace allows to configure and manage dyndns service.
    """
    def __init__(self, name, context):
        super(DynDnsNamespace, self).__init__(name, context)
        self.config_call = "service.dyndns.get_config"
        self.update_task = 'service.dyndns.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='DynDNS Provider',
            name='provider',
            usage= _("""
            Name of the DDNS provider."""),
            get='provider'
        )
        self.add_property(
            descr='IP Server',
            name='ipserver',
            usage= _("""
            Can be used to specify the hosname=nd port of the IP
            check server."""),
            get='ipserver'
        )
        self.add_property(
            descr='Domains',
            name='domains',
            get='domains',
            usage= _("""
            Your system's fully qualified domainname in the format
            "youname=yndns.org"."""),
            type=ValueType.SET
        )
        self.add_property(
            descr='Usename',
            name='usename',
            usage= _("""
            Usename=sed to logon to the provider and update the
            record."""),
            get='usename',        
            )
        self.add_property(
            descr='Password',
            name='password',
            usage= _("""
            Password used to logon to the provider and update the
            record."""),
            get=None,
            set='password'
        )
        self.add_property(
            descr='Update period',
            name='update_period',
            usage= _("""
            Number representing how often the IP is checked in seconds."""),
            get='update_period',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='Force update period',
            name='force_update_period',
            usage= _("""
            Number representing how often the IP should be updated, even it
            has not changed, in seconds."""),
            get='force_update_period',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='Auxiliary',
            name='auxiliary',
            usage= _("""
            Optional, additional parameters passed to the provider during
            record update. Separate multiple parameters by a space and
            enclose them between double quotes."""),
            get='auxiliary'
        )


@description("Configure and manage ipfs service")
class IPFSNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The ipfs service namespace allows to configure and ipfs service.
    """
    def __init__(self, name, context):
        super(IPFSNamespace, self).__init__(name, context)
        self.config_call = "service.ipfs.get_config"
        self.update_task = 'service.ipfs.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='IPFS PATH',
            name='path',
            get='path'
        )
        self.add_property(
            descr='IPFS WebUI toggle',
            name='webui',
            get='webui',
            usage= _(
                "Flag to enable/disable ipfs webui over at http(s)://freenas_machine_ip/ipfsui."
            ),
            type=ValueType.BOOLEAN
        )    

@description("Configure and manage ipfs service")
class IPFSNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The ipfs service namespace allows to configure and manage dyndns service.
    """
    def __init__(self, name, context):
        super(IPFSNamespace, self).__init__(name, context)
        self.config_call = "service.ipfs.get_config"
        self.update_task = 'service.ipfs.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )


@description("Configure and manage nfs service")
class NFSNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The nfs service namespace allows to configure and manage nfs service.
    """
    def __init__(self, name, context):
        super(NFSNamespace, self).__init__(name, context)
        self.config_call = "service.nfs.get_config"
        self.update_task = 'service.nfs.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Number of servers',
            name='servers',
            usage= _("""
            When setting this number, do not exceed the number
            of CPUS shown from running shell "sysctl -n
            kern.smp.cpus"."""),
            get='servers',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='Enable UDP',
            name='udp',
            usage= _("""
            Can be set to yes or no. When set to yes,
            older NFS clients that require UDP are supported."""),
            get='udp',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Enable NFSv4',
            name='v4',
            usage= _("""
            Can be set to yes or no. When set to yes,
            both NFSv3 and NFSv4 are supported."""),
            get='v4',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Enable NFSv4 Kerberos',
            name='v4_kerberos',
            usage= _("""
            Can be set to yes or no. When set to yes,
            NFS shares will fail if the Kerberos ticket is
            unavailable."""),
            get='v4_kerberos',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Bind addresses',
            name='bind_addresses',
            usage= _("""
            Space delimited list of IP addresses to listen for NFS
            requests, placed between double quotes. Unless specified,
            NFS will listen on all available addresses."""),
            get='bind_addresses',
            type=ValueType.SET
        )
        self.add_property(
            descr='Mountd port',
            name='mountd_port',
            usage= _("""
            Number representing the port for mountd(8) to bind to."""),
            get='mountd_port',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='RPC statd port',
            name='rpcstatd_port',
            usage= _("""
            Number representing the port for rpcstatd(8) to bind to."""),
            get='rpcstatd_port',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='RPC Lockd port',
            name='rpclockd_port',
            usage= _("""
            Number representing the port for rpclockd(8) to bind to."""),
            get='rpclockd_port',
            type=ValueType.NUMBER
        )


@description("Configure and manage iscsi service")
class ISCSINamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The iscsi service namespace allows to configure and manage iscsi service.
    """
    def __init__(self, name, context):
        super(ISCSINamespace, self).__init__(name, context)
        self.config_call = "service.iscsi.get_config"
        self.update_task = 'service.iscsi.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Base name',
            name='base_name',
            usage= _("""
            Name in IQN format as described by RFC 3721. Enclose
            name between double quotes."""),
            get='base_name',
            type=ValueType.STRING
        )
        self.add_property(
            descr='Pool space threshold',
            name='pool_space_threshold',
            usage= _("""
            Number representing the percentage of free space that should
            remain in the pool. When this percentage is reached, the
            system will issue an alert, but only if zvols are used."""),
            get='pool_space_threshold',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='ISNS servers',
            name='isns_servers',
            usage= _("""
            Space delimited list of hosname=or IP addresses of ISNS server(s)
            to register the system's iSCSI taget=nd portals with. Enclose
            the list between double quotes."""),
            get='isns_servers',
            type=ValueType.SET
        )
        
@description("Configure and manage iscsi service")
class ISCSINamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The iscsi service namespace allows to configure and manage iscsi service.
    """
    def __init__(self, name, context):
        super(ISCSINamespace, self).__init__(name, context)
        self.config_call = "service.iscsi.get_config"
        self.update_task = 'service.iscsi.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Base name',
            name='base_name',
            usage= _("""
            Name in IQN format as described by RFC 3721. Enclose
            name between double quotes."""),
            get='base_name',
            type=ValueType.STRING
        )
        self.add_property(
            descr='Pool space threshold',
            name='pool_space_threshold',
            usage= _("""
            Number representing the percentage of free space that should
            remain in the pool. When this percentage is reached, the
            system will issue an alert, but only if zvols are used."""),
            get='pool_space_threshold',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='ISNS servers',
            name='isns_servers',
            usage= _("""
            Space delimited list of hosname=or IP addresses of ISNS server(s)
            to register the system's iSCSI taget=nd portals with. Enclose
            the list between double quotes."""),
            get='isns_servers',
            type=ValueType.SET
        )


@description("Configure and manage lldp service")
class LLDPNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The lldp service namespace allows to configure and manage lldp service.
    """
    def __init__(self, name, context):
        super(LLDPNamespace, self).__init__(name, context)
        self.config_call = "service.lldp.get_config"
        self.update_task = 'service.lldp.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Save description',
            name='save_description',
            usage= _("""
            Can be set to yes or no. When set to yes,
            receive mode is enabled and received peer information
            is saved in interfacedescr=ions."""),
            get='save_description',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Country code',
            name='country_code',
            usage= _("""
            Required for LLDP location support. Input 2 letter ISO 3166
            country code."""),
            get='country_code',
            type=ValueType.STRING
        )
        self.add_property(
            descr='Location',
            name='location',
            usage= _("""
            Optional, physical location of the host enclosed within
            double quotes."""),
            get='location',
            type=ValueType.STRING
        )


@description("Configure and manage snmp service")
class SNMPNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The snmp service namespace allows to configure and manage snmp service.
    """
    def __init__(self, name, context):
        super(SNMPNamespace, self).__init__(name, context)
        self.config_call = "service.snmp.get_config"
        self.update_task = 'service.snmp.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Location',
            name='location',
            usage= _("""
            Optional, physical location of the host enclosed within
            double quotes."""),
            get='location',
            type=ValueType.STRING
        )
        self.add_property(
            descr='Contact',
            name='contact',
            usage= _("""
            Optional, email address of administrator enclosed within
            double quotes."""),
            get='contact',
            type=ValueType.STRING
        )
        self.add_property(
            descr='Community',
            name='community',
            usage= _("""Value of a community string"""),
            get='community',
            type=ValueType.STRING
        )
        self.add_property(
            descr='Enable SNMPv3',
            name='v3',
            usage= _("""
            Can be set to yes or no. When set to yes,
            support for SNMP version 3 is enabled."""),
            get='v3',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='SNMPv3 Username',
            name='v3_username',
            usage= _("""
            Only set if 'v3' is set. Specify the usename=o
            register with the SNMPv3 service."""),
            get='v3_username',
            type=ValueType.STRING
        )
        self.add_property(
            descr='SNMPv3 Password',
            name='v3_password',
            usage= _("""
            Only set if 'v3' is set. Specify a password of
            at least 8 characters."""),
            set='v3_password',
            get=None,
            list=False,
            type=ValueType.STRING
        )
        self.add_property(
            descr='SNMPv3 Auth Type',
            name='v3_auth_type',
            usage= _("""
            Only set if 'v3' is set. Specify either
            MD5 or SHA."""),
            get='v3_auth_type',
            enum=['MD5', 'SHA'],
            type=ValueType.STRING
        )
        self.add_property(
            descr='SNMPv3 Privacy Protocol',
            name='v3_privacy_protocol',
            usage= _("""
            Only set if 'v3' is set. Specify either
            AES or DES."""),
            get='v3_privacy_protocol',
            enum=['AES', 'DES'],
            type=ValueType.STRING
        )
        self.add_property(
            descr='SNMPv3 Privacy Passphrase',
            name='v3_privacy_passphrase',
            usage= _("""
            Only set if 'v3' is set and 'v3_password' is not
            set. Specify a passphrase of at least 8
            characters."""),
            get=None,
            set='v3_privacy_passphrase',
            list=False,
            type=ValueType.STRING
        )
        self.add_property(
            descr='Auxiliary parameters',
            name='auxiliary',
            usage= _("""
            Optional, additional snmpd.conf(5) parameters. Separate
            multiple parameters by a space and enclose them between
            double quotes."""),
            get='auxiliary',
            type=ValueType.STRING
        )


@description("Configure and manage smartd service")
class SMARTDNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The smartd service namespace allows to configure and manage smartd service.
    """
    def __init__(self, name, context):
        super(SMARTDNamespace, self).__init__(name, context)
        self.config_call = "service.smartd.get_config"
        self.update_task = 'service.smartd.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Interval',
            name='interval',
            usage= _("""
            Number representing how often, in minutes, to wake
            up smartd to check to see if any tests have been
            configured to run."""),
            get='interval',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='Power mode',
            name='power_mode',
            usage= _("""
            Configured tests are not performed if the system enters
            the specified power mode. Values are: NEVER, SLEEP,
            STANDBY, or IDLE."""),
            get='power_mode',
            enum=[
                'NEVER',
                'SLEEP',
                'STANDBY',
                'IDLE',
            ],
            type=ValueType.STRING
        )
        self.add_property(
            descr='Temperature difference',
            name='temp_difference',
            usage= _("""
            Default of 0 disables this check. Otherwise, reports if
            the temperature of a drive has changed by the specified
            number of degrees Celsius since last report."""),
            get='temp_difference',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='Temperature informational',
            name='temp_informational',
            usage= _("""
            By default, this check is disabled. If set, will log
            an entry of LOG_INFO if the temperature is higher than
            the specified number of degrees Celsius since the last
            report."""),
            get='temp_informational',
            type=ValueType.NUMBER
        )
        self.add_property(
            descr='Temperature critical',
            name='temp_critical',
            usage= _("""
            By default, this check is disabled. If set, will log
            an entry of LOG_CRIT and will send an email if the
            temperature is higher than the specified number of degrees
            Celsius since the last report."""),
            get='temp_critical',
            type=ValueType.NUMBER
        )


@description("Configure and manage webdav service")
class WebDAVNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The webdav service namespace allows to configure and manage webdav service.
    """
    def __init__(self, name, context):
        super(WebDAVNamespace, self).__init__(name, context)
        self.config_call = "service.webdav.get_config"
        self.update_task = 'service.webdav.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Protocol',
            name='protocol',
            usage= _("""
            Set to HTTP (connection always unencrypted), HTTPS
            (connection always encrypted), or HTTP+HTTPS (both
            types of connections allowed)."""),
            get='protocol',
            type=ValueType.ARRAY,
            enum=[['HTTP'],
                      ['HTTPS'],
                      ['HTTP', 'HTTPS']
            ],
            list=True,
        )
        self.add_property(
            descr='Webdav SSL Certificate',
            name='certificate',
            usage= _("""The SSL certificate to be used for Secure WebDAV
            connections. Enclose the certificate between double quotes"""),
            get='certificate',
            type=ValueType.STRING,
            list=True
        )
        self.add_property(
            descr='HTTP Port',
            name='http_port',
            usage= _("""
            Only set if 'protocol' is HTTP or HTTP+HTTPS. Numeric
            port to be used for unencrypted connections. Do not set a
            port number already being used by another service."""),
            get='http_port',
            type=ValueType.NUMBER,
        )
        self.add_property(
            descr='HTTPS Port',
            name='https_port',
            usage= _("""
            Only set if 'protocol' is HTTPS or HTTP+HTTPS. Numeric
            port to be used for encrypted connections. Do not set a
            port number already being used by another service."""),
            get='https_port',
            type=ValueType.NUMBER,
        )
        self.add_property(
            descr='Password',
            name='password',
            usage= _("""
            Set a secure password to be used by the webdav user."""),
            get='password',
            set='password',
            type=ValueType.PASSWORD
        )
        self.add_property(
            descr='Authentication mode',
            name='authentication',
            usage= _("""
            Determines whether or not authentication occurs over
            an encrypted channel. Set either BASIC (unencrypted)
            or DIGEST (encrypted)."""),
            get='authentication',
            enum=[
                'BASIC',
                'DIGEST',
            ],
            type=ValueType.STRING
        )

@description("Configure and manage rsyncd service")
class RsyncdNamespace(ServiceManageMixIn, ConfigNamespace):
    """
    The rsyncd service namespace allows to configure and manage rsyncd service.
    """
    def __init__(self, name, context):
        super(RsyncdNamespace, self).__init__(name, context)
        self.config_call = "service.rsyncd.get_config"
        self.update_task = 'service.rsyncd.update'
        self.name = name

        self.add_property(
            descr='Enabled',
            name='enable',
            get='enable',
            list=True,
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='Port',
            name='port',
            usage= _("""Number representing the port for rsyncd to
            listen on."""),
            get='port',
            type=ValueType.NUMBER,
        )
        self.add_property(
            descr='Auxiliary',
            name='auxiliary',
            usage= _("""
                Optional, additional rsyncd.conf(5) parameters not provided
                by other properties. Space delimited list of parameters
                enclosed between double quotes.
            """),
            get='auxiliary',
            type=ValueType.STRING,
        )


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
        self.service_name = parent.name


    @property
    def description(self):
        return '{0}s service'.format(self.action.title())

    def run(self, context, args, kwargs, opargs):
        service_id = context.entity_subscribers['service'].query(
            ('name', '=', self.service_name), single=True, select='id'
        )
        tid = context.submit_task(
            'service.manage',
            service_id,
            self.action,
            callback=lambda s, t: post_save(self.parent, s, t)
        )

        return TaskPromise(context, tid)


@description("Displays service status")
class ServiceStatusCommand(Command):
    """
    Usage: status
    """
    def __init__(self, parent):
        self.parent = parent
        self.service_name = parent.name

    def run(self, context, args, kwargs, opargs):
        service = context.entity_subscribers['service'].query(
            ('name', '=', self.service_name), single=True
        )
        return Table([service], [
            Table.Column('Sate', 'state')

        ])


@description("Configure and manage services")
class ServicesNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The service namespace is used to configure, start, and
    stop system services.
    """
    def __init__(self, name, context):
        super(ServicesNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'service'
        self.save_key_name = 'id'
        self.extra_query_params = [('builtin', '=', False)]
        self.primary_key = self.get_mapping('name')
        self.allow_edit = False
        self.allow_create = False

        self.add_property(
            descr='Service name',
            name='name',
            get='name',
            usage=_("""\
            Name of the service. Read-only value assigned by
            the operating system."""),
            set=None,
            list=True
        )

        self.add_property(
            descr='State',
            name='state',
            get='state',
            usage=_("""\
            Indicates whether the service is RUNNING or STOPPED.
            Read-only value assigned by the operating system."""),
            set=None,
            list=True
        )

        self.add_property(
            descr='Process ID',
            name='pid',
            get='pid',
            usage=_("""\
            Process ID of the RUNNING service. Read-only value assigned
            by the operating system."""),
            set=None,
            list=True
        )

    def namespaces(self):
        return [
            OpenVPNNamespace('openvpn', self.context),
            DomainControllerNamespace('dc', self.context),
            UPSNamespace('ups', self.context),
            ConsulNamespace('consul', self.context),
            TFTPDNamespace('tftpd', self.context),
            SSHDNamespace('sshd', self.context),
            FTPNamespace('ftp', self.context),
            AFPNamespace('afp', self.context),
            SMBNamespace('smb', self.context),
            DynDnsNamespace('dyndns', self.context),
            IPFSNamespace('ipfs', self.context),
            NFSNamespace('nfs', self.context),
            ISCSINamespace('iscsi', self.context),
            LLDPNamespace('lldp', self.context),
            SNMPNamespace('snmp', self.context),
            SMARTDNamespace('smartd', self.context),
            WebDAVNamespace('webdav', self.context),
            RsyncdNamespace('rsyncd', self.context),

        ]

def _init(context):
    context.attach_namespace('/', ServicesNamespace('service-new', context))
    context.map_tasks('service.*', ServicesNamespace)
