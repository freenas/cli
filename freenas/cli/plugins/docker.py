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
    Namespace, EntityNamespace, Command, EntitySubscriberBasedLoadMixin,
    TaskBasedSaveMixin, CommandException, description, ConfigNamespace, RpcBasedLoadMixin
)
from freenas.cli.output import ValueType, Table, Sequence, read_value
from freenas.cli.utils import (
    TaskPromise, post_save, EntityPromise, get_item_stub, objname2id, objid2name, set_name, check_name,
    get_related, set_related
)
from freenas.utils import query as q
from freenas.cli.complete import NullComplete, EntitySubscriberComplete, EnumComplete
from freenas.cli.console import Console
from freenas.utils import first_or_default
from freenas.cli.plugins.vm import StartVMCommand, StopVMCommand, RebootVMCommand, ConsoleCommand, KillVMCommand


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


DOCKER_PRESET_2_PROPERTY_MAP = {
    'autostart': 'autostart',
    'bridge.dhcp': 'dhcp',
    'capabilities_add': 'capabilities_add',
    'capabilities_drop': 'capabilities_drop',
    'command': 'command',
    'expose_ports': 'expose_ports',
    'interactive': 'interactive',
    'ports': 'port',
    'primary_network_mode': 'primary_network_mode',
    'privileged': 'privileged',
}


docker_names_pattern = '^[a-zA-Z0-9]+[a-zA-Z0-9._-]*'


@description("View information about Docker hosts")
class DockerHostNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    """
    The docker host namespace provides commands for listing data
    about Docker hosts available in the system.
    """
    def __init__(self, name, context):
        super(DockerHostNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'docker.host'
        self.primary_key_name = 'name'
        self.create_task = 'docker.host.create'
        self.update_task = 'docker.host.update'
        self.delete_task = 'docker.host.delete'
        self.required_props = ['name', 'datastore']

        self.add_property(
            descr='VM name',
            name='name',
            get='name',
            list=True,
            usage=_('Name of Virtual Machine instance hosting a Docker service.')
        )

        self.add_property(
            descr='State',
            name='state',
            get='state',
            set=None,
            usersetable=False,
            list=True,
            usage=_('State of a Docker host service. Can be UP or DOWN.')
        )

        self.add_property(
            descr='Datastore',
            name='datastore',
            get=lambda o: get_related(self.context, 'vm.datastore', o, 'target'),
            set=lambda o, v: set_related(self.context, 'vm.datastore', o, 'target', v),
            createsetable=True,
            usersetable=False,
            complete=EntitySubscriberComplete('datastore=', 'vm.datastore', lambda i: i['name']),
            usage=_("The datastore on which the Docker host VM is stored")
        )

        self.add_property(
            descr='Memory size (MB)',
            name='memsize',
            get=lambda o: q.get(o, 'config.memsize') * 1024 * 1024,
            set=lambda o, v: q.set(o, 'config.memsize', int(v / 1024 / 1024)),
            list=True,
            type=ValueType.SIZE,
            usage=_("Size of the Memory allocated to the Docker host VM")
        )

        self.add_property(
            descr='CPU cores',
            name='cores',
            get='config.ncpus',
            list=True,
            type=ValueType.NUMBER,
            usage=_("Number of cpu cores assigned to the Docker host VM")
        )

        self.add_property(
            descr='Operating system',
            name='os',
            get='status.os',
            set=None,
            usersetable=False,
            list=False,
            usage=_('Name of the operating system hosting a Docker service.')
        )

        self.add_property(
            descr='Docker unique ID',
            name='docker_unique_id',
            get='status.unique_id',
            set=None,
            usersetable=False,
            list=False,
            usage=_('Unique ID of a Docker host.')
        )

        self.primary_key = self.get_mapping('name')

        self.entity_commands = lambda this: {
            'start': StartVMCommand(this),
            'stop': StopVMCommand(this),
            'kill': KillVMCommand(this),
            'reboot': RebootVMCommand(this),
            'console': ConsoleCommand(this)
        }

        self.entity_namespaces = lambda this: [
            DockerNetworkNamespace('network', self.context, this)
        ]


@description("Configure and manage Docker host networks")
class DockerNetworkNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    """
    The docker network namespace provides commands for listing,
    creating, and managing networks on selected docker host.
    """
    def __init__(self, name, context, parent):
        super(DockerNetworkNamespace, self).__init__(name, context)
        self.parent = parent
        self.entity_subscriber_name = 'docker.network'
        self.create_task = 'docker.network.create'
        self.update_task = 'docker.network.update'
        self.delete_task = 'docker.network.delete'
        self.extra_query_params = [('host', '=', self.parent.entity.get('id'))]
        self.primary_key_name = 'name'
        self.required_props = ['name']
        self.skeleton_entity = {
            'host': self.parent.entity.get('id'),
            'driver': 'bridge'
        }

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> <property>=<value>

            Examples:
                create with-my-subnet subnet="10.20.4.0/24" gateway=10.20.4.1 driver=bridge
                create docker-selects-subnet driver=bridge
                create create-and-connect containers=mycontainer1,mycontainer2

            Creates a Docker network. If subnet and gateway properties are not specified
            the values will be selected by the docker engine.
            The driver property defaults to 'bridge'

            For a list of properties, see 'help properties'.""")

        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Deletes the specified Docker container.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all Docker containers. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")

        self.add_property(
            descr='Host',
            name='host',
            get=self.parent.entity.get('name'),
            createsetable=False,
            usersetable=False,
            list=False,
            usage=_('''\
            Name of Docker host instance owning network instance.
            Docker host name equals to name of Virtual Machine
            hosting Docker service.''')
        )

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            set=lambda o, v: set_name(o, 'name', v, docker_names_pattern),
            list=True,
            usage=_('Name of a network.')
        )

        self.add_property(
            descr='Driver',
            name='driver',
            get='driver',
            usersetable=False,
            list=True,
            usage=_('Type of a docker network driver. Supported values : "bridge"'),
            enum=['bridge']
        )

        self.add_property(
            descr='Subnet',
            name='subnet',
            get='subnet',
            list=True,
            usage=_("""\
            The subnet of the network in CIDR format. Specify the value between quotes.
            If left unspecified it will be selected by the docker engine
            """)
        )

        self.add_property(
            descr='Gateway',
            name='gateway',
            get='gateway',
            usage=_("""\
            IPv4 address of the network's default gateway.
            If left unspecified it will be selected by the docker engine
            """),
            list=True
        )

        self.add_property(
            descr='Containers',
            name='containers',
            get=lambda o: [objid2name(self.context, 'docker.container', id) for id in o.get('containers')],
            set=self.set_containers,
            usage=_("""\
            List of containers connected to the network.
            """),
            complete=EntitySubscriberComplete(
                name='containers=',
                datasource='docker.container',
                mapper=lambda c: q.get(c, 'names.0'),
                filter=[('host', '=', self.parent.entity.get('id'))]
            ),
            list=True,
            type=ValueType.ARRAY
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = self.get_entity_commands

    def set_containers(self, o, v):
        o['containers'] = [objname2id(self.context, 'docker.container', name) for name in read_value(v, ValueType.SET)]

    def get_entity_commands(self, this):
        this.load()
        commands = {
            'connect': DockerNetworkConnectCommand(this),
            'disconnect': DockerNetworkDisconnectCommand(this)
        }

        return commands


@description("Connect containers to a network")
class DockerNetworkConnectCommand(Command):
    """
    Usage: connect containers=<container1>,<container2>...

    Example:
        / docker network mynetwork connect containers=mycontainer
        / docker network mynetwork connect containers=mycontainer,mycontainer2

    Connects containers to a network.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not kwargs.get('containers'):
            raise CommandException('Please specify containers to connect to the network')
        tid = context.submit_task(
            'docker.network.connect',
            [objname2id(context, 'docker.container', c) for c in read_value(kwargs.get('containers'), ValueType.SET)],
            self.parent.entity['id']
        )
        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            EntitySubscriberComplete(
                name='containers=',
                datasource='docker.container',
                mapper=lambda c: q.get(c, 'names.0'),
                filter=[('host', '=', self.parent.entity.get('host'))]
            )
        ]


