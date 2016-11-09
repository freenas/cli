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

from freenas.cli.output import Sequence, ValueType
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
            'reload': ServiceManageCommand(self, 'reload')
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


@description("Provides the URL for the Domain Controller virtual appliance")
class DomainControllerUrlCommand(Command):
    """
    Usage: get_url

    Provides URL that allows to access the virtual Domain Controller appliance.
    """
    def run(self, context, args, kwargs, opargs):
        dc_url = context.call_sync('service.dc.provide_dc_url')
        return Sequence(dc_url)


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

        self.add_property(
            descr='Mode',
            name='mode',
            usage= _("""
            Can be set to MASTER or SLAVE."""),
            get='mode',
            type=ValueType.STRING,
            enum=['MASTER', 'SLAVE'],
        )
        self.add_property(
            descr='Identifier',
            name='identifier',
            usage= _("""
            Can be set to an alphanumericdescr=ion."""),
            get='identifier',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Remote Host',
            name='remote_host',
            usage= _(""""""),
            get='remote_host',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Remote Port',
            name='remote_port',
            usage= _(""""""),
            get='remote_port',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Driver',
            name='driver',
            usage= _(""""""),
            get='driver',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Driver Port',
            name='driver_port',
            usage= _(""""""),
            get='driver_port',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Description',
            name='description',
            usage= _("""
            Optional description. If it contains any spaces,
            enclose it between double quotes."""),
            get='description',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Shutdown Mode',
            name='shutdown_mode',
            usage= _("""
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
            usage= _("""
            Number in seconds. UPS will initiate shutdown this many
            seconds after UPS enters BATT 'shutdown_mode', unless power
            is restored"""),
            get='shutdown_timer',
            type=ValueType.NUMBER,
        )
        self.add_property(
            descr='Monitor User',
            name='monitor_user',
            usage= _(""""""),
            get='monitor_user',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Monitor Password',
            name='monitor_password',
            usage= _(""""""),
            get=None,
            set='monitor_password',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Monitor Remote',
            name='monitor_remote',
            usage= _("""
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
            usage= _(""""""),
            get='auxiliary_users',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Email Notify',
            name='email_notify',
            usage= _("""
            Can be set to yes or no. When set to yes,
            status updates will be emailed to
            'email_recipients'."""),
            get='email_notify',
            type=ValueType.BOOLEAN,
        )
        self.add_property(
            descr='Email Recipients',
            name='email_recipients',
            usage= _("""
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
            usage= _("""
            Subject to use in status emails. Enclose between
            double quotes if it contains a space. Requires
            'email_notify' to be set to yes."""),
            get='email_subject',
            type=ValueType.STRING,
        )
        self.add_property(
            descr='Powerdown',
            name='powerdown',
            usage= _("""
            Can be set to yes or no. When set to yes,
            the UPS will also power off after shutting down the
            FreeNAS system"""),
            get='powerdown',
            type=ValueType.BOOLEAN,
        )
        self.add_property(
            descr='Auxiliary',
            name='auxiliary',
            usage= _("""
            Optional, additional ups.conf(5) parameters not provided
            by other properties. Space delimited list of parameters
            enclosed between double quotes."""),
            get='auxiliary',
            type=ValueType.STRING,
        )


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
            descr='Port',
            name='port',
            usage= _("""Number representing the port for tftpd to
            listen on."""),
            get='port',
            type=ValueType.NUMBER,
        )
        self.add_property(
            descr='Path',
            name='path',
            usage= _(""" """),
            get='path',
            type=ValueType.STRING
        )
        self.add_property(
            descr='Allow New Files',
            name='alllow_new_files',
            usage= _("""
            Can be set to yes or no. When set to yes,
            network devices can save files on the system."""),
            get='alllow_new_files',
            type=ValueType.BOOLEAN
        )
        self.add_property(
            descr='UMASK',
            name='umask',
            usage= _("""
            Number representing the umask for newly created files, default
            is 022 (everyone can read, nobody can write). Some devices
            require a less strict umask."""),
            get='umask',
            type=ValueType.PERMISSIONS
        )
        self.add_property(
            descr='Auxiliary',
            name='auxiliary',
            usage= _("""
            Optional, additional tftpd(8) parameters not provided
            by other properties. Space delimited list of parameters
            enclosed between double quotes."""),
            get='auxiliary',
            type=ValueType.STRING
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
        self.update_task = 'service.update'
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

        ]

def _init(context):
    context.attach_namespace('/', ServicesNamespace('service-new', context))
