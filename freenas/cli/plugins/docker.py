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

import re
import gettext
from freenas.dispatcher.rpc import RpcException
from freenas.cli.namespace import (
    Namespace, EntityNamespace, Command, EntitySubscriberBasedLoadMixin,
    TaskBasedSaveMixin, CommandException, description, ConfigNamespace, RpcBasedLoadMixin
)
from freenas.cli.output import ValueType, Table, Sequence, read_value
from freenas.cli.utils import (
    TaskPromise, post_save, EntityPromise, get_item_stub, netmask_to_cidr, objname2id, get_related
)
from freenas.utils import query as q
from freenas.cli.complete import NullComplete, EntitySubscriberComplete, EnumComplete, RpcComplete
from freenas.cli.console import Console
from freenas.utils import first_or_default


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


class DockerUtilsMixin(object):
    def get_host(self, o):
        h = self.context.entity_subscribers['docker.host'].query(('id', '=', o['host']), single=True)
        return h['name'] if h else None

    def get_hosts(self, o):
        return list(self.context.entity_subscribers['docker.host'].query(('id', 'in', o['hosts']), select='name')) or []

    def set_host(self, o, v):
        h = self.context.entity_subscribers['docker.host'].query(('name', '=', v), single=True)
        if h:
            o['host'] = h['id']
            return h['id']

    def set_netmask(entity, netmask):
        try:
            netmask_to_cidr(entity, netmask)
        except ValueError as error:
            raise CommandException(error)

    def set_name(self, obj, field, name):
        DockerUtilsMixin.check_name(name)
        obj[field] = name

    @staticmethod
    def check_name(name):
        if not re.match(r'[a-zA-Z0-9._-]*$', name):
            raise CommandException(_(
                'Invalid name: {0}. Only [a-zA-Z0-9._-] characters are allowed'.format(name)
            ))


@description("View information about Docker hosts")
class DockerHostNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The docker host namespace provides commands for listing data
    about Docker hosts available in the system.
    """
    def __init__(self, name, context):
        super(DockerHostNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'docker.host'
        self.primary_key_name = 'name'
        self.allow_create = False
        self.allow_edit = False

        self.add_property(
            descr='VM name',
            name='name',
            get='name',
            set=None,
            usersetable=False,
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


@description("Configure and manage Docker networks")
class DockerNetworkNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, DockerUtilsMixin, EntityNamespace):
    """
    The docker network namespace provides commands for listing,
    creating, and managing Docker networks.
    """
    def __init__(self, name, context):
        super(DockerNetworkNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'docker.network'
        self.create_task = 'docker.network.create'
        self.delete_task = 'docker.network.delete'
        self.allow_edit = False
        self.primary_key_name = 'name'
        self.required_props = ['name']
        self.skeleton_entity = {
            'driver': 'bridge'
        }

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> <property>=<value>

            Examples:
                create with-my-subnet subnet="10.20.4.0/24" gateway=10.20.4.1 driver=bridge
                create docker-selects-subnet driver=bridge

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
            get=self.get_host,
            set=self.set_host,
            usersetable=False,
            list=True,
            complete=EntitySubscriberComplete('host=', 'docker.host', lambda d: d['name']),
            usage=_('''\
            Name of Docker host instance owning network instance.
            Docker host name equals to name of Virtual Machine
            hosting Docker service.''')
        )

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            set=lambda o, v: self.set_name(o, 'name', v),
            usersetable=False,
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
            get=lambda o: [get_related(self.context, 'docker.container', c, 'id') for c in o.get('containers')],
            usage=_("""\
            List of containers connected to the network.
            """),
            list=True,
            type=ValueType.ARRAY
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = self.get_entity_commands

    def get_entity_commands(self, this):
        this.load()
        commands = {
            'connect': DockerNetworkConnectCommand(this),
            'disconnect': DockerNetworkDisconnectCommand(this)
        }

        return commands


@description("Connect container to a network")
class DockerNetworkConnectCommand(Command):
    """
    Usage: connect container=<container_name>

    Example:
        / docker network mynetwork connect container=mycontainer

    Connects container to a network.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not kwargs.get('container'):
            raise CommandException('Please specify container to connect to the network')
        tid = context.submit_task(
            'docker.network.connect',
            objname2id(context, 'docker.container', kwargs.get('container')),
            self.parent.entity['id']
        )
        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            EntitySubscriberComplete('container=', 'docker.container', lambda c: q.get(c, 'names.0'))
        ]


