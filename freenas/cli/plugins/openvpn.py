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
    Namespace, EntityNamespace, Command, RpcBasedLoadMixin,
    CommandException, description, ConfigNamespace
)

from freenas.cli.output import Sequence, ValueType

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Configure OpenVPN general settings")
class OpenVPNConfigNamespace(ConfigNamespace):
    """
    The OpenVPN config namespace provides commands for listing,
    and managing OpenVPN settings.
    It also provides ability to generate corresponding client config and
    static key.
    """
    def __init__(self, name, context):
        super(OpenVPNConfigNamespace, self).__init__(name, context)
        self.config_call = "service.openvpn.get_readable_config"
        self.update_task = 'service.openvpn.update'

        self.extra_commands = {
            'bridge': OpenVPNBridgeCommand(),
            'generate_crypto': OpenVPNCryptoCommand(),
            'provide_client_config': OpenVPNClientConfigCommand(),
            'provide_static_key': OpenVPNStaticKeyCommand()
        }

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

        context.submit_task('service.openvpn.bridge')

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

        context.submit_task('service.openvpn.gen_key', kwargs['key_type'], kwargs.get('key_length'))

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


@description("Manages OpenVPN service")
class OpenVPNamespace(RpcBasedLoadMixin, EntityNamespace):
    """
    This namespace provides commands for managing the OpenVPN service.
    Go into 'config' namespace for configuration related actions.
    """
    def __init__(self, name, context):
        super(OpenVPNamespace, self).__init__(name, context)

        self.extra_query_params = [('name', '=', 'openvpn')]
        self.query_call = 'service.query'
        self.primary_key = self.get_mapping('name')

        self.allow_create = False
        self.allow_edit = False

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

        self.extra_commands = {
            'start': OpenVPNManageCommand('start'),
            'stop': OpenVPNManageCommand('stop'),
            'reload': OpenVPNManageCommand('reload'),
            'restart': OpenVPNManageCommand('restart')
        }

    def namespaces(self):
        return [OpenVPNConfigNamespace('config', self.context)]

@description("Start/stop/restart/reload a service")
class OpenVPNManageCommand(Command):
    """
    Usage: start, stop, restart, reload
    start - starts a service
    stop - stops a service
    restart - restarts a service
    reload - gracefully restarts a service
    """
    def __init__(self, action):
        self.action = action

    @property
    def description(self):
        return '{0}s service'.format(self.action.title())

    def run(self, context, args, kwargs, opargs):
        self.service_id = context.entity_subscribers['service'].query(('name', '=', 'openvpn'),
                                                                      single=True, select='id')
        context.submit_task(
            'service.manage',
            self.service_id,
            self.action
            )


def _init(context):
    context.attach_namespace('/', OpenVPNamespace('openvpn', context))
