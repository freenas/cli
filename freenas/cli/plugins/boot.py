# +
# Copyright 2014 iXsystems, Inc.
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
import icu
from freenas.cli.namespace import (
    Namespace, EntityNamespace, Command, RpcBasedLoadMixin,
    IndexCommand, description, CommandException
)
from freenas.cli.utils import iterate_vdevs, post_save
from freenas.cli.output import ValueType, Table, output_msg
import inspect

t = icu.Transliterator.createInstance("Any-Accents", icu.UTransDirection.FORWARD)
_ = t.transliterate


@description("Boot Environment Management")
class BootEnvironmentNamespace(RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(BootEnvironmentNamespace, self).__init__(name, context)
        self.query_call = 'boot.environments.query'
        self.primary_key_name = 'name'
        self.allow_edit = False
        self.required_props = ['name']

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create name=<bootenv name>

            Example: create foo

            Creates a boot environment""")

        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set name=<newname>

            Example: set name=foo

            Set the name of the current boot environment""")

        self.skeleton_entity = {
            'name': None,
            'realname': None
        }

        self.add_property(
            descr='Boot Environment ID',
            name='name',
            get='id',
            set='id',
            list=True
            )

        self.add_property(
            descr='Active',
            name='active',
            get='active',
            list=True,
            type=ValueType.BOOLEAN,
            set=None,
            )

        self.add_property(
            descr='Boot Environment Name',
            name='realname',
            get='realname',
            list=True,
            set=None,
            )

        self.add_property(
            descr='On Reboot',
            name='onreboot',
            get='on_reboot',
            list=True,
            type=ValueType.BOOLEAN,
            set=None,
            )

        self.add_property(
            descr='Mount point',
            name='mountpoint',
            get='mountpoint',
            list=True,
            set=None,
            )

        self.add_property(
            descr='Space used',
            name='space',
            get='space',
            list=True,
            set=None,
            )

        self.add_property(
            descr='Date created',
            name='created',
            get='created',
            list=True,
            set=None,
            )

        self.primary_key = self.get_mapping('name')

        self.entity_commands = lambda this: {
            'activate': ActivateBootEnvCommand(this),
            'rename': RenameBootEnvCommand(this),
        }

    def get_one(self, name):
        return self.context.call_sync(
            self.query_call, [('id', '=', name)], {'single': True}
        )

    def delete(self, name):
        self.context.submit_task('boot.environments.delete', [name])

    def save(self, this, new=False):
        if new:
            self.context.submit_task(
                'boot.environments.create',
                this.entity['id'],
                callback=lambda s: post_save(this, s),
                )
        else:
            return


@description("Renames a boot environment")
class RenameBootEnvCommand(Command):
    """
    Usage: rename

    Renames the current boot environment.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        try:
            new_be_name = args.pop(0)
        except IndexError:
            raise CommandException('Please provide a target name for the renaming')
        entity = self.parent.entity
        name_property = self.parent.get_mapping('name')
        old_be = entity['id']
        name_property.do_set(entity, new_be_name)
        self.parent.modified = True
        context.submit_task(
            'boot.environments.rename',
            old_be,
            new_be_name,
            callback=lambda s: post_save(self.parent, s)
        )


@description("Activates a boot environment")
class ActivateBootEnvCommand(Command):
    """
    Usage: activate

    Activates the current boot environment
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.submit_task(
            'boot.environments.activate',
            self.parent.entity['id'],
            callback=lambda s: post_save(self.parent, s))


@description("Boot pool management")
class BootPoolNamespace(Namespace):
    def __init__(self, name, context):
        super(BootPoolNamespace, self).__init__(name)

    def commands(self):
        return {
            '?': IndexCommand(self),
            'show_disks': BootPoolShowDisksCommand(),
            'attach_disk': BootPoolAttachDiskCommand(),
            'detach_disk': BootPoolDetachDiskCommand(),
        }


@description("Shows the disks in the boot pool")
class BootPoolShowDisksCommand(Command):
    """
    Usage: show_disks

    Shows the disks in the boot pool
    """

    def run(self, context, args, kwargs, opargs):
        volume = context.call_sync('zfs.pool.get_boot_pool')
        result = list(iterate_vdevs(volume['groups']))
        return Table(result, [
            Table.Column('Name', 'path'),
            Table.Column('Status', 'status')
        ])


@description("Attaches a disk to the boot pool")
class BootPoolAttachDiskCommand(Command):
    """
    Usage: attach_disk <disk>

    Example: attach_disk ada1

    Attaches a disk to the boot pool.
    """
    def run(self, context, args, kwargs, opargs):
        if not args:
            output_msg("attach_disk requires more arguments.\n{0}".format(inspect.getdoc(self)))
            return
        disk = args.pop(0)
        # The all_disks below is a temporary fix, use this after "select" is working
        # all_disks = context.call_sync('disks.query', [], {"select":"path"})
        all_disks = [d["path"] for d in context.call_sync("disks.query")]
        available_disks = context.call_sync('volumes.get_available_disks')
        if not re.match("^\/dev\/", disk):
            disk = "/dev/" + disk
        if disk not in all_disks:
            output_msg("Disk " + disk + " does not exist.")
            return
        if disk not in available_disks:
            output_msg("Disk " + disk + " is not usable.")
            return
        volume = context.call_sync('zfs.pool.get_boot_pool')
        context.submit_task('boot.attach_disk', volume['groups']['data'][0]['guid'], disk)
        return


@description("Detaches a disk from the boot pool")
class BootPoolDetachDiskCommand(Command):
    """
    Usage: detach_disk <disk>

    Example: detach_disk ada1

    Detaches a disk from the boot pool.
    """
    def run(self, context, args, kwargs, opargs):
        disk = args.pop(0)
        context.submit_task('boot.detach_disk', [], disk)
        return


@description("Boot management")
class BootNamespace(Namespace):
    def __init__(self, name, context):
        super(BootNamespace, self).__init__(name)
        self.context = context

    def commands(self):
        return {
            '?': IndexCommand(self)
        }

    def namespaces(self):
        return [
            BootPoolNamespace('pool', self.context),
            BootEnvironmentNamespace('environment', self.context)
        ]


def _init(context):
    context.attach_namespace('/', BootNamespace('boot', context))
