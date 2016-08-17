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

from freenas.cli.namespace import (
    Namespace, EntityNamespace, Command, EntitySubscriberBasedLoadMixin,
    TaskBasedSaveMixin, CommandException
)
from freenas.cli.output import ValueType, Table
from freenas.cli.output import Sequence


class DockerHostNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
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


class DockerContainerNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
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
            'start': DockerContainerStartStopCommand(this, 'start'),
            'stop': DockerContainerStartStopCommand(this, 'stop'),
        }


class DockerImageNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(DockerImageNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'docker.image'
        self.primary_key_name = 'names.0'
        self.allow_create = False
        self.allow_edit = False

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
            get='host',
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


class DockerImagePullCommand(Command):
    def run(self, context, args, kwargs, opargs):
        if len(args) != 2:
            raise CommandException("Please specify image name and docker host name")

        hostid = context.entity_subscribers['docker.host'].query(('name', '=', args[1]), single=True)
        if not hostid:
            raise CommandException("Docker host {0} not found".format(args[1]))

        context.submit_task('docker.image.pull', args[0], hostid['id'])


class DockerImageSearchCommand(Command):
    def run(self, context, args, kwargs, opargs):
        if len(args) != 1:
            raise CommandException("Please specify fragment of the image name")

        return Table(context.call_sync('docker.image.search', args[0]), [
            Table.Column('Name', 'name'),
            Table.Column('Description', 'description')
        ])


class DockerImageReadmeCommand(Command):
    def run(self, context, args, kwargs, opargs):
        if len(args) != 1:
            raise CommandException("Please specify the image name")

        readme = context.call_sync('docker.image.readme', args[0])
        if readme:
            return Sequence(readme)
        else:
            return Sequence("Image {0} readme does not exist".format(args[0]))


class DockerContainerStartStopCommand(Command):
    def __init__(self, parent, action):
        self.action = action
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.submit_task('docker.container.{0}'.format(self.action), self.parent.entity['id'])


class DockerNamespace(Namespace):
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
