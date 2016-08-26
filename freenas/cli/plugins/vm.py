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
from freenas.cli.output import Sequence
from freenas.cli.namespace import (
    EntityNamespace, Command, NestedObjectLoadMixin, NestedObjectSaveMixin, EntitySubscriberBasedLoadMixin,
    RpcBasedLoadMixin, TaskBasedSaveMixin, description, CommandException
)
from freenas.cli.output import ValueType, get_humanized_size
from freenas.cli.utils import post_save
from freenas.utils import first_or_default
from freenas.utils.query import get, set
from freenas.cli.complete import NullComplete
from freenas.cli.console import Console


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


class StartVMCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.submit_task('vm.start', self.parent.entity['id'])


class StopVMCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.submit_task('vm.stop', self.parent.entity['id'])


class KillVMCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.submit_task('vm.stop', self.parent.entity['id'], True)


class RebootVMCommand(Command):
    """
    Usage: reboot force=<force>

    Examples:
        reboot
        reboot force=yes

    Reboots VM
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        force = kwargs.get('force', False)
        context.submit_task('vm.reboot', self.parent.entity['id'], force)


class ConsoleCommand(Command):
    """
    Usage: console

    Examples: console

    Connects to VM serial console. ^] returns to CLI
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        console = Console(context, self.parent.entity['id'])
        console.start()


class ConsoleVGACommand(Command):
    """
    Usage: console_vga

    Examples: console_vga

    Returns link to VM VGA console.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        url = context.call_sync('containerd.console.request_webvnc_console', self.parent.entity['id'])
        return url


@description("Import virtual machine from volume")
class ImportVMCommand(Command):
    """
    Usage: import <name> volume=<volume>

    Imports a VM.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        try:
            name = args[0]
        except IndexError:
            raise CommandException(_("Please specify the name of VM."))
        volume = kwargs.get('volume', None)
        if not volume:
            raise CommandException(_("Please specify which volume is containing a VM being imported."))
        context.submit_task('vm.import', name, volume, callback=lambda s, t: post_save(self.parent, t))


