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
from freenas.cli.output import ValueType, Table, Sequence
from freenas.cli.utils import TaskPromise, post_save, EntityPromise
from freenas.utils.query import get, set
from freenas.cli.complete import NullComplete, EntitySubscriberComplete
from freenas.cli.console import Console


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


class DockerUtilsMixin(object):
    def get_host(self, o):
        h = self.context.entity_subscribers['docker.host'].query(('id', '=', o['host']), single=True)
        return h['name'] if h else None

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
            complete=EntitySubscriberComplete('image=', 'docker.image', lambda i: get(i, 'names.0')),
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
            'console': DockerContainerConsoleCommand(this)
        }


@description("Configure and manage Docker container images")
class DockerImageNamespace(EntitySubscriberBasedLoadMixin, DockerUtilsMixin, EntityNamespace):
    """
    The docker image namespace provides commands for listing,
    creating, and managing Docker container images.
    """
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
            get=self.get_host,
            set=None,
            usersetable=False,
            list=True,
            usage=_('Name of a Docker host storing a container image.')
        )

        self.primary_key = self.get_mapping('name')
        self.extra_commands = {
            'pull': DockerImagePullCommand(self),
            'search': DockerImageSearchCommand(),
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
            set=lambda o, v: set(o, 'default_host', self.set_host({}, v)),
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
            set=lambda o, v: set(o, 'default_host', self.set_host({}, v)),
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
            Table.Column('Name', 'name'),
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
            get(self.parent.entity, 'names.0'),
            self.parent.entity['host'],
            callback=lambda s, t: post_save(self.parent, s, t)
        )

        return TaskPromise(context, tid)


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

    Connects to a container serial console. ^] returns to CLI
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        console = Console(context, self.parent.entity['id'])
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
