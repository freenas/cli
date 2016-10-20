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


import gettext
from freenas.cli.namespace import (
    Namespace, EntityNamespace, Command, EntitySubscriberBasedLoadMixin,
    description, CommandException
)
from freenas.cli.utils import TaskPromise, iterate_vdevs, post_save, correct_disk_path
from freenas.cli.output import ValueType, Table, output_msg
import inspect

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Manage boot environments")
class BootEnvironmentNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The environment namespace provides commands for listing and
    managing boot environments.
    """
    def __init__(self, name, context):
        super(BootEnvironmentNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'boot.environment'
        self.primary_key_name = 'id'
        self.required_props = ['name']

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <bootenv name>

            Example: create mybootenv

            Create a boot environment.""")

        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set name=<newname>

            Example: set name=mybootenv

            Edit the name of the specified boot environment.""")
        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Examples: delete

            Delete the specified boot environment. This command will
            fail if the boot environment is active.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists boot environments.

            Examples:
                show
                show | search name == default
                show | search active == no
                show | search name~="FreeNAS" | sort name""")
        self.entity_localdoc['GetEntityCommand'] = ("""\
            Usage: get <field>

            Examples:
                get name

            Display value of specified field.""")
        self.entity_localdoc['EditEntityCommand'] = ("""\
            Usage: edit <field>

            Examples: edit name

            Opens the default editor for the specified property. The default editor
            is inherited from the shell's $EDITOR which can be set from the shell.
            For a list of properties for the current namespace, see 'help properties'.""")
        self.entity_localdoc['ShowEntityCommand'] = ("""\
            Usage: show

            Examples: show

            Display the property values for boot environment.""")

        self.add_property(
            descr='Name',
            name='name',
            get='id',
            usage=_("""\
            Editable value. This is the name of the entry which
            appears in the boot menu."""),
            set='id',
            list=True
        )

        self.add_property(
            descr='Active',
            name='active',
            get='active',
            usage=_("""\
            Can be set to yes or no. Yes indicates which boot
            entry was used at last system boot. Only one entry
            can be set to yes."""),
            list=True,
            type=ValueType.BOOLEAN,
            set=None,
        )

        self.add_property(
            descr='Real Name',
            name='realname',
            get='realname',
            usage=_("""\
            Read-only name issued when boot environment
            is created."""),
            list=False,
            set=None,
        )

        self.add_property(
            descr='On Reboot',
            name='onreboot',
            get='on_reboot',
            usage=_("""\
            Can be set to yes or no. Yes indicates the default
            boot entry for the next system boot. Only one entry
            can be set to yes."""),
            list=True,
            type=ValueType.BOOLEAN,
            set=None,
        )

        self.add_property(
            descr='Space used',
            name='space',
            get='space',
            usage=_("""\
            Read-only value indicating how much space the boot
            environment occupies."""),
            list=True,
            set=None,
            type=ValueType.SIZE
        )

        self.add_property(
            descr='Date created',
            name='created',
            get='created',
            usage=_("""\
            Read-only timestamp indicating when the boot
            environment was created."""),
            list=True,
            set=None,
        )

        self.add_property(
            descr='Keep',
            name='keep',
            get='keep',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.primary_key = self.get_mapping('name')

        self.entity_commands = lambda this: {
            'activate': ActivateBootEnvCommand(this),
            'rename': RenameBootEnvCommand(this),
        }

    def serialize(self):
        raise NotImplementedError()

    def delete(self, this, kwargs):
        return self.context.submit_task('boot.environment.delete', this.entity['id'])

    def save(self, this, new=False):
        if new:
            return self.context.submit_task(
                'boot.environment.clone',
                this.entity['id'],
                callback=lambda s, t: post_save(this, s, t),
                )
        else:
            return self.context.submit_task(
                'boot.environment.update',
                this.orig_entity['id'],
                this.get_diff(),
                callback=lambda s, t: post_save(this, s, t)
                )


@description("Rename a boot environment")
class RenameBootEnvCommand(Command):
    """
    Usage: rename <newname>

    Examples: rename mybootenv

    Rename the boot environment.
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
        name_property.do_set(entity, new_be_name)
        self.parent.modified = True
        self.parent.save()


@description("Activate a boot environment")
class ActivateBootEnvCommand(Command):
    """
    Usage: activate

    Examples: activate

    Activate the specified boot environment.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        tid = context.submit_task(
            'boot.environment.activate',
            self.parent.entity['id'],
            callback=lambda s, t: post_save(self.parent, s, t))

        return TaskPromise(context, tid)


@description("Manage devices in boot pool")
class BootPoolNamespace(Namespace):
    """
    The pool namespace provides commands for listing and managing the devices
    in the boot pool.
    """
    def __init__(self, name, context):
        super(BootPoolNamespace, self).__init__(name)

    def commands(self):
        return {
            'show_disks': BootPoolShowDisksCommand(),
            'attach_disk': BootPoolAttachDiskCommand(),
            'detach_disk': BootPoolDetachDiskCommand(),
            'show': BootPoolShowCommand(),
            'scrub': BootPoolScrubCommand(),
        }


@description("Shows boot pool space usage")
class BootPoolShowCommand(Command):
    """
    Usage: show

    Examples: show
    """
    def run(self, context, args, kwargs, opargs):
        volume = context.call_sync('boot.pool.get_config')
        result = [
            {'free': volume['properties']['free']['value'],
             'occupied': volume['properties']['allocated']['value'],
             'total': volume['properties']['size']['value'],
             'last_scrub_time': volume['scan']['end_time'],
             'last_scrub_errors': volume['scan']['errors']}
        ]
        return Table(result, [
            Table.Column('Total size', 'total', ValueType.STRING),
            Table.Column('Occupied space', 'occupied', ValueType.STRING),
            Table.Column('Free space', 'free', ValueType.STRING),
            Table.Column('Last scrub time', 'last_scrub_time', ValueType.STRING),
            Table.Column('Last scrub errors', 'last_scrub_errors', ValueType.STRING),

        ])


@description("Scrub the boot pool")
class BootPoolScrubCommand(Command):
    """
    Usage: scrub
`
    Examples: scrub

    Scrub the boot pool.
    """

    def run(self, context, args, kwargs, opargs):
        context.submit_task('boot.pool.scrub')


@description("List the devices in the boot pool")
class BootPoolShowDisksCommand(Command):
    """
    Usage: show_disks

    Examples: show_disks

    List the device(s) in the boot pool and display
    the status of the boot pool.
    """

    def run(self, context, args, kwargs, opargs):
        volume = context.call_sync('zfs.pool.get_boot_pool')
        result = list(iterate_vdevs(volume['groups']))
        return Table(result, [
            Table.Column('Name', 'path'),
            Table.Column('Status', 'status')
        ])


@description("Attach a device to the boot pool")
class BootPoolAttachDiskCommand(Command):
    """
    Usage: attach_disk <disk>

    Example: attach_disk ada1

    Attach the specified device(s) to the boot pool,
    creating an N-way mirror where N is the total number
    of devices in the pool. The command will fail if a
    device is smaller than the smallest device already in
    the pool.
    """
    def run(self, context, args, kwargs, opargs):
        if not args:
            output_msg("attach_disk requires more arguments.\n{0}".format(inspect.getdoc(self)))
            return
        disk = args.pop(0)
        # The all_disks below is a temporary fix, use this after "select" is working
        # all_disks = context.call_sync('disk.query', [], {"select":"path"})
        all_disks = [d["path"] for d in context.call_sync("disk.query")]
        available_disks = context.call_sync('volume.get_available_disks')
        disk = correct_disk_path(disk)
        if disk not in all_disks:
            output_msg("Disk " + disk + " does not exist.")
            return
        if disk not in available_disks:
            output_msg("Disk " + disk + " is not usable.")
            return

        tid = context.submit_task('boot.disk.attach', disk)
        return TaskPromise(context, tid)


@description("Detach a device from the boot pool")
class BootPoolDetachDiskCommand(Command):
    """
    Usage: detach_disk <disk>

    Example: detach_disk ada1p2

    Detach the specified device(s) from the boot pool,
    reducing the number of devices in the N-way mirror. If
    only one device remains, it has no redundancy. At least
    one device must remain in the pool.
    See 'show_disks' for a list of disks that can be detached from the pool.
    """
    def run(self, context, args, kwargs, opargs):
        if not args:
            raise CommandException("detach_disk requires more arguments.\n{0}".format(inspect.getdoc(self)))
        disk = args.pop(0)
        disk = correct_disk_path(disk)
        tid = context.submit_task('boot.disk.detach', disk)
        return TaskPromise(context, tid)


@description("Manage boot environments and the boot pool")
class BootNamespace(Namespace):
    """
    The boot namespace provides commands for listing and managing
    boot environments and the devices in the boot pool.
    """
    def __init__(self, name, context):
        super(BootNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            BootPoolNamespace('pool', self.context),
            BootEnvironmentNamespace('environment', self.context)
        ]


def _init(context):
    context.attach_namespace('/', BootNamespace('boot', context))