@description("Configure and manage virtual machines")
class VMNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The vm namespace provides commands for listing, importing,
    creating, and managing virtual machines.
    """
    def __init__(self, name, context):
        super(VMNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'vm'
        self.create_task = 'vm.create'
        self.update_task = 'vm.update'
        self.delete_task = 'vm.delete'
        self.required_props = ['name', 'volume']
        self.primary_key_name = 'name'
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> volume=<volume> <property>=<value> ...

            Examples: create myvm volume=myvolume
                      create myfreebsd volume=myvolume template=freebsd-11-zfs

            Creates a virtual machine. For a list of properties, see 'help properties'.
            For a list of templates see '/ vm template show'""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set memsize=2GB
                      set cores=4
                      set guest_type=freebsd64
                      set bootloader=GRUB

            Sets a virtual machine property. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Deletes the specified virtual machine.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all virtual machines. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")

        def set_memsize(o, v):
            set(o, 'config.memsize', int(v / 1024 / 1024))

        self.skeleton_entity = {
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
            descr='Template name',
            name='template',
            get='template.name'
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
            get=lambda o: get(o, 'config.memsize') * 1024 * 1024,
            set=set_memsize,
            list=True,
            type=ValueType.SIZE
        )

        self.add_property(
            descr='CPU cores',
            name='cores',
            get='config.ncpus',
            list=True,
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Start on boot',
            name='autostart',
            get='config.autostart',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Boot device',
            name='boot_device',
            get='config.boot_device',
            list=False
        )

        self.add_property(
            descr='Boot partition (for GRUB)',
            name='boot_partition',
            get='config.boot_partition',
            list=False
        )

        self.add_property(
            descr='Bootloader type',
            name='bootloader',
            get='config.bootloader',
            list=False,
            enum=['BHYVELOAD', 'GRUB', 'UEFI']
        )

        self.add_property(
            descr='Guest type',
            name='guest_type',
            get='guest_type',
            list=False,
            enum=[
                'linux64',
                'freebsd32',
                'freebsd64',
                'netbsd64',
                'openbsd32',
                'openbsd64',
                'windows64',
                'solaris64',
                'other'
            ]
        )

        self.add_property(
            descr='Cloud-init data',
            name='cloud_init',
            get='config.cloud_init',
            list=False,
        )

        self.add_property(
            descr='Enabled',
            name='enabled',
            get='enabled',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Immutable',
            name='immutable',
            get='immutable',
            list=False,
            usersetable=False,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Readme',
            name='readme',
            get='template.readme',
            set='template.readme',
            list=False,
            type=ValueType.TEXT_FILE
        )

        self.add_property(
            descr='NAT IP address',
            name='nat_ip',
            get='status.nat_lease.client_ip',
            set=None,
            list=False,
            condition=lambda o: get(o, 'status.state') != 'STOPPED' and get(o, 'status.nat_lease')
        )

        self.primary_key = self.get_mapping('name')
        self.entity_namespaces = self.get_entity_namespaces

        self.entity_commands = self.get_entity_commands

        self.extra_commands = {
            'import': ImportVMCommand(self)
        }

    def namespaces(self):
        yield TemplateNamespace('template', self.context)
        for namespace in super(VMNamespace, self).namespaces():
            yield namespace

    def get_entity_namespaces(self, this):
        this.load() if hasattr(this, 'load') else None
        return [
            VMDeviceNamespace('device', self.context, this),
            VMVolumeNamespace('volume', self.context, this),
            VMSnapshotsNamespace('snapshot', self.context, this)
        ]

    def get_entity_commands(self, this):
        this.load() if hasattr(this, 'load') else None

        commands = {
            'start': StartVMCommand(this),
            'stop': StopVMCommand(this),
            'kill': KillVMCommand(this),
            'reboot': RebootVMCommand(this),
            'console': ConsoleCommand(this),
            'readme': ReadmeCommand(this)
        }

        if hasattr(this, 'entity') and this.entity is not None:
            if first_or_default(lambda d: d['type'] == 'GRAPHICS', this.entity['devices']):
                commands['console_vga'] = ConsoleVGACommand(this)

        return commands


class VMDeviceDiskMixin(EntityNamespace):
    def __init__(self, name, context):
        def get_humanized_summary(o):
            if get(o, 'type') == 'DISK':
                return "{0} {1} DISK".format(
                    get_humanized_size(get(o, 'properties.size')),
                    get(o, 'mode')
                )

            return get(o, 'type')

        super(VMDeviceDiskMixin, self).__init__(name, context)
        self.humanized_summaries['DISK'] = get_humanized_summary
        self.humanized_summaries['CDROM'] = get_humanized_summary

        self.add_property(
            descr='Disk mode',
            name='disk_mode',
            get='properties.mode',
            enum=['AHCI', 'VIRTIO'],
            list=False,
            condition=lambda e: e['type'] in ('DISK', 'CDROM')
        )

        self.add_property(
            descr='Disk size',
            name='disk_size',
            get='properties.size',
            type=ValueType.SIZE,
            list=False,
            condition=lambda e: e['type'] == 'DISK'
        )

        self.add_property(
            descr='Image path',
            name='disk_image_path',
            get='properties.path',
            list=False,
            condition=lambda e: e['type'] == 'CDROM'
        )


class VMDeviceNicMixin(EntityNamespace):
    def __init__(self, name, context):
        def get_humanized_summary(o):
            if get(o, 'properties.bridge'):
                return "{0} NIC bridged to {1}".format(get(o, 'properties.device'), get(o, 'properties.bridge'))

            return "{0} NIC".format(get(o, 'properties.device'))

        super(VMDeviceNicMixin, self).__init__(name, context)
        self.humanized_summaries['NIC'] = get_humanized_summary

        self.add_property(
            descr='NIC mode',
            name='nic_mode',
            get='properties.mode',
            enum=['NAT', 'BRIDGED', 'MANAGEMENT'],
            list=False,
            condition=lambda e: e['type'] == 'NIC'
        )

        self.add_property(
            descr='Emulated device type',
            name='nic_device_type',
            get='properties.device',
            enum=['VIRTIO', 'E1000', 'NE2K'],
            list=False,
            condition=lambda e: e['type'] == 'NIC'
        )

        self.add_property(
            descr='Bridge with',
            name='nic_bridge',
            get='properties.bridge',
            list=False,
            condition=lambda e: e['type'] == 'NIC'
        )

        self.add_property(
            descr='MAC address',
            name='nic_macaddr',
            get='properties.link_address',
            list=False,
            condition=lambda e: e['type'] == 'NIC'
        )


class VMDeviceUSBMixin(EntityNamespace):
    def __init__(self, name, context):
        def get_humanized_summary(o):
            return "USB {0} device".format(get(o, 'properties.device'))

        super(VMDeviceUSBMixin, self).__init__(name, context)
        self.humanized_summaries['USB'] = get_humanized_summary

        self.add_property(
            descr='Emulated device type',
            name='usb_device_type',
            get='properties.device',
            enum=['tablet'],
            list=False,
            condition=lambda e: e['type'] == 'USB'
        )


class VMDeviceVGAMixin(EntityNamespace):
    def __init__(self, name, context):
        def get_humanized_summary(o):
            return "VGA device with resolution {0}".format(get(o, 'properties.resolution'))

        def set_resolution(o ,v):
            if 'properties' in o:
                o['properties'].update({'resolution': '{0}x{1}'.format(v[0], v[1])})
            else:
                o.update({'properties': {'resolution': '{0}x{1}'.format(v[0], v[1])}})

        def set_vnc_port(obj, val):
            if val not in range(1, 65536):
                raise CommandException(_("vnc_port must be value in range 1..65535"))
            if 'properties' in obj:
                obj['properties']['vnc_port'] = val
            else:
                obj.update({'properties': {'vnc_port': '{0}'.format(val)}})

        super(VMDeviceVGAMixin, self).__init__(name, context)
        self.humanized_summaries['GRAPHICS'] = get_humanized_summary

        self.add_property(
            descr='Framebuffer resolution',
            name='resolution',
            get=lambda o: list(o['properties']['resolution'].split('x')),
            set=set_resolution,
            list=False,
            type=ValueType.ARRAY,
            enum=[
                [1920, 1200],
                [1920, 1080],
                [1600, 1200],
                [1600, 900],
                [1280, 1024],
                [1280, 720],
                [1024, 768],
                [800, 600],
                [640, 480]
            ],
            condition=lambda e: e['type'] == 'GRAPHICS'
        )

        self.add_property(
            descr='VNC server enabled',
            name='vnc_enabled',
            get='properties.vnc_enabled',
            list=False,
            type=ValueType.BOOLEAN,
            condition=lambda e: e['type'] == 'GRAPHICS'
        )

        self.add_property(
            descr='VNC server port',
            name='vnc_port',
            get='properties.vnc_port',
            list=False,
            set=set_vnc_port,
            type=ValueType.NUMBER,
            condition=lambda e: e['type'] == 'GRAPHICS'
        )


class VMDeviceListMixin(EntityNamespace):
    def __init__(self, name, context):
        def get_humanized_summary(o):
            return self.humanized_summaries[o['type']](o)

        super(VMDeviceListMixin, self).__init__(name, context)
        self.humanized_summaries = {}

        self.add_property(
            descr='Device name',
            name='name',
            get='name'
        )

        self.add_property(
            descr='Device type',
            name='type',
            get='type',
            set='type',
            enum=['DISK', 'CDROM', 'NIC', 'USB', 'GRAPHICS']
        )

        self.add_property(
            descr="Device summary",
            name='device_summary',
            get=get_humanized_summary,
            set=None,
        )


class VMDeviceNamespace(NestedObjectLoadMixin,
                        NestedObjectSaveMixin,
                        VMDeviceVGAMixin,
                        VMDeviceUSBMixin,
                        VMDeviceNicMixin,
                        VMDeviceDiskMixin,
                        VMDeviceListMixin):
    def __init__(self, name, context, parent):
        super(VMDeviceNamespace, self).__init__(name, context)
        self.parent = parent
        self.primary_key_name = 'name'
        self.extra_query_params = [('type', 'in', ('DISK', 'CDROM', 'NIC', 'USB', 'GRAPHICS'))]
        self.parent_path = 'devices'
        self.primary_key = self.get_mapping('name')


class VMVolumeNamespace(NestedObjectLoadMixin, NestedObjectSaveMixin, EntityNamespace):
    def __init__(self, name, context, parent):
        super(VMVolumeNamespace, self).__init__(name, context)
        self.parent = parent
        self.primary_key_name = 'name'
        self.extra_query_params = [('type', '=', 'VOLUME')]
        self.parent_path = 'devices'
        self.skeleton_entity = {
            'type': 'VOLUME',
            'properties': {}
        }
        self.required_props = ['name','destination']
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> destination=<destination> <property>=<value> ...

            Examples: create myvolume destination=/mnt/tank/vmvolume

            Creates a VM volume. For a list of properties, see 'help properties.'""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set auto=yes
                      set destination=/mnt/tank/newdest

            Sets a VM volume property. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Deletes the specified VM volume.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all VM volumes. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")

        self.add_property(
            descr='Volume name',
            name='name',
            get='name'
        )

        self.add_property(
            descr='Volume type',
            name='type',
            get='properties.type',
            enum=['VT9P']
        )

        self.add_property(
            descr='Destination path',
            name='destination',
            get='properties.destination'
        )

        self.add_property(
            descr='Automatically create storage',
            name='auto',
            get='properties.auto',
            type=ValueType.BOOLEAN
        )

        self.primary_key = self.get_mapping('name')


class VMSnapshotsNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context, parent):
        super(VMSnapshotsNamespace, self).__init__(name, context)
        self.parent = parent
        self.entity_subscriber_name = 'vm.snapshot'
        self.create_task = 'vm.snapshot.create'
        self.update_task = 'vm.snapshot.update'
        self.delete_task = 'vm.snapshot.delete'
        self.required_props = ['name']
        self.primary_key_name = 'name'
        if self.parent.entity:
            self.extra_query_params = [('parent.id', '=', self.parent.entity['id'])]

        self.skeleton_entity = {
            'description': ''
        }

        self.add_property(
            descr='VM snapshot name',
            name='name',
            get='name',
            list=True
        )

        self.add_property(
            descr='Description',
            name='description',
            get='description',
            list=True
        )

        self.primary_key = self.get_mapping('name')

        self.entity_commands = lambda this: {
            'publish': PublishVMCommand(this),
            'rollback': RollbackVMCommand(this)
        }

    def commands(self):
        cmds = super(VMSnapshotsNamespace, self).commands()
        cmds.update({'create': CreateVMSnapshotCommand(self)})
        return cmds


@description("Creates VM snapshot")
class CreateVMSnapshotCommand(Command):
    """
    Usage: create <name> description=<description>

    Example: create mysnap
             create mysnap description="My first VM snapshot"

    Creates a snapshot of configuration and state of selected VM.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args and not kwargs:
            raise CommandException(_("create requires more arguments, see 'help create' for more information"))
        if len(args) > 1:
            raise CommandException(_("Wrong syntax for create, see 'help create' for more information"))

        if len(args) == 1:
            if 'name' in kwargs:
                raise CommandException(_("Both implicit and explicit 'name' parameters are specified."))
            else:
                kwargs[self.parent.primary_key.name] = args.pop(0)

        if 'name' not in kwargs:
            raise CommandException(_('Please specify a name for your snapshot'))
        else:
            name = kwargs.pop('name')

        descr = kwargs.pop('description', '')

        context.submit_task(
            self.parent.create_task,
            self.parent.parent.entity['id'],
            name,
            descr
        )

    def complete(self, context, **kwargs):
        return [
            NullComplete('name='),
            NullComplete('description=')
        ]