@description("Disconnect containers from a network")
class DockerNetworkDisconnectCommand(Command):
    """
    Usage: disconnect containers=<container1>,<container2>

    Example:
        / docker network mynetwork disconnect containers=mycontainer
        / docker network mynetwork disconnect containers=mycontainer,mycontainer2

    Disconnects containers from a network.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not kwargs.get('containers'):
            raise CommandException('Please specify containers to disconnect from the network')
        tid = context.submit_task(
            'docker.network.disconnect',
            [objname2id(context, 'docker.container', c) for c in read_value(kwargs.get('containers'), ValueType.SET)],
            self.parent.entity['id']
        )
        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            EntitySubscriberComplete(
                name='containers=',
                datasource='docker.container',
                mapper=lambda c: q.get(c, 'names.0'),
                filter=[('host', '=', self.parent.entity.get('host'))]
            )
        ]


@description("Configure and manage Docker containers")
class DockerContainerNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    """
    The docker container namespace provides commands for listing,
    creating, and managing Docker container.
    """
    def __init__(self, name, context):
        super(DockerContainerNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'docker.container'
        self.create_task = 'docker.container.create'
        self.update_task = 'docker.container.update'
        self.delete_task = 'docker.container.delete'
        self.primary_key_name = 'names.0'
        self.required_props = ['name', 'image']
        self.skeleton_entity = {
            'command': []
        }

        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Deletes the specified Docker container.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all Docker containers. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")

        def get_ports(o):
            return {'{0}/{1}'.format(i['container_port'], i['protocol']): str(i['host_port']) for i in o['ports']}

        def set_ports(o, p):
            ports = []
            for k, v in p.items():
                protocol = 'TCP'
                if '/' in k:
                    container_port, protocol = k.split('/', 1)
                    protocol = protocol.upper()
                else:
                    container_port = k

                ports.append({
                    'container_port': int(container_port),
                    'host_port': int(v),
                    'protocol': protocol
                })

            o['ports'] = ports

        def get_volumes(o, ro):
            return {i['container_path']: i['host_path'] for i in o['volumes'] if i['readonly'] == ro}

        def set_volumes(o, vol, ro):
            volumes = []
            for k, v in vol.items():
                volumes.append({
                    'container_path': k,
                    'host_path': v,
                    'readonly': ro
                })

            o['volumes'] = volumes

        self.add_property(
            descr='Name',
            name='name',
            get='names.0',
            list=True,
            usage=_('Name of a container instance.')
        )

        self.add_property(
            descr='Running',
            name='running',
            get='running',
            set=None,
            usersetable=False,
            type=ValueType.BOOLEAN,
            list=True,
            usage=_('State of a container returned by a Docker service.')
        )

        self.add_property(
            descr='Health',
            name='health',
            get='health',
            set=None,
            usersetable=False,
            usage=_('State of a health status of a container.')
        )

        self.add_property(
            descr='Image name',
            name='image',
            get='image',
            list=True,
            complete=EntitySubscriberComplete('image=', 'docker.image', lambda i: q.get(i, 'names.0')),
            strict=False,
            usage=_('Name of container image used to create an instance of a container.')
        )

        self.add_property(
            descr='Command',
            name='command',
            get='command',
            list=False,
            type=ValueType.ARRAY,
            usage=_('''\
            Command being run on a container (like /bin/sh).
            Can be a single string or a list of strings.''')
        )

        self.add_property(
            descr='Environment',
            name='environment',
            get='environment',
            list=False,
            type=ValueType.ARRAY,
            usage=_('''\
            Array of strings formed as KEY=VALUE.
            These are being converted to environment variables
            visible to a running container instance.''')
        )

        self.add_property(
            descr='Web UI URL',
            name='web_ui_url',
            get='web_ui_url',
            set=None,
            usersetable=False,
            list=True,
        )

        self.add_property(
            descr='Container host name',
            name='hostname',
            get='hostname',
            set=None,
            list=False,
            usage=_('''\
            Used to set host name of a container - like my_ubuntu_container.
            If not set explicitly it defaults in most cases
            to generating a random string as a container's host name.''')
        )

        self.add_property(
            descr='Host',
            name='host',
            get=lambda o: objid2name(context, 'docker.host', o['host']),
            set=lambda o, v: q.set(o, 'host', objname2id(context, 'docker.host', v)),
            list=True,
            complete=EntitySubscriberComplete('host=', 'docker.host', lambda d: d['name']),
            usage=_('''\
            Name of Docker host instance owning container instance.
            Docker host name equals to name of Virtual Machine
            hosting Docker service.''')
        )

        self.add_property(
            descr='Ports',
            name='ports',
            get=get_ports,
            set=set_ports,
            list=False,
            type=ValueType.DICT,
            usage=_('''\
            Array of strings used for defining network ports forwarding.
            Each of values should be formatted like:
            <container_port_number>/<tcp/udp>=<freenas_port_number>
            Ports are always being forwarded to a default FreeNAS box's
            network interface.''')
        )

        self.add_property(
            descr='Expose ports',
            name='expose_ports',
            get='expose_ports',
            list=True,
            type=ValueType.BOOLEAN,
            usage=_('''\
            Property defining whether or not ports which are defined in `ports`
            should be actually forwarded to FreeNAS (host machine).''')
        )

        self.add_property(
            descr='Autostart container',
            name='autostart',
            get='autostart',
            list=False,
            type=ValueType.BOOLEAN,
            usage=_('''\
            Defines if a container should be started automatically
            when a Docker host related to it goes UP''')
        )

        self.add_property(
            descr='Privileged container',
            name='privileged',
            get='privileged',
            list=False,
            type=ValueType.BOOLEAN,
            usage=_('''\
            Defines if a container should started in priveleged mode.''')
        )

        self.add_property(
            descr='Interactive',
            name='interactive',
            get='interactive',
            list=False,
            type=ValueType.BOOLEAN,
            usage=_('''\
            Defines if container's standard input should act
            like it is open even if no console is attached to a container.
            Useful to keep alive a process (command) being run on a container
            which immediately exits when there is no standard input
            opened to it (i.e. /bin/bash or any other shell).''')
        )

        self.add_property(
            descr='Volumes',
            name='volumes',
            get=lambda o: get_volumes(o, False),
            set=lambda o, v: set_volumes(o, v, False),
            list=False,
            type=ValueType.DICT,
            usage=_('''\
            List of strings formatted like:
            <container_path>=<freenas_path>
            Defines which of FreeNAS paths should be exposed to a container.''')
        )

        self.add_property(
            descr='Readonly Volumes',
            name='ro_volumes',
            get=lambda o: get_volumes(o, True),
            set=lambda o, v: set_volumes(o, v, True),
            list=False,
            type=ValueType.DICT,
            usage=_('''\
            List of strings formatted like:
            <container_path>=<freenas_path>
            Defines which of FreeNAS paths should be exposed to a container.''')
        )

        self.add_property(
            descr='Capabilities Added',
            name='capabilities_add',
            get='capabilities_add',
            list=False,
            type=ValueType.SET,
            usage=_('''\
            List of Linux capabilities added to the
            capabilities of docker container.''')
        )

        self.add_property(
            descr='Capabilities Dropped',
            name='capabilities_drop',
            get='capabilities_drop',
            list=False,
            type=ValueType.SET,
            usage=_('''\
            List of Linux capabilities removed from the
            capabilities of docker container.''')
        )

        self.add_property(
            descr='Version',
            name='version',
            get='version',
            list=False,
            type=ValueType.NUMBER,
            usage=_('''\
            Version of container image read from FreeNAS metadata''')
        )

        self.add_property(
            descr='DHCP Enabled',
            name='dhcp',
            get='bridge.dhcp',
            list=False,
            type=ValueType.BOOLEAN,
            condition=lambda o: q.get(o, 'primary_network_mode') == 'BRIDGED',
            usage=_('''\
            Defines if container will have it's IP address acquired via DHCP.'''),
        )

        self.add_property(
            descr='Container address',
            name='address',
            get='bridge.address',
            list=False,
            condition=lambda o: q.get(o, 'primary_network_mode') == 'BRIDGED',
            usage=_('''\
            IP address of a container when it's set to a bridged mode.'''),
        )

        self.add_property(
            descr='Container Mac address',
            name='macaddress',
            get='bridge.macaddress',
            list=False,
            condition=lambda o: q.get(o, 'primary_network_mode') == 'BRIDGED',
            usage=_('''\
            IP address of a container when it's set to a bridged mode.'''),
        )

        self.add_property(
            descr='Primary Network Mode',
            name='primary_network_mode',
            get='primary_network_mode',
            list=True,
            type=ValueType.STRING,
            enum=['NAT', 'BRIDGED', 'HOST', 'NONE'],
            usage=_('''\
            Defines mode of container's primary networking.
            NAT means that container is connected to default docker bridge network "docker0" and external
            access is achieved via NAT. In this mode container can be connected to user-defined internal networks.
            BRIDGED means that container's primary interface is bridged to default box interface and either
            static IP is set or DHCP option is selected. In this mode container can be connected to
            user-defined internal networks
            HOST means that container is using the docker host network stack.
            NONE means that container's networking is disabled.'''),
        )

        self.add_property(
            descr='Docker networks',
            name='networks',
            get=lambda o: [objid2name(self.context, 'docker.network', id) for id in o.get('networks')],
            set=self.set_networks,
            usersetable=False,
            usage=_("""\
            List of docker networks the container is connected to.
            """),
            list=False,
            type=ValueType.ARRAY
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = self.get_entity_commands

    def set_networks(self, o, v):
        o['networks'] = [objname2id(self.context, 'docker.network', name) for name in read_value(v, ValueType.SET)]

        self.primary_key = self.get_mapping('name')
        self.entity_commands = self.get_entity_commands

    def commands(self):
        ret = super(DockerContainerNamespace, self).commands()
        ret['create'] = DockerContainerCreateCommand(self)
        return ret

    def get_entity_commands(self, this):
        this.load()
        commands = {
            'start': DockerContainerStartCommand(this),
            'stop': DockerContainerStopCommand(this),
            'restart': DockerContainerRestartCommand(this),
            'console': DockerContainerConsoleCommand(this),
            'exec': DockerContainerExecConsoleCommand(this),
            'readme': DockerContainerReadmeCommand(this),
            'clone': DockerContainerCloneCommand(this),
            'commit': DockerContainerCommitCommand(this)
        }
        if this.entity and not this.entity.get('interactive'):
            commands['logs'] = DockerContainerLogsCommand(this)

        return commands


@description("Configure and manage Docker container images")
class DockerImageNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The docker image namespace provides commands for listing,
    creating, and managing Docker container images.
    """
    default_images = []

    def __init__(self, name, context):
        super(DockerImageNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'docker.image'
        self.primary_key_name = 'names.0'
        self.allow_create = False
        self.allow_edit = False
        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Deletes the specified Docker container image.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all Docker container images. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")

        def get_hosts(o):
            return list(context.entity_subscribers['docker.host'].query(('id', 'in', o['hosts']), select='name')) or []

        self.add_property(
            descr='Name',
            name='name',
            get='names.0',
            set=None,
            usersetable=False,
            list=True,
            usage=_('Name of a Docker container image')
        )

        self.add_property(
            descr='Parent image',
            name='parent',
            get=lambda o: context.entity_subscribers['docker.image'].query(('id', '=', o['parent']), select='names.0'),
            set=None,
            usersetable=False,
            list=True,
            usage=_('Name of the source image.')
        )

        self.add_property(
            descr='Size',
            name='size',
            get='size',
            set=None,
            usersetable=False,
            list=True,
            type=ValueType.SIZE,
            usage=_('Size of a Docker container image on a Docker host.')
        )

        self.add_property(
            descr='Created at',
            name='created_at',
            get='created_at',
            set=None,
            usersetable=False,
            list=True,
            usage=_('Creation time of a Docker container image.')
        )

        self.add_property(
            descr='Host',
            name='host',
            get=get_hosts,
            set=None,
            usersetable=False,
            list=False,
            type=ValueType.SET,
            usage=_('Names of a Docker hosts storing this container image.')
        )

        self.add_property(
            descr='Version',
            name='version',
            get='presets.version',
            usersetable=False,
            list=True,
            type=ValueType.NUMBER,
            usage=_('''\
            Version of container image read from FreeNAS metadata''')
        )

        self.primary_key = self.get_mapping('name')
        self.extra_commands = {
            'pull': DockerImagePullCommand(self),
            'search': DockerImageSearchCommand(),
            'readme': DockerImageReadmeCommand(),
            'flush_cache': DockerImageFlushCacheCommand()
        }

        self.entity_commands = lambda this: {
            'delete': DockerImageDeleteCommand(this)
        }


@description("Configure Docker general settings")
class DockerConfigNamespace(ConfigNamespace):
    """
    The docker config namespace provides commands for listing,
    and managing Docker general settings.
    """
    def __init__(self, name, context):
        super(DockerConfigNamespace, self).__init__(name, context)
        self.config_call = "docker.config.get_config"
        self.update_task = 'docker.config.update'

        self.add_property(
            descr='Default Docker host',
            name='default_host',
            get=lambda o: objid2name(context, 'docker.host', o['default_host']),
            set=lambda o, v: q.set(o, 'default_host', objname2id(context, 'docker.host', v)),
            complete=EntitySubscriberComplete('default_host=', 'docker.host', lambda d: d['name']),
            usage=_('''\
            Name of a Docker host selected by default for any
            container or container image operations
            when there is no `host` parameter set explicitly in a command.''')
        )

        self.add_property(
            descr='Forward Docker remote API to host',
            name='api_forwarding',
            get=lambda o: objid2name(context, 'docker.host', o['api_forwarding']),
            set=lambda o, v: q.set(o, 'api_forwarding', objname2id(context, 'docker.host', v)),
            complete=EntitySubscriberComplete('api_forwarding=', 'docker.host', lambda d: d['name']),
            usage=_('''\
            Defines which (if any) Docker host - Virtual Machine hosting
            a Docker service - should expose their standard remote HTTP API
            at FreeNAS's default network interface.''')
        )

        self.add_property(
            descr='Docker remote API forwarding',
            name='api_forwarding_enable',
            get='api_forwarding_enable',
            set='api_forwarding_enable',
            type=ValueType.BOOLEAN,
            usage=_('''\
            Used for enabling/disabling Docker HTTP API forwarding
            to FreeNAS's default network interface.''')
        )


@description("Configure and manage Docker container collections")
class DockerCollectionNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    """
    The docker collection namespace provides commands for listing,
    creating, and managing Docker container collections.
    """
    def __init__(self, name, context):
        super(DockerCollectionNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'docker.collection'
        self.create_task = 'docker.collection.create'
        self.update_task = 'docker.collection.update'
        self.delete_task = 'docker.collection.delete'
        self.primary_key_name = 'name'
        self.required_props = ['name', 'collection']
        self.skeleton_entity = {
            'match_expr': ''
        }

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> collection=<collection> <refine>=<refine>

            Examples: create my_collection collection=freenas
                      create my_collection collection=freenas refine=plex

            Creates a known Docker container collection to simplify DockerHub browsing.

            Collection is going to contain DockerHub images of 'collection='
            DockerHub user which names do contain 'refine=' parameter value in their name.

            For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set name=new_collection_name
                      set collection=linuxserver
                      set refine=s3

            Sets a Docker collection property. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Deletes the specified Docker collection.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all Docker collections. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            list=True,
            usage=_("The name of the collection.")
        )

        self.add_property(
            descr='DockerHub collection name',
            name='collection',
            get='collection',
            list=True,
            usage=_("The name of theDockerHub collection.")
        )

        self.add_property(
            descr='Search refinement string',
            name='refine',
            get='match_expr',
            list=False,
            usage=_("""
            Collection contains images from a selected DockerHub collection
            which do contain 'refine' parameter value in their name.""")
        )

        self.primary_key = self.get_mapping('name')

        self.entity_namespaces = lambda this: [
            CollectionImagesNamespace('image', self.context, this)
        ]


@description("Container collection images operations")
class CollectionImagesNamespace(RpcBasedLoadMixin, EntityNamespace):
    """
    The docker collection image namespace provides commands for listing,
    creating, and managing images which belong to a specific
    Docker container collection.
    """
    def __init__(self, name, context, parent):
        super(CollectionImagesNamespace, self).__init__(name, context)
        self.query_call = 'docker.collection.full_query'
        self.primary_key_name = 'name'
        self.allow_create = False
        self.allow_edit = False
        self.call_timeout = 300
        self.parent = parent

        if self.parent and self.parent.entity:
            self.extra_query_params = [
                ('id', '=', self.parent.entity.get('id'))
            ]
            self.extra_query_options = {
                'select': 'images',
                'single': True
            }

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            usersetable=False,
            list=True,
            usage=_("Name of the image")
        )

        self.add_property(
            descr='Description',
            name='description',
            get='description',
            usersetable=False,
            list=True,
            usage=_("Description of the image")
        )

        self.add_property(
            descr='Pull count',
            name='pull_count',
            get='pull_count',
            usersetable=False,
            list=True,
            type=ValueType.NUMBER,
            usage=_("Pull count of the image")
        )

        self.add_property(
            descr='Star count',
            name='star_count',
            get='star_count',
            usersetable=False,
            list=True,
            type=ValueType.NUMBER,
            usage=_("Star count of the image")
        )

        self.add_property(
            descr='Version',
            name='version',
            get='presets.version',
            usersetable=False,
            list=True,
            usage=_('''\
            Version of container image read from FreeNAS metadata''')
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = lambda this: {
            'pull': CollectionImagePullCommand(this)
        }

    def query(self, params, options):
        result = super(CollectionImagesNamespace, self).query([], {})

        return q.query(result, *params, **options)

    def get_one(self, name):
        return self.query(
            [(self.primary_key_name, '=', name)],
            {'single': True}
        )


@description("Pull container image from Docker Hub to Docker host")
class DockerImagePullCommand(Command):
    """
    Usage: pull <name> host=<host>

    Example: pull debian:latest
             pull debian:latest host=my_docker_host
             pull name=debian:latest host=my_docker_host

    Pulls container image from Docker Hub to selected Docker host.
    If no host is specified, then default Docker host is selected.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args and not kwargs:
            raise CommandException(_("Pull requires more arguments, see 'help pull' for more information"))
        if len(args) > 1:
            raise CommandException(_("Wrong syntax for pull, see 'help create' for more information"))

        if len(args) == 1:
            if 'name' in kwargs:
                raise CommandException(_("Both implicit and explicit 'name' parameters are specified."))
            else:
                kwargs['name'] = args.pop(0)

        if 'name' not in kwargs:
            raise CommandException(_('Please specify image name'))
        else:
            name = kwargs.pop('name')

        host = kwargs.get('host')
        hostid = None
        if host:
            hostid = context.entity_subscribers['docker.host'].query(('name', '=', host), single=True, select='id')

        ns = get_item_stub(context, self.parent, name)

        tid = context.submit_task('docker.image.pull', name, hostid, callback=lambda s, t: post_save(ns, s, t))

        return EntityPromise(context, tid, ns)

    def complete(self, context, **kwargs):
        return [
            EnumComplete('name=', q.query(DockerImageNamespace.default_images, select='name')),
            EntitySubscriberComplete('host=', 'docker.host', lambda d: d['name'])
        ]


@description("Pull collection container image from Docker Hub to Docker host")
class CollectionImagePullCommand(Command):
    """
    Usage: pull host=<host>

    Example: pull
             pull host=my_docker_host

    Pulls container image from Docker Hub to selected Docker host.
    If no host is specified, then default Docker host is selected.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        host = kwargs.get('host')
        hostid = None
        name = self.parent.entity['name']
        if host:
            hostid = context.entity_subscribers['docker.host'].query(('name', '=', host), single=True, select='id')

        tid = context.submit_task('docker.image.pull', name, hostid)

        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            EntitySubscriberComplete('host=', 'docker.host', lambda d: d['name'])
        ]


