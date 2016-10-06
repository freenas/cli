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
    TaskBasedSaveMixin, CommandException, description, ConfigNamespace
)
from freenas.cli.output import ValueType, Table, Sequence, read_value
from freenas.cli.utils import TaskPromise, post_save, EntityPromise
from freenas.utils import query as q
from freenas.cli.complete import NullComplete, EntitySubscriberComplete, EnumComplete
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
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> image=<image> command=<command> environment=<environment>
                          hostname=<hostname> host=<host> ports=<ports>
                          expose_ports=<expose_ports> autostart=<autostart>
                          interactive=<interactive> volumes=<volumes>

            Examples: create my_ubuntu_container image=ubuntu:latest interactive=yes
                      create my_container image=dockerhub_image_name
                             host=docker_host_vm_name hostname=container_hostname
                      create my_container image=dockerhub_image_name autostart=yes
                      create my_container image=dockerhub_image_name
                             ports="8443:8443","25565:25565/TCP","1234:12356/UDP"
                             expose_ports=yes
                      create my_container image=dockerhub_image_name
                             volumes="/container/directory:/host/my_pool/container_data"

            Creates a Docker container. For a list of properties, see 'help properties'.""")
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
            return ['{0}:{1}/{2}'.format(i['container_port'], i['host_port'], i['protocol']) for i in o['ports']]

        def set_ports(o, v):
            o['ports'] = [{'container_port': int(ch[0]), 'host_port': int(ch[1]), 'protocol': p.upper()} for ch, p in ((t[0].split(':'), t[1]) if len(t) == 2 else (t[0].split(':'), 'tcp') for t in (x.rsplit('/') for x in v))]

        def get_volumes(o):
            return ['{0}:{1}'.format(i['container_path'], i['host_path']) for i in o['volumes']]

        def set_volumes(o, v):
            o['volumes'] = [{'container_path': c, 'host_path': h, 'readonly': False} for c, h in (x.split(':') for x in v)]

        self.add_property(
            descr='Name',
            name='name',
            get='names.0',
            usersetable=False,
            list=True,
            usage=_('Name of a container instance.')
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
            descr='Status',
            name='status',
            get='status',
            set=None,
            usersetable=False,
            list=True,
            usage=_('String status of a container returned by a Docker service.')
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
            set=set_ports,
            usersetable=False,
            list=True,
            type=ValueType.SET,
            usage=_('''\
            Array of strings used for defining network ports forwarding.
            Each of values should be formatted like:
            <container_port_number>:<freenas_port_number>/<tcp/udp>
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
            get=get_volumes,
            set=set_volumes,
            usersetable=False,
            list=True,
            type=ValueType.SET,
            usage=_('''\
            List of strings formatted like:
            container_path:freenas_path
            Defines which of FreeNAS paths should be exposed to a container.''')
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = lambda this: {
            'start': DockerContainerStartCommand(this),
            'stop': DockerContainerStopCommand(this),
            'console': DockerContainerConsoleCommand(this),
            'exec': DockerContainerExecConsoleCommand(this)
        }

    def commands(self):
        ret = super(DockerContainerNamespace, self).commands()
        ret['create'] = DockerContainerCreateCommand(self)
        return ret


@description("Configure and manage Docker container images")
class DockerImageNamespace(EntitySubscriberBasedLoadMixin, DockerUtilsMixin, EntityNamespace):
    """
    The docker image namespace provides commands for listing,
    creating, and managing Docker container images.
    """
    freenas_images = []

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

        if not DockerImageNamespace.freenas_images:
            context.call_async(
                'docker.image.get_collection_images',
                lambda r: DockerImageNamespace.freenas_images.extend(list(r)),
                'freenas'
            )

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

        self.primary_key = self.get_mapping('name')
        self.extra_commands = {
            'pull': DockerImagePullCommand(self),
            'search': DockerImageSearchCommand(),
            'list': DockerImageListCommand(),
            'readme': DockerImageReadmeCommand()
        }

        self.entity_commands = lambda this: {
            'delete': DockerImageDeleteCommand(this)
        }


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

        tid = context.submit_task('docker.image.pull', name, hostid)
        return EntityPromise(context, tid, self.parent)

    def complete(self, context, **kwargs):
        return [
            NullComplete('name='),
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
            Table.Column('Name', 'name', display_width_percentage=30),
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
        return Table(DockerImageNamespace.freenas_images, [
            Table.Column('Name', 'name', display_width_percentage=30),
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


@description("Delete cached container image")
class DockerImageDeleteCommand(Command):
    """
    Usage: delete

    Example: delete

    Deletes cached container image.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        tid = context.submit_task(
            'docker.image.delete',
            q.get(self.parent.entity, 'names.0'),
            self.parent.entity['host'],
            callback=lambda s, t: post_save(self.parent, s, t)
        )

        return TaskPromise(context, tid)