@description("Publishes VM snapshot")
class PublishVMCommand(Command):
    """
    Usage: publish name=<name> author=<author> mail=<mail>
                   description=<description>

    Example: publish my_template
             publish name=my_template author=Author mail=author@authormail.com
                     description="My template"

    Publishes VM snapshot over IPFS as an instantiable template.
    After publishing shareable IPFS link can be found by typing:
    /vm template my_template get hash
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args and not kwargs:
            raise CommandException(_("publish requires more arguments, see 'help publish' for more information"))
        if len(args) > 1:
            raise CommandException(_("Wrong syntax for publish, see 'help publish' for more information"))

        if len(args) == 1:
            if 'name' in kwargs:
                raise CommandException(_("Both implicit and explicit 'name' parameters are specified."))
            else:
                kwargs['name'] = args.pop(0)

        if 'name' not in kwargs:
            raise CommandException(_('Please specify a name for your template'))

        context.submit_task(
            'vm.snapshot.publish',
            self.parent.entity['id'],
            kwargs.get('name', ''),
            kwargs.get('author', ''),
            kwargs.get('mail', ''),
            kwargs.get('description', ''),
        )

    def complete(self, context, **kwargs):
        return [
            NullComplete('name='),
            NullComplete('author='),
            NullComplete('mail='),
            NullComplete('description=')
        ]


@description("Returns VM to previously saved state")
class RollbackVMCommand(Command):
    """
    Usage: rollback

    Example: rollback

    Returns VM to previously saved state of VM snapshot.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        context.submit_task(
            'vm.snapshot.rollback',
            self.parent.entity['id'],
        )