@description("Search Docker Hub for an image matching a given name")
class DockerImageSearchCommand(Command):
    """
    Usage: search <name>

    Example: search plex
             search name=plex

    Searches Docker Hub for an image matching a given name.
    Specified name can be just a part of a full image name.
    """
    def run(self, context, args, kwargs, opargs):
        if len(args) != 1 and 'name' not in kwargs:
            raise CommandException("Please specify fragment of the image name")

        name = kwargs.get('name') or args[0]

        return Table(context.call_sync('docker.image.search', name), [
            Table.Column('Name', 'name', width=30),
            Table.Column('Description', 'description')
        ])

    def complete(self, context, **kwargs):
        return [
            NullComplete('name=')
        ]


@description("Get full description of container image")
class DockerImageReadmeCommand(Command):
    """
    Usage: readme <name>

    Example: readme plex
             readme name=plex

    Returns full description of a given container image.
    """
    def run(self, context, args, kwargs, opargs):
        if len(args) != 1 and 'name' not in kwargs:
            raise CommandException("Please specify the image name")

        name = kwargs.get('name') or args[0]

        readme = context.call_sync('docker.image.readme', name)
        if readme:
            return Sequence(readme)
        else:
            return Sequence("Image {0} readme does not exist".format(args[0]))

    def complete(self, context, **kwargs):
        return [
            NullComplete('name=')
        ]