@description("Disconnect container from a network")
class DockerNetworkDisconnectCommand(Command):
    """
    Usage: disconnect container=<container_name>

    Example:
        / docker network mynetwork disconnect container=mycontainer

    Disconnects container from a network.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not kwargs.get('container'):
            raise CommandException('Please specify container to disconnect from the network')
        tid = context.submit_task(
            'docker.network.disconnect',
            objname2id(context, 'docker.container', kwargs.get('container')),
            self.parent.entity['id']
        )
        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            EntitySubscriberComplete('container=', 'docker.container', lambda c: q.get(c, 'names.0'))
        ]


@description("Configure and manage Docker containers")
class DockerContainerNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, DockerUtilsMixin, EntityNamespace):
    """
    The docker container namespace provides commands for listing,
    creating, and managing Docker container.
    """
    def __init__(self, name, context):
        super(DockerContainerNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'docker.container'
        self.create_task = 'docker.container.create'
        self.delete_task = 'docker.container.delete'
        self.allow_edit = False
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
            return ['{0}/{2}={1}'.format(i['container_port'], i['host_port'], i['protocol']) for i in o['ports']]

        def get_volumes(o, ro):
            return ['{0}={1}'.format(i['container_path'], i['host_path']) for i in o['volumes'] if i['readonly'] == ro]

        self.add_property(
            descr='Name',
            name='name',
            get='names.0',
            usersetable=False,
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
            descr='Image name',
            name='image',
            get='image',
            usersetable=False,
            list=True,
            complete=EntitySubscriberComplete('image=', 'docker.image', lambda i: q.get(i, 'names.0')),
            strict=False,
            usage=_('Name of container image used to create an instance of a container.')
        )

        self.add_property(
            descr='Command',
            name='command',
            get='command',
            usersetable=False,
            list=True,
            type=ValueType.ARRAY,
            usage=_('''\
            Command being run on a container (like /bin/sh).
            Can be a single string or a list of strings.''')
        )

        self.add_property(
            descr='Environment',
            name='environment',
            get='environment',
            set='environment',
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
            usersetable=False,
            list=False,
            usage=_('''\
            Used to set host name of a container - like my_ubuntu_container.
            If not set explicitly it defaults in most cases
            to generating a random string as a container's host name.''')
        )

        self.add_property(
            descr='Host',
            name='host',
            get=self.get_host,
            set=self.set_host,
            usersetable=False,
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
            usersetable=False,
            list=True,
            type=ValueType.SET,
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
            usersetable=False,
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
            usersetable=False,
            list=True,
            type=ValueType.BOOLEAN,
            usage=_('''\
            Defines if a container should be started automatically
            when a Docker host related to it goes UP''')
        )

        self.add_property(
            descr='Interactive',
            name='interactive',
            get='interactive',
            usersetable=False,
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
            usersetable=False,
            list=True,
            type=ValueType.SET,
            usage=_('''\
            List of strings formatted like:
            <container_path>=<freenas_path>
            Defines which of FreeNAS paths should be exposed to a container.''')
        )

        self.add_property(
            descr='Readonly Volumes',
            name='ro_volumes',
            get=lambda o: get_volumes(o, True),
            usersetable=False,
            list=True,
            type=ValueType.SET,
            usage=_('''\
            List of strings formatted like:
            <container_path>=<freenas_path>
            Defines which of FreeNAS paths should be exposed to a container.''')
        )

        self.add_property(
            descr='Version',
            name='version',
            get='version',
            usersetable=False,
            list=True,
            type=ValueType.NUMBER,
            usage=_('''\
            Version of container image read from FreeNAS metadata''')
        )

        self.add_property(
            descr='DHCP Enabled',
            name='dhcp',
            get='bridge.dhcp',
            usersetable=False,
            list=True,
            condition=lambda o: q.get(o, 'bridge.enabled'),
            usage=_('''\
            Defines if container will have it's IP address acquired via DHCP.'''),
        )

        self.add_property(
            descr='Container address',
            name='address',
            get='bridge.address',
            usersetable=False,
            list=False,
            condition=lambda o: q.get(o, 'bridge.enabled'),
            usage=_('''\
            IP address of a container when it's set to a bridged mode.'''),
        )

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
            'console': DockerContainerConsoleCommand(this),
            'exec': DockerContainerExecConsoleCommand(this),
            'readme': DockerContainerReadmeCommand(this)
        }
        if this.entity and not this.entity.get('interactive'):
            commands['logs'] = DockerContainerLogsCommand(this)

        return commands


@description("Configure and manage Docker container images")
class DockerImageNamespace(EntitySubscriberBasedLoadMixin, DockerUtilsMixin, EntityNamespace):
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

        if not DockerImageNamespace.default_images:
            DockerImageNamespace.load_collection_images(context)

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
            get=self.get_hosts,
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
            'list': DockerImageListCommand(),
            'readme': DockerImageReadmeCommand(),
            'flush_cache': DockerImageFlushCacheCommand()
        }

        self.entity_commands = lambda this: {
            'delete': DockerImageDeleteCommand(this)
        }

    @staticmethod
    def load_collection_images(context):
        def refresh_images(i):
            DockerImageNamespace.default_images.clear()
            if isinstance(i, RpcException):
                return
            DockerImageNamespace.default_images.extend(list(i))

        def fetch(collection):
            if collection:
                collection_entity = context.entity_subscribers['docker.collection'].query(
                    ('id', '=', collection),
                    single=True
                )
                if collection_entity:
                    context.call_async(
                        'docker.collection.get_entries',
                        lambda r: refresh_images(r),
                        collection
                    )

        context.call_async(
            'docker.config.get_config',
            lambda r: fetch(r.get('default_collection'))
        )


@description("Configure Docker general settings")
class DockerConfigNamespace(DockerUtilsMixin, ConfigNamespace):
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
            get=lambda o: self.get_host({'host': o['default_host']}),
            set=lambda o, v: q.set(o, 'default_host', self.set_host({}, v)),
            complete=EntitySubscriberComplete('default_host=', 'docker.host', lambda d: d['name']),
            usage=_('''\
            Name of a Docker host selected by default for any
            container or container image operations
            when there is no `host` parameter set explicitly in a command.''')
        )

        self.add_property(
            descr='Forward Docker remote API to host',
            name='api_forwarding',
            get=lambda o: self.get_host({'host': o['default_host']}),
            set=lambda o, v: q.set(o, 'default_host', self.set_host({}, v)),
            complete=EntitySubscriberComplete('default_host=', 'docker.host', lambda d: d['name']),
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

        self.add_property(
            descr='Default DockerHub collection',
            name='default_collection',
            get=lambda o: context.call_sync(
                'docker.collection.query',
                [('id', '=', o['default_collection'])],
                {'single': True, 'select': 'name'}
            ),
            set=lambda o, v: q.set(o, 'default_collection', context.call_sync(
                'docker.collection.query',
                [('name', '=', v)],
                {'single': True, 'select': 'id'}
            )),
            complete=RpcComplete('default_collection=', 'docker.collection.query', lambda o: o['name']),
            usage=_('''\
            Used for setting a default DockerHub container images collection,
            which later is being used in tab completion in other 'docker' namespaces.
            Collection equals to DockerHub username''')
        )

    def load(self):
        if self.saved:
            DockerImageNamespace.load_collection_images(self.context)
        super(DockerConfigNamespace, self).load()


@description("Configure and manage Docker container collections")
class DockerCollectionNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, DockerUtilsMixin, EntityNamespace):
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


@description("Get a list of canned FreeNAS docker images")
class DockerImageListCommand(Command):
    """
    Usage: canned
    """
    def run(self, context, args, kwargs, opargs):
        return Table(DockerImageNamespace.default_images, [
            Table.Column('Name', 'name', width=30),
            Table.Column('Description', 'description')
        ])


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
            name,
            host,
            callback=lambda s, t: post_save(self.parent, s, t)
        )

        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            EnumComplete(
                'host=',
                context.entity_subscribers['docker.host'].query(
                    ('id', 'in', self.parent.entity['hosts']),
                    select='name'
                )
            )
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

    Examples: create my-ubuntu-container image=ubuntu:latest interactive=yes
              create my-ubuntu-container image=ubuntu:latest interactive=yes
                     VAR1=VALUE1 VAR2=2
              create my-container image=dockerhub_image_name
                     host=docker_host_vm_name hostname=container_hostname
              create my-container image=dockerhub_image_name autostart=yes
              create my-container image=dockerhub_image_name
                     port:8443/TCP=8443 port:1234/UDP=12356
                     expose_ports=yes
              create my-container image=dockerhub_image_name
                     volume:/container/directory=/mnt/my_pool/container_data
              create bridged-and-static-ip image=ubuntu:latest interactive=yes
                     bridged=yes bridge_address=10.20.0.180
              create bridged-and-dhcp image=ubuntu:latest interactive=yes
                     bridged=yes dhcp=yes

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

        DockerUtilsMixin.check_name(name)

        image = context.entity_subscribers['docker.image'].query(('names.0', 'in', kwargs['image']), single=True)
        if not image:
            image = q.query(DockerImageNamespace.default_images, ('name', '=', kwargs['image']), single=True)

        command = kwargs.get('command', [])
        command = command if isinstance(command, (list, tuple)) else [command]
        env = ['{0}={1}'.format(k, v) for k, v in kwargs.items() if k.isupper()]
        presets = image.get('presets') or {} if image else {}
        ports = presets.get('ports', [])
        volumes = presets.get('static_volumes', [])

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

        create_args = {
            'names': [name],
            'image': kwargs['image'],
            'host': kwargs.get('host'),
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
                'enable': read_value(
                    kwargs.get('bridged', q.get(presets, 'bridge.enable', False)),
                    ValueType.BOOLEAN
                ),
                'dhcp': read_value(
                    kwargs.get('dhcp', q.get(presets, 'bridge.dhcp', False)),
                    ValueType.BOOLEAN
                ),
                'address': kwargs.get('bridge_address')
            }
        }

        ns = get_item_stub(context, self.parent, name)

        tid = context.submit_task(self.parent.create_task, create_args, callback=lambda s, t: post_save(ns, s, t))
        return EntityPromise(context, tid, ns)

    def complete(self, context, **kwargs):
        props = []
        name = q.get(kwargs, 'kwargs.image')
        if name:
            image = context.entity_subscribers['docker.image'].query(('names', 'in', name), single=True)
            if not image:
                image = q.query(DockerImageNamespace.default_images, ('name', '=', name), single=True)

            if image and image['presets']:
                presets = image['presets']
                props += [NullComplete('{id}='.format(**i)) for i in presets['settings']]
                props += [NullComplete(('ro_' if v.get('readonly') else '') + 'volume:{container_path}='.format(**v)) for v in presets['volumes']]
                props += [NullComplete('port:{container_port}/{protocol}='.format(**v)) for v in presets['ports']]

        available_images = q.query(DockerImageNamespace.default_images, select='name')
        available_images += context.entity_subscribers['docker.image'].query(select='names.0')
        available_images = list(set(available_images))

        return props + [
            NullComplete('name='),
            NullComplete('command='),
            NullComplete('hostname='),
            NullComplete('bridge_address='),
            NullComplete('volume:'),
            NullComplete('ro_volume:'),
            NullComplete('port:'),
            EnumComplete('image=', available_images),
            EntitySubscriberComplete('host=', 'docker.host', lambda i: q.get(i, 'name')),
            EnumComplete('interactive=', ['yes', 'no']),
            EnumComplete('autostart=', ['yes', 'no']),
            EnumComplete('expose_ports=', ['yes', 'no']),
            EnumComplete('bridged=', ['yes', 'no']),
            EnumComplete('dhcp=', ['yes', 'no']),
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
            DockerNetworkNamespace('network', self.context),
            DockerImageNamespace('image', self.context),
            DockerConfigNamespace('config', self.context),
            DockerCollectionNamespace('collection', self.context)
        ]


def _init(context):
    context.attach_namespace('/', DockerNamespace('docker', context))
    context.map_tasks('docker.config.*', DockerConfigNamespace)
    context.map_tasks('docker.container.*', DockerContainerNamespace)
    context.map_tasks('docker.network.*', DockerNetworkNamespace)
    context.map_tasks('docker.host.*', DockerHostNamespace)
    context.map_tasks('docker.image.*', DockerImageNamespace)
    context.map_tasks('docker.collection.*', DockerCollectionNamespace)

