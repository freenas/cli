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
    TaskBasedSaveMixin, CommandException, description
)
from freenas.cli.output import ValueType, Table
from freenas.cli.output import Sequence
from freenas.cli.utils import post_save
from freenas.utils.query import get
from freenas.cli.complete import NullComplete, EntitySubscriberComplete


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


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
            list=True
        )

        self.add_property(
            descr='State',
            name='state',
            get='state',
            set=None,
            usersetable=False,
            list=True
        )

        self.add_property(
            descr='Operating system',
            name='os',
            get='status.os',
            set=None,
            usersetable=False,
            list=False
        )

        self.add_property(
            descr='Docker unique ID',
            name='docker_unique_id',
            get='status.unique_id',
            set=None,
            usersetable=False,
            list=False
        )

        self.primary_key = self.get_mapping('name')


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
        self.delete_task = 'docker.container.delete'
        self.primary_key_name = 'names.0'

        def get_host(o):
            h = context.entity_subscribers['docker.host'].query(('id', '=', o['host']), single=True)
            return h['name'] if h else None

        def set_host(o, v):
            h = context.entity_subscribers['docker.host'].query(('name', '=', v), single=True)
            if h:
                o['host'] = h['id']

        def get_ports(o):
            return ['{0}:{1}'.format(i['container_port'], i['host_port']) for i in o['ports']]

        def set_ports(o, v):
            o['ports'] = [{'container_port': c, 'host_port': h} for c, h in (x.split(':') for x in v)]

        def get_volumes(o):
            return ['{0}:{1}'.format(i['container_path'], i['host_path']) for i in o['volumes']]

        def set_volumes(o, v):
            o['volumes'] = [{'container_path': c, 'host_path': h, 'readonly': False} for c, h in (x.split(':') for x in v)]

        self.add_property(
            descr='Name',
            name='name',
            get='names.0',
            usersetable=False,
            list=True
        )

        self.add_property(
            descr='Image name',
            name='image',
            get='image',
            usersetable=False,
            list=True
        )

        self.add_property(
            descr='Command',
            name='command',
            get='command',
            usersetable=False,
            list=True
        )

        self.add_property(
            descr='Status',
            name='status',
            get='status',
            set=None,
            usersetable=False,
            list=True
        )

        self.add_property(
            descr='Host',
            name='host',
            get=get_host,
            set=set_host,
            usersetable=False,
            list=True
        )

        self.add_property(
            descr='Ports',
            name='ports',
            get=get_ports,
            set=set_ports,
            usersetable=False,
            list=True,
            type=ValueType.SET
        )

        self.add_property(
            descr='Expose ports',
            name='expose_ports',
            get='expose_ports',
            usersetable=False,
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Volumes',
            name='volumes',
            get=get_volumes,
            set=set_volumes,
            usersetable=False,
            list=True,
            type=ValueType.SET
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = lambda this: {
            'start': DockerContainerStartCommand(this),
            'stop': DockerContainerStopCommand(this),
        }


@description("Configure and manage Docker conatiner images")
class DockerImageNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
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

        def get_host(o):
            h = context.entity_subscribers['docker.host'].query(('id', '=', o['host']), single=True)
            return h['name'] if h else None

        self.add_property(
            descr='Name',
            name='name',
            get='names.0',
            set=None,
            usersetable=False,
            list=True
        )

        self.add_property(
            descr='Size',
            name='size',
            get='size',
            set=None,
            usersetable=False,
            list=True,
            type=ValueType.SIZE
        )

        self.add_property(
            descr='Created at',
            name='created_at',
            get='created_at',
            set=None,
            usersetable=False,
            list=True
        )

        self.add_property(
            descr='Host',
            name='host',
            get=get_host,
            set=None,
            usersetable=False,
            list=True
        )

        self.primary_key = self.get_mapping('name')
        self.extra_commands = {
            'pull': DockerImagePullCommand(),
            'search': DockerImageSearchCommand(),
            'readme': DockerImageReadmeCommand()
        }

        self.entity_commands = lambda this: {
            'delete': DockerImageDeleteCommand(this)
        }


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

        host = kwargs.pop('host')
        hostid = None
        if host:
            hostid = context.entity_subscribers['docker.host'].query(('name', '=', host), single=True, select='id')

        context.submit_task('docker.image.pull', name, hostid)

    def complete(self, context):
        return [
            NullComplete('name='),
            EntitySubscriberComplete('host=', 'docker.host', lambda d: d['name'], ['auto'], list=True)
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

    def complete(self, context):
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

    def complete(self, context):
        return [
            NullComplete('name=')
        ]


@description("Delete cached container image")
class DockerImageDeleteCommand(Command):
    """
    Usage: delete

    Deletes cached container image.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.submit_task(
            'docker.image.delete',
            get(self.parent.entity, 'names.0'),
            self.parent.entity['host'],
            callback=lambda s, t: post_save(self.parent, s, t)
        )


@description("Start container")
class DockerContainerStartCommand(Command):
    """
    Usage: start

    Starts a container.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.submit_task('docker.container.start', self.parent.entity['id'])


@description("Stop container")
class DockerContainerStopCommand(Command):
    """
    Usage: stop

    Stops a container.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.submit_task('docker.container.stop', self.parent.entity['id'])


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
            DockerImageNamespace('image', self.context)
        ]


def _init(context):
    context.attach_namespace('/', DockerNamespace('docker', context))


def get_top_namespace(context):
    return DockerNamespace('docker', context)