@description("Delete all cached Docker container images")
class DockerImageFlushCacheCommand(Command):
    """
    Usage: flush_cache

    Example: flush_cache

    Deletes all cached Docker container images.
    """
    def run(self, context, args, kwargs, opargs):
        tid = context.submit_task('docker.image.flush')

        return TaskPromise(context, tid)


@description("Delete cached container image")
class DockerImageDeleteCommand(Command):
    """
    Usage: delete host=<host>

    Example: delete
             delete host=docker_host_0

    Deletes cached container image.
    When no host is specified image is going to be deleted
    from all available Docker hosts at once.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        host = kwargs.get('host', None)
        name = q.get(self.parent.entity, 'names.0')
        id = q.get(self.parent.entity, 'id')

        if host:
            host = context.call_sync('docker.host.query', [('name', '=', host)], {'single': True, 'select': 'id'})
            if not host:
                raise CommandException(_('Docker host {0} not found'.format(kwargs.get('host'))))

            if host not in self.parent.entity['hosts']:
                raise CommandException(_('Image {0} does not exist on {1}'.format(
                    name,
                    kwargs.get('host')
                )))

        tid = context.submit_task(
            'docker.image.delete',
            id,
            host,
            callback=lambda s, t: post_save(self.parent, s, t)
        )

        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            EntitySubscriberComplete('host=', 'docker.host', lambda i: q.get(i, 'name'))
        ]


class DockerContainerCreateCommand(Command):
    """
    Usage: create <name> image=<image> command=<command> hostname=<hostname>
                  host=<host> expose_ports=<expose_ports>
                  autostart=<autostart> interactive=<interactive>
                  ...
                  <ENVIRONMENT_NAME>=<VALUE>
                  port:<CONTAINER_PORT>/<PROTOCOL>=<HOST_PORT>
                  volume:<CONTAINER_PATH>=<HOST_PATH>

    Examples: create interactive-container image=ubuntu:latest interactive=yes
              create autostarting-container image=freenas/busybox
                     host=docker_host_0 hostname=busybox primary_network_mode=NAT
                     autostart=yes
              create exposed-ports image=dockerhub_image_name
                     port:8443/TCP=8443 port:1234/UDP=12356
                     expose_ports=yes
              create volume-mapping image=dockerhub_image_name
                     volume:/container/directory=/mnt/my_pool/container_data
              create bridged-and-static-ip image=ubuntu:latest interactive=yes
                     primary_network_mode=BRIDGED bridge_address=10.20.0.180
              create bridged-and-dhcp image=ubuntu:latest interactive=yes
                     primary_network_mode=BRIDGED dhcp=yes
              create bridged-and-dhcp-macaddr image=ubuntu:latest interactive=yes
                     primary_network_mode=BRIDGED dhcp=yes bridge_macaddress=01:02:03:04:05:06
              create create-and-connect image=dockerhub_image_name host=docker_host_0
                     networks=mynetwork1,mynetwork2
              create with-host-networking-stack image=freenas/busybox primary_network_mode=HOST
              create disabled-networking image=freenas/busybox primary_network_mode=NONE


    Environment variables are provided as any number of uppercase KEY=VALUE
    elements.
    The same applies to sequences of port:<CONTAINER_PORT>/<PROTOCOL>=<HOST_PORT>
    and volume:<CONTAINER_PATH>=<HOST_PATH> elements.

    Creates a Docker container. For a list of properties, see 'help properties'.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not kwargs.get('name') and not args:
            raise CommandException('name is a required property')

        if not kwargs.get('image'):
            raise CommandException('image is a required property')

        name = kwargs.get('name') or args[0]

        check_name(name, docker_names_pattern)

        image = context.entity_subscribers['docker.image'].query(('names.0', 'in', kwargs['image']), single=True)
        if not image:
            image = q.query(DockerImageNamespace.default_images, ('name', '=', kwargs['image']), single=True)

        env = ['{0}={1}'.format(k, v) for k, v in kwargs.items() if k.isupper()]
        presets = image.get('presets') or {} if image else {}
        ports = presets.get('ports', [])
        volumes = presets.get('static_volumes', [])
        command = read_value(kwargs.get('command', presets.get('command')), ValueType.ARRAY)

        for k, v in kwargs.items():
            if k.startswith('volume:'):
                _, container_path = k.split(':', maxsplit=1)
                volumes.append({
                    'container_path': container_path,
                    'host_path': v,
                    'readonly': False
                })

            if k.startswith('ro_volume:'):
                _, container_path = k.split(':', maxsplit=1)
                volumes.append({
                    'container_path': container_path,
                    'host_path': v,
                    'readonly': True
                })

            if k.startswith('port:'):
                _, portspec = k.split(':', maxsplit=1)
                port, protocol = portspec.split('/', maxsplit=1)
                protocol = protocol.upper()
                try:
                    port = int(port)
                except ValueError:
                    continue

                if protocol not in ('TCP', 'UDP'):
                    continue

                mapping = first_or_default(lambda m: m['container_port'] == port and m['protocol'] == protocol, ports)
                if mapping:
                    mapping['host_port'] = v
                    continue

                ports.append({
                    'container_port': port,
                    'host_port': v,
                    'protocol': protocol
                })

        host = kwargs.get('host')
        if host:
            host_id = context.entity_subscribers['docker.host'].query(('name', '=', host), single=True, select='id')
            if host_id:
                host = host_id

        create_args = {
            'names': [name],
            'image': kwargs['image'],
            'host': host,
            'hostname': kwargs.get('hostname'),
            'command': command,
            'environment': env,
            'volumes': volumes,
            'ports': ports,
            'autostart': read_value(kwargs.get('autostart', 'no'), ValueType.BOOLEAN),
            'expose_ports': read_value(
                kwargs.get('expose_ports', q.get(presets, 'expose_ports', False)),
                ValueType.BOOLEAN
            ),
            'interactive': read_value(
                kwargs.get('interactive', q.get(presets, 'interactive', False)),
                ValueType.BOOLEAN
            ),
            'bridge': {
                'dhcp': read_value(
                    kwargs.get('dhcp', q.get(presets, 'bridge.dhcp', False)),
                    ValueType.BOOLEAN
                ),
                'address': kwargs.get('bridge_address'),
                'macaddress': kwargs.get('bridge_macaddress')
            },
            'capabilities_add': read_value(
                kwargs.get('capabilities_add', q.get(presets, 'capabilities_add', [])),
                ValueType.SET
            ),
            'capabilities_drop': read_value(
                kwargs.get('capabilities_drop', q.get(presets, 'capabilities_drop', [])),
                ValueType.SET
            ),
            'privileged': read_value(
                kwargs.get('privileged', q.get(presets, 'privileged', False)),
                ValueType.BOOLEAN
            ),
            'primary_network_mode': read_value(
                kwargs.get('primary_network_mode', q.get(presets, 'primary_network_mode', '')),
                ValueType.STRING
            ),
            'networks': [
                objname2id(context, 'docker.network', name) for name in read_value(
                    kwargs.get('networks'),
                    ValueType.SET
                )
            ]
        }

        for p in presets.get('immutable', []):
            if q.get(create_args, p) != q.get(presets, p):
                raise CommandException(
                    'Cannot change property: {0}. It was defined as immutable in the Dockerfile'.format(DOCKER_PRESET_2_PROPERTY_MAP[p])
                )

        bridge = create_args.get('bridge')
        bridge_enabled = create_args.get('primary_network_mode') == 'BRIDGED'
        if bridge_enabled and not (bridge.get('dhcp') or bridge.get('address')):
            raise CommandException('Either dhcp or static address must be selected for bridged container')

        if not bridge_enabled and (bridge.get('dhcp') or bridge.get('address') or bridge.get('macaddress')):
            raise CommandException('Cannot set the "dhcp","address" and "macaddress" bridge properties when '
                                   'bridge is not enabled')

        ns = get_item_stub(context, self.parent, name)

        tid = context.submit_task(self.parent.create_task, create_args, callback=lambda s, t: post_save(ns, s, t))
        return EntityPromise(context, tid, ns)

    def complete(self, context, **kwargs):
        props = []
        immutable = []
        presets = {}
        name = q.get(kwargs, 'kwargs.image')
        host_name = q.get(kwargs, 'kwargs.host')
        host_id = context.entity_subscribers['docker.host'].query(('name', '=', host_name), single=True, select='id')
        if name:
            image = context.entity_subscribers['docker.image'].query(('names.0', 'in', name), single=True)
            if not image:
                image = q.query(DockerImageNamespace.default_images, ('name', '=', name), single=True)

            if image and image['presets']:
                presets = image['presets']
                immutable = [DOCKER_PRESET_2_PROPERTY_MAP[v] for v in presets.get('immutable')]
                caps_add = ','.join(presets['capabilities_add'])
                caps_drop = ','.join(presets['capabilities_drop'])
                command = ','.join(presets['command'])
                props += [NullComplete('{id}='.format(**i)) for i in presets['settings']]
                props += [NullComplete(('ro_' if v.get('readonly') else '') + 'volume:{container_path}='.format(**v)) for v in presets['volumes']]
                if 'port' not in immutable:
                    props += [NullComplete('port:{container_port}/{protocol}='.format(**v)) for v in presets['ports']]
                if caps_add and 'capabilities_add' not in immutable:
                    props += [NullComplete('capabilities_add={0}'.format(caps_add))]
                if caps_drop and 'capabilities_drop' not in immutable:
                    props += [NullComplete('capabilities_drop={0}'.format(caps_drop))]
                if command and 'command' not in immutable:
                    props += [NullComplete('command={0}'.format(command))]

        available_images = q.query(DockerImageNamespace.default_images, select='name')
        available_images += context.entity_subscribers['docker.image'].query(select='names.0')
        available_images = list(set(available_images))

        bridge_enabled = q.get(presets, 'primary_network_mode') == 'BRIDGED'
        if 'primary_network_mode' not in immutable and q.get(kwargs, 'kwargs.primary_network_mode') in ('NAT', 'BRIDGED', 'HOST', 'NONE'):
            bridge_enabled = read_value(q.get(kwargs, 'kwargs.primary_network_mode'), ValueType.STRING) == 'BRIDGED'

        if 'autostart' not in immutable:
            props += [EnumComplete('autostart=', ['yes', 'no'])]
        if 'primary_network_mode' not in immutable:
            props += [EnumComplete('primary_network_mode=', ['NAT', 'BRIDGED', 'HOST', 'NONE'])]
        if bridge_enabled:
            props += [NullComplete('bridge_address=')]
            props += [NullComplete('bridge_macaddress=')]
            if 'dhcp' not in immutable:
                props += [EnumComplete('dhcp=', ['yes', 'no'])]
        if 'capabilities_add' not in immutable:
            props += [NullComplete('capabilities_add=')]
        if 'capabilities_drop' not in immutable:
            props += [NullComplete('capabilities_drop=')]
        if 'command' not in immutable:
            props += [NullComplete('command=')]
        if 'expose_ports' not in immutable:
            props += [EnumComplete('expose_ports=', ['yes', 'no'])]
        if 'interactive' not in immutable:
            props += [EnumComplete('interactive=', ['yes', 'no'])]
        if 'port' not in immutable:
            props += [NullComplete('port:')]
        if 'privileged' not in immutable:
            props += [EnumComplete('privileged=', ['yes', 'no'])]

        return props + [
            NullComplete('name='),
            NullComplete('hostname='),
            NullComplete('volume:'),
            NullComplete('ro_volume:'),
            EnumComplete('image=', available_images),
            EntitySubscriberComplete('host=', 'docker.host', lambda i: q.get(i, 'name')),
            EntitySubscriberComplete(
                name='networks=',
                datasource='docker.network',
                mapper=lambda i: q.get(i, 'name'),
                filter=[('host', '=', host_id)]
            )
        ]


