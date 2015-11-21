#
# Copyright 2015 iXsystems, Inc.
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
    Namespace, EntityNamespace, Command, IndexCommand,
    NestedObjectLoadMixin, NestedObjectSaveMixin, RpcBasedLoadMixin,
    TaskBasedSaveMixin, description, CommandException, ListCommand
)
from freenas.cli.output import ValueType, Table
from freenas.utils import first_or_default


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


class StartVMCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.call_task_sync('container.start', self.parent.entity['id'])


class StopVMCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.call_task_sync('container.stop', self.parent.entity['id'])


class RebootVMCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        pass


@description("Configure and manage virtual machines")
class VMNamespace(TaskBasedSaveMixin, RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(VMNamespace, self).__init__(name, context)
        self.query_call = 'container.query'
        self.create_task = 'container.create'
        self.update_task = 'container.update'
        self.delete_task = 'container.delete'
        self.primary_key_name = 'name'

        self.skeleton_entity = {
            'type': 'VM',
            'devices': [],
            'config': {}
        }

        self.add_property(
            descr='VM Name',
            name='name',
            get='name',
            list=True
        )

        self.add_property(
            descr='State',
            name='state',
            get='status.state',
            set=None
        )

        self.add_property(
            descr='Volume',
            name='volume',
            get='target',
            createsetable=True,
            usersetable=False
        )

        self.add_property(
            descr='Description',
            name='description',
            get='description',
            list=False
        )

        self.add_property(
            descr='Memory size (MB)',
            name='memsize',
            get='config.memsize',
            list=True,
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='CPU cores',
            name='cores',
            get='config.ncpus',
            list=True,
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='CD image',
            name='boot_device',
            get='config.boot_device',
            list=False
        )

        self.add_property(
            descr='Bootloader type',
            name='bootloader',
            get='config.bootloader',
            list=False,
            enum=['BHYVELOAD', 'GRUB']
        )

        self.primary_key = self.get_mapping('name')
        self.entity_namespaces = lambda this: [
            VMDisksNamespace('disks', self.context, this),
            VMNicsNamespace('nic', self.context, this)
        ]

        self.entity_commands = lambda this: {
            'start': StartVMCommand(this),
            'stop': StopVMCommand(this),
            'reboot': RebootVMCommand(this)
        }


class VMDisksNamespace(NestedObjectLoadMixin, NestedObjectSaveMixin, EntityNamespace):
    def __init__(self, name, context, parent):
        super(VMDisksNamespace, self).__init__(name, context)
        self.parent = parent
        self.extra_query_params = [('type', 'in', ['DISK', 'CDROM'])]
        self.parent_path = 'devices'
        self.skeleton_entity = {
            'type': 'DISK',
            'properties': {}
        }

        self.add_property(
            descr='Disk name',
            name='name',
            get='name'
        )

        self.add_property(
            descr='Disk type',
            name='type',
            get='type',
            enum=['DISK', 'CDROM']
        )

        self.add_property(
            descr='Disk size',
            name='size',
            get='properties.size',
            type=ValueType.SIZE,
            condition=lambda e: e['type'] == 'DISK'
        )

        self.add_property(
            descr='Image path',
            name='path',
            get='properties.path',
            condition=lambda e: e['type'] == 'CDROM'
        )



class VMNicsNamespace(NestedObjectLoadMixin, NestedObjectSaveMixin, EntityNamespace):
    def __init__(self, name, context, parent):
        super(VMNicsNamespace, self).__init__(name, context)
        self.parent = parent
        self.extra_query_params = [('type', '=', 'NIC')]
        self.parent_path = 'devices'
        self.skeleton_entity = {
            'type': 'NIC',
            'properties': {}
        }

        self.add_property(
            descr='NIC name',
            name='name',
            get='name'
        )

        self.add_property(
            descr='MAC address',
            name='macaddr',
            get='properties.macaddr',
            type=ValueType.SIZE
        )


def _init(context):
    context.attach_namespace('/', VMNamespace('vm', context))