class DockerContainerCreateCommand(Command):
    """
    Usage: ...
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not kwargs.get('name') and not args:
            raise CommandException('name is a required property')

        if not kwargs.get('image'):
            raise CommandException('image is a required property')

        name = kwargs.get('name') or args[0]
        image = context.entity_subscribers['docker.image'].query(('names', 'in', kwargs['image']), single=True)
        if not image:
            image = q.query(DockerImageNamespace.freenas_images, ('name', '=', kwargs['image']), single=True)

        command = kwargs.get('command', [])
        command = command if isinstance(command, (list, tuple)) else [command]
        env = ['{0}={1}'.format(k, v) for k, v in kwargs.items() if k.isupper()]
        presets = image.get('presets') or {} if image else {}
        ports = presets.get('ports', [])
        volumes = []

        for k, v in kwargs.items():
            if k.startswith('volume:'):
                _, container_path = k.split(':', maxsplit=1)
                volumes.append({
                    'container_path': container_path,
                    'host_path': v,
                    'readonly': False
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

        if len(presets.get('volumes', [])) != len(volumes):
            presets_volumes = set(i['container_path'] for i in presets['volumes'])
            entered_volumes = set(i['container_path'] for i in volumes)
            raise CommandException('Required volumes missing: {0}'.format(', '.join(presets_volumes - entered_volumes)))

        create_args = {
            'names': [name],
            'image': kwargs['image'],
            'host': kwargs.get('host'),
            'hostname': kwargs.get('hostname'),
            'command': command,
            'environment': env,
            'volumes': volumes,
            'ports': ports,
            'expose_ports': read_value(
                kwargs.get('expose_ports', q.get(presets, 'expose_ports', False)),
                ValueType.BOOLEAN
            ),
            'interactive': read_value(
                kwargs.get('interactive', q.get(presets, 'interactive', False)),
                ValueType.BOOLEAN
            )
        }

        tid = context.submit_task(self.parent.create_task, create_args)
        return EntityPromise(context, tid, self.parent)

    def complete(self, context, **kwargs):
        props = []
        name = q.get(kwargs, 'kwargs.image')
        if name:
            image = context.entity_subscribers['docker.image'].query(('names', 'in', name), single=True)
            if not image:
                image = q.query(DockerImageNamespace.freenas_images, ('name', '=', name), single=True)

            if image and image['presets']:
                presets = image['presets']
                props += [NullComplete('{id}='.format(**i)) for i in presets['settings']]
                props += [NullComplete('volume:{container_path}='.format(**v)) for v in presets['volumes']]
                props += [NullComplete('port:{container_port}/{protocol}='.format(**v)) for v in presets['ports']]

        return props + [
            NullComplete('name='),
            NullComplete('command='),
            NullComplete('hostname='),
            EntitySubscriberComplete('image=', 'docker.image', lambda i: q.get(i, 'names.0')),
            EntitySubscriberComplete('host=', 'docker.host', lambda i: q.get(i, 'name')),
            EnumComplete('interactive=', ['yes', 'no']),
            EnumComplete('autostart=', ['yes', 'no']),
            EnumComplete('expose_ports=', ['yes', 'no']),
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

    Connects to a container's serial console. ^] returns to CLI
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
            DockerConfigNamespace('config', self.context)
        ]


def _init(context):
    context.attach_namespace('/', DockerNamespace('docker', context))
    context.map_tasks('docker.config.*', DockerConfigNamespace)
    context.map_tasks('docker.container.*', DockerContainerNamespace)
    context.map_tasks('docker.host.*', DockerHostNamespace)
    context.map_tasks('docker.image.*', DockerImageNamespace)