@description("Start container")
class DockerContainerStartCommand(Command):
    """
    Usage: start

    Example:
    Start single container:
        start
    Start all containers on the system using CLI scripting:
        for (i in $(docker container show)) { / docker container ${i["names"][0]} start }

    Starts a container.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        tid = context.submit_task('docker.container.start', self.parent.entity['id'])
        return TaskPromise(context, tid)


@description("Stop container")
class DockerContainerStopCommand(Command):
    """
    Usage: stop

    Example: stop

    Stops a container.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        tid = context.submit_task('docker.container.stop', self.parent.entity['id'])
        return TaskPromise(context, tid)


@description("Restart container")
class DockerContainerRestartCommand(Command):
    """
    Usage: restart

    Example:
    Restart single container:
        restart
    Restart all containers on the system using CLI scripting:
        for (i in $(docker container show)) { / docker container ${i["names"][0]} restart }

    Restarts a container.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not self.parent.entity['running']:
            raise CommandException('Container {0} is not running'.format(self.parent.entity['name']))
        tid = context.submit_task('docker.container.restart', self.parent.entity['id'])
        return TaskPromise(context, tid)


@description("Start Docker container console")
class DockerContainerConsoleCommand(Command):
    """
    Usage: console

    Examples: console

    Connects to a container's serial console.
    For interactive containers it's a console of primary process,
    for non-interactive ones, this command is executing /bin/sh.
    ^] returns to CLI
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        exec_id = context.call_sync('docker.container.request_interactive_console', self.parent.entity['id'])

        console = Console(context, exec_id)
        console.start()