@description("Container templates operations")
class TemplateNamespace(RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(TemplateNamespace, self).__init__(name, context)
        self.query_call = 'vm.template.query'
        self.primary_key_name = 'template.name'
        self.allow_create = False

        self.skeleton_entity = {
            'devices': [],
            'config': {}
        }

        self.add_property(
            descr='Name',
            name='name',
            get='template.name',
            usersetable=False,
            list=True
        )

        self.add_property(
            descr='Description',
            name='description',
            get='template.description',
            usersetable=False,
            list=True
        )

        self.add_property(
            descr='Source',
            name='source',
            get='template.driver',
            usersetable=False,
            list=True
        )

        self.add_property(
            descr='Size',
            name='size',
            get='template.fetch_size',
            usersetable=False,
            list=True,
            type=ValueType.SIZE
        )

        self.add_property(
            descr='IPFS hash',
            name='hash',
            get='template.hash',
            usersetable=False,
            list=False,
            condition=lambda e: get(e, 'template.driver') == 'ipfs'
        )

        self.add_property(
            descr='Created at',
            name='created_at',
            get='template.created_at',
            usersetable=False,
            list=False,
            type=ValueType.TIME
        )

        self.add_property(
            descr='Updated at',
            name='updated_at',
            get='template.updated_at',
            usersetable=False,
            list=True,
            type=ValueType.TIME
        )

        self.add_property(
            descr='Author',
            name='author',
            get='template.author',
            usersetable=False,
            list=False
        )

        self.add_property(
            descr='Memory size (MB)',
            name='memsize',
            get='config.memsize',
            usersetable=False,
            list=False,
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='CPU cores',
            name='cores',
            get='config.ncpus',
            usersetable=False,
            list=False,
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Boot device',
            name='boot_device',
            get='config.boot_device',
            usersetable=False,
            list=False
        )

        self.add_property(
            descr='Bootloader type',
            name='bootloader',
            get='config.bootloader',
            list=False,
            usersetable=False,
            enum=['BHYVELOAD', 'GRUB']
        )

        self.add_property(
            descr='Template images cached',
            name='cached',
            get='template.cached',
            usersetable=False,
            list=False,
            type=ValueType.BOOLEAN
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = self.get_entity_commands

    def get_entity_commands(self, this):
        this.load() if hasattr(this, 'load') else None
        commands = {
            'download': DownloadImagesCommand(this),
            'readme': ReadmeCommand(this)
        }

        if hasattr(this, 'entity') and this.entity is not None:
            template = this.entity.get('template')
            if template:
                if template.get('cached', False):
                    commands['delete_cache'] = DeleteImagesCommand(this)

                if template.get('driver') != 'git':
                    commands['delete'] = DeleteTemplateCommand(this)

        return commands


@description("Downloads VM images to the local cache")
class DownloadImagesCommand(Command):
    """
    Usage: download

    Example: download

    Downloads VM template images to the local cache.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs, filtering=None):
        context.submit_task('vm.cache.update', self.parent.entity['template']['name'])


@description("Shows readme entry of selected VM template")
class ReadmeCommand(Command):
    """
    Usage: readme

    Example: readme

    Shows readme entry of selected VM
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs, filtering=None):
        if self.parent.entity['template'].get('readme'):
            return Sequence(self.parent.entity['template']['readme'])
        else:
            return Sequence("Selected template does not have readme entry")


@description("Deletes VM images from the local cache")
class DeleteImagesCommand(Command):
    """
    Usage: delete_cache

    Example: delete_cache

    Deletes VM template images from the local cache.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs, filtering=None):
        context.submit_task('vm.cache.delete', self.parent.entity['template']['name'])


@description("Deletes VM images and VM template from the local cache")
class DeleteTemplateCommand(Command):
    """
    Usage: delete

    Example: delete

    Deletes VM template images and VM template from the local cache.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs, filtering=None):
        context.submit_task('vm.template.delete', self.parent.entity['template']['name'])
        context.ml.cd_up()


def _init(context):
    context.attach_namespace('/', VMNamespace('vm', context))
    context.map_tasks('vm.*', VMNamespace)