@description("Show standard output of container's primary process.")
class DockerContainerLogsCommand(Command):
    """
    Usage: logs

    Examples: logs

    Shows standard output of non-interactive container's primary process.
    ^] returns to CLI
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        console = Console(context, self.parent.entity['id'])
        console.start()


@description("Create a new process inside of a container and attach a serial console to that process")
class DockerContainerExecConsoleCommand(Command):
    """
    Usage: exec <command>

    Examples: exec /bin/sh

    Creates and attaches console to a new process on a container.
    ^] returns to CLI
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not len(args):
            raise CommandException('Please specify a command to run on a container')

        exec_id = context.call_sync('docker.container.create_exec', self.parent.entity['id'], args[0])
        console = Console(context, exec_id)
        console.start()


@description("Display container's image readme from Dockerhub")
class DockerContainerReadmeCommand(Command):
    """
    Usage: readme

    Examples: readme

    Displays container's image readme from Dockerhub
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        readme = context.call_sync('docker.image.readme', self.parent.entity['image'].split(':')[0])
        if not readme:
            readme = 'Selected container\'s image does not have readme entry'
        return Sequence(readme)


@description("Clones a Docker container into a new container instance")
class DockerContainerCloneCommand(Command):
    """
    Usage: clone name=<name>

    Example: clone name=test_container_clone

    Clones a Docker container
    into a new container instance.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if len(args) == 1:
            kwargs['name'] = args[0]

        new_name = kwargs.pop('name')
        if not new_name:
            raise CommandException(_('Name of a new container has to be specified'))

        tid = context.submit_task(
            'docker.container.clone',
            self.parent.entity['id'],
            new_name
        )

        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            NullComplete('name='),
        ]


@description("Commits a new image from existing Docker container")
class DockerContainerCommitCommand(Command):
    """
    Usage: commit name=<name> tag=<tag>

    Example: clone name="my_repository/test_image" tag=my_tag

    Commits a new image from an existing Docker container
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if len(args) == 1:
            kwargs['name'] = args[0]

        new_name = kwargs.pop('name')
        if not new_name:
            raise CommandException(_('Name of a new image has to be specified'))

        tag = kwargs.get('tag')

        tid = context.submit_task(
            'docker.container.commit',
            self.parent.entity['id'],
            new_name,
            tag
        )

        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            NullComplete('name='),
            NullComplete('tag='),
        ]


@description("Fetches presets from a given Docker collection")
class DockerFetchPresetsCommand(Command):
    """
    Usage: fetch_presets collection=<collection> <force>=force

    Example: fetch_presets collection=freenas
             fetch_presets collection=freenas force=yes

    Fetch presets of a given Docker collection
    into CLI's cache for tab completion purposes
    around docker namespace.

    When 'force' is set, command queries Dockerhub for fresh data,
    even if local cache is considered still valid by FreeNAS.
    """
    def run(self, context, args, kwargs, opargs):
        def update_default_images(state, task):
            if state == 'FINISHED':
                DockerImageNamespace.default_images = list(task['result'])

        collection_name = kwargs.get('collection')

        if collection_name:
            collection = context.entity_subscribers['docker.collection'].query(
                ('name', '=', collection_name),
                single=True,
                select='id'
            )
            if not collection:
                raise CommandException(_(f'Collection {collection_name} does not exist'))

        else:
            raise CommandException(_('Collection name not specified'))


        force = read_value(kwargs.get('force', False), ValueType.BOOLEAN)

        tid = context.submit_task(
            'docker.collection.get_presets',
            collection,
            force,
            callback=update_default_images
        )

        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            EntitySubscriberComplete('collection=', 'docker.collection', lambda c: c['name']),
            EnumComplete('force=', ['yes', 'no'])
        ]


@description("Configure and manage Docker hosts, images and containers")
class DockerNamespace(Namespace):
    """
    The docker namespace provides commands for listing,
    creating, and managing hosts, images and containers.
    """
    def __init__(self, name, context):
        super(DockerNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            DockerHostNamespace('host', self.context),
            DockerContainerNamespace('container', self.context),
            DockerImageNamespace('image', self.context),
            DockerConfigNamespace('config', self.context),
            DockerCollectionNamespace('collection', self.context)
        ]

    def commands(self):
        return {
            'fetch_presets': DockerFetchPresetsCommand()
        }


def _init(context):
    context.attach_namespace('/', DockerNamespace('docker', context))
    context.map_tasks('docker.config.*', DockerConfigNamespace)
    context.map_tasks('docker.container.*', DockerContainerNamespace)
    context.map_tasks('docker.host.network.*', DockerNetworkNamespace)
    context.map_tasks('docker.host.*', DockerHostNamespace)
    context.map_tasks('docker.image.*', DockerImageNamespace)
    context.map_tasks('docker.collection.*', DockerCollectionNamespace)

