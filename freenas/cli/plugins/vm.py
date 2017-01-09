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
from freenas.cli.output import Sequence, Table
from freenas.cli.namespace import (
    EntityNamespace, Command, NestedObjectLoadMixin, NestedObjectSaveMixin, EntitySubscriberBasedLoadMixin,
    RpcBasedLoadMixin, TaskBasedSaveMixin, description, CommandException, ConfigNamespace, BaseVariantMixin,
    Namespace
)
from freenas.cli.output import Object, ValueType, get_humanized_size
from freenas.cli.utils import TaskPromise, post_save, EntityPromise, get_item_stub, get_related, set_related
from freenas.utils import first_or_default
from freenas.utils.query import get, set
from freenas.cli.complete import NullComplete, EntitySubscriberComplete, RpcComplete, MultipleSourceComplete
from freenas.cli.console import Console


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


class StartVMCommand(Command):
    """
    Usage: start

    Examples:
        start

    Starts the VM
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        tid = context.submit_task('vm.start', self.parent.entity['id'])
        return TaskPromise(context, tid)


class StopVMCommand(Command):
    """
    Usage: stop

    Examples:
        stop

    Gracefully shutsdown the VM.
    Note: This only works for some compatible OS's.
    If this command fails try the `kill` command.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        tid =context.submit_task('vm.stop', self.parent.entity['id'])
        return TaskPromise(context, tid)


class KillVMCommand(Command):
    """
    Usage: kill

    Examples:
        kill

    Abruptly kills a stuck (or one that does not support the gracefull shutdown) VM.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        tid = context.submit_task('vm.stop', self.parent.entity['id'], True)
        return TaskPromise(context, tid)


class RebootVMCommand(Command):
    """
    Usage: reboot force=<force>

    Examples:
        reboot
        reboot force=yes

    Reboots the VM
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        force = kwargs.get('force', False)
        tid = context.submit_task('vm.reboot', self.parent.entity['id'], force)
        return TaskPromise(context, tid)


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


@description("Clones a VM into a new VM instance")
class CloneVMCommand(Command):
    """
    Usage: clone name=<name>

    Example: clone name=test_vm_clone

    Clones a VM into a new VM instance.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        new_name = kwargs.pop('name')
        if not new_name:
            raise CommandException(_('Name of a new VM has to be specified'))

        tid = context.submit_task(
            'vm.clone',
            self.parent.entity['id'],
            new_name
        )

        return TaskPromise(context, tid)


class ConsoleVGACommand(Command):
    """
    Usage: console_vga

    Examples: console_vga

    Returns a link to the VM's VGA console.
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

    Examples:
        vm import name=freebsd-12-zfs volume=jhol

    Imports a VM from an existing pool.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args and not kwargs:
            raise CommandException(_("import requires more arguments, see 'help import' for more information"))
        if len(args) > 1:
            raise CommandException(_("Wrong syntax for import, see 'help import' for more information"))

        if len(args) == 1:
            if 'name' in kwargs:
                raise CommandException(_("Both positional and keyword 'name' parameters are specified."))
            else:
                kwargs['name'] = args.pop(0)

        if 'name' not in kwargs:
            raise CommandException(_("Please specify the name of VM."))
        else:
            name = kwargs.pop('name')

        volume = kwargs.get('volume', None)
        if not volume:
            raise CommandException(_("Please specify which volume is containing a VM being imported."))

        ns = get_item_stub(context, self.parent, name)

        tid = context.submit_task('vm.import', name, volume, callback=lambda s, t: post_save(ns, s, t))
        return EntityPromise(context, tid, ns)

    def complete(self, context, **kwargs):
        return [
            NullComplete('name='),
            EntitySubscriberComplete('volume=', 'volume', lambda i: i['id'])
        ]


@description("Configure system-wide virtualization behavior")
class VMConfigNamespace(ConfigNamespace):
    def __init__(self, name, context):
        super(VMConfigNamespace, self).__init__(name, context)
        self.config_call = "vm.config.get_config"
        self.update_task = 'vm.config.update'

        def get_templates(o):
            result = []
            for i in o['additional_templates']:
                result.append(i['url'])

            return result

        def set_templates(o, v):
            template_sources = []
            for i in v:
                if i:
                    template_sources.append({
                        'id': i.replace('/', '-'),
                        'driver': 'git',
                        'url': i
                    })

            o['additional_templates'] = template_sources

        self.add_property(
            descr='Management network',
            name='management_network',
            get='network.management',
            usage=_("The address range for the vm management(internal) network")
        )

        self.add_property(
            descr='NAT network',
            name='nat_network',
            get='network.nat',
            usage=_("The address range from which VM's with natted nics will be allocated ips")
        )

        self.add_property(
            descr='Additional templates',
            name='additional_templates',
            get=get_templates,
            set=set_templates,
            type=ValueType.ARRAY,
            usage=_("Array of additional VM template Git repositories")
        )


class VMDatastoreLocalPropertiesMixin(BaseVariantMixin):
    def add_properties(self):
        super(VMDatastoreLocalPropertiesMixin, self).add_properties()

        self.add_property(
            descr='Path',
            name='local_path',
            get='properties.path',
            list=False,
            condition=lambda o: o['type'] == 'local'
        )


class VMDatastoreNFSPropertiesMixin(BaseVariantMixin):
    def add_properties(self):
        super(VMDatastoreNFSPropertiesMixin, self).add_properties()

        self.add_property(
            descr='Path',
            name='nfs_path',
            get='properties.path',
            list=False,
            condition=lambda o: o['type'] == 'nfs'
        )

        self.add_property(
            descr='Address',
            name='nfs_address',
            get='properties.address',
            list=False,
            condition=lambda o: o['type'] == 'nfs'
        )

        self.add_property(
            descr='NFS version',
            name='nfs_version',
            get='properties.version',
            enum=['NFSV3', 'NFSV4'],
            list=False,
            condition=lambda o: o['type'] == 'nfs'
        )


@description("Configure virtual machine datastores")
class VMDatastoreNamespace(
    TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, VMDatastoreLocalPropertiesMixin,
    VMDatastoreNFSPropertiesMixin, EntityNamespace
):
    def __init__(self, name, context):
        super(VMDatastoreNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'vm.datastore'
        self.create_task = 'vm.datastore.create'
        self.update_task = 'vm.datastore.update'
        self.delete_task = 'vm.datastore.delete'
        self.primary_key_name = 'name'
        self.skeleton_entity = {
            'type': None
        }

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            list=True
        )

        self.add_property(
            descr='Type',
            name='type',
            get='type',
            set='type',
            usersettable=False,
            list=True
        )

        self.add_properties()
        self.primary_key = self.get_mapping('name')


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
        self.required_props = ['name', 'datastore']
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
            list=True,
            usage=_("Name of the VM")
        )

        self.add_property(
            descr='Template name',
            name='template',
            get='template.name',
            complete=RpcComplete('template=', 'vm.template.query', lambda i: get(i, 'template.name')),
            usage=_("Name of the template used to create the VM from")
        )

        self.add_property(
            descr='State',
            name='state',
            get='status.state',
            set=None,
            usage=_("The current state of the VM [RUNNING|STOPPED]")
        )

        self.add_property(
            descr='Datastore',
            name='datastore',
            get=lambda o: get_related(self.context, 'vm.datastore', o, 'target'),
            set=lambda o, v: set_related(self.context, 'vm.datastore', o, 'target', v),
            createsetable=True,
            usersetable=False,
            complete=EntitySubscriberComplete('datastore=', 'vm.datastore', lambda i: i['name']),
            usage=_("The volume on which the VM is stored")
        )

        self.add_property(
            descr='Description',
            name='description',
            get='description',
            list=False,
            usage=_("Its a description D'OH!")
        )

        self.add_property(
            descr='Parent',
            name='parent',
            get=lambda o: self.context.entity_subscribers['vm'].query(('id', '=', o['parent']), single=True, select=name),
            usersetable=False,
            list=False,
            usage=_("Parent of a VM. Set to name of a other VM when VM is a clone")
        )

        self.add_property(
            descr='Memory size (MB)',
            name='memsize',
            get=lambda o: get(o, 'config.memsize') * 1024 * 1024,
            set=set_memsize,
            list=True,
            type=ValueType.SIZE,
            usage=_("Size of the Memory allocated to the VM")
        )

        self.add_property(
            descr='CPU cores',
            name='cores',
            get='config.ncpus',
            list=True,
            type=ValueType.NUMBER,
            usage=_("Number of cpu cores assigned to the VM")
        )

        self.add_property(
            descr='Start on boot',
            name='autostart',
            get='config.autostart',
            type=ValueType.BOOLEAN,
            usage=_("Property that controls whether the VM is autostarted on System Boot up")
        )

        self.add_property(
            descr='Boot device',
            name='boot_device',
            get='config.boot_device',
            list=False,
            usage=_("The device from the devices namespace from which to boot from"),
            complete=RpcComplete(
                'boot_device=',
                'vm.query',
                lambda o: [i['name'] for i in o['devices'] if i['type'] in ('DISK', 'CDROM')]
            )
        )

        self.add_property(
            descr='Boot directory (for GRUB)',
            name='boot_directory',
            get='config.boot_directory',
            list=False,
            usage=_("The directory in VM's dataset under the files directory that contains grub.cfg")
        )

        self.add_property(
            descr='Boot partition (for GRUB)',
            name='boot_partition',
            get='config.boot_partition',
            list=False,
            usage=_("The partition on the os's boot device to boot from (i.e. msdos1 for the first partition of a BIOS partition layout)")
        )

        self.add_property(
            descr='Bootloader type',
            name='bootloader',
            get='config.bootloader',
            list=False,
            enum=['BHYVELOAD', 'GRUB', 'UEFI', 'UEFI_CSM'],
            usage=_("Type of Bootloader"),
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
            ],
            usage=_("Type of the guest os (i.e. freebsd32, windows64, linux64, etc.)")
        )

        self.add_property(
            descr='Cloud-init data',
            name='cloud_init',
            get='config.cloud_init',
            list=False,
            usage=_("Bread goes in, Toast comes out. You can't explain that (or this!)")
        )

        self.add_property(
            descr='Enabled',
            name='enabled',
            get='enabled',
            list=True,
            type=ValueType.BOOLEAN,
            usage=_("Enables/Disables the VM")
        )

        self.add_property(
            descr='Immutable',
            name='immutable',
            get='immutable',
            list=False,
            usersetable=False,
            type=ValueType.BOOLEAN,
            usage=_("Sets VM as immutable")
        )

        self.add_property(
            descr='Readme',
            name='readme',
            get='config.readme',
            set='config.readme',
            list=False,
            type=ValueType.TEXT_FILE,
            usage=_("Information about this VM including instructions on how to login, username and password, etc.")
        )

        self.add_property(
            descr='NAT IP address',
            name='nat_ip',
            get='status.nat_lease.client_ip',
            set=None,
            list=False,
            condition=lambda o: get(o, 'status.state') != 'STOPPED' and get(o, 'status.nat_lease'),
            usage=_("Displays the natted IP address of the VM (if any)")
        )

        self.add_property(
            descr='Logging',
            name='logging',
            get='config.logging',
            list=False,
            type=ValueType.SET
        )

        self.add_property(
            descr='VM tools available',
            name='vm_tools_available',
            get='status.vm_tools_available',
            set=None,
            list=False,
            condition=lambda o: get(o, 'status.state') != 'STOPPED',
            usage=_("Shows whether freenas-vm-tools are running on the VM"),
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Guest health',
            name='health',
            get='status.health',
            set=None,
            list=False,
            condition=lambda o: get(o, 'status.state') != 'STOPPED',
            usage=_("Shows guest health status")
        )

        self.primary_key = self.get_mapping('name')
        self.entity_namespaces = self.get_entity_namespaces
        self.entity_commands = self.get_entity_commands

        self.extra_commands = {
            'import': ImportVMCommand(self)
        }

    def namespaces(self):
        yield TemplateNamespace('template', self.context)
        yield VMDatastoreNamespace('datastore', self.context)
        yield VMConfigNamespace('config', self.context)
        for namespace in super(VMNamespace, self).namespaces():
            yield namespace

    def get_entity_namespaces(self, this):
        return [
            VMDeviceNamespace('device', self.context, this),
            VMVolumeNamespace('volume', self.context, this),
            VMSnapshotsNamespace('snapshot', self.context, this),
            VMGuestNamespace('guest', self.context, this)
        ]

    def get_entity_commands(self, this):
        commands = {
            'start': StartVMCommand(this),
            'stop': StopVMCommand(this),
            'kill': KillVMCommand(this),
            'reboot': RebootVMCommand(this),
            'console': ConsoleCommand(this),
            'clone': CloneVMCommand(this),
            'readme': ReadmeCommand(this, 'config'),
            'guest_info': ShowGuestInfoCommand(this)
        }

        if hasattr(this, 'entity') and this.entity is not None:
            if first_or_default(lambda d: d['type'] == 'GRAPHICS', this.entity['devices']):
                commands['console_vga'] = ConsoleVGACommand(this)

        return commands


class VMGuestNamespace(Namespace):
    def __init__(self, name, context, parent):
        super(VMGuestNamespace, self).__init__(name)
        self.context = context
        self.parent = parent

    def commands(self):
        return {
            'show': ShowGuestInfoCommand(self.parent),
            'ls': GuestLsCommand(self.parent),
            'cat': GuestCatCommand(self.parent),
            'exec': GuestExecCommand(self.parent)
        }


class VMDeviceGraphicsPropertiesMixin(BaseVariantMixin):
    """
    The VM Device Graphics namespace provides commands for managing graphics resources
    available on selected virtual machine
    """
    def add_properties(self):
        super(VMDeviceGraphicsPropertiesMixin, self).add_properties()

        def set_resolution(o, v):
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

        self.add_property(
            descr='Framebuffer resolution',
            name='graphics_resolution',
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
            usage=_("Resolution of the graphics device attached to the VM (example: 1024x768)"),
            condition=lambda o: o['type'] == 'GRAPHICS',
        )

        self.add_property(
            descr='VNC server enabled',
            name='graphics_vnc_enabled',
            get='properties.vnc_enabled',
            list=False,
            type=ValueType.BOOLEAN,
            usage=_("Flag controlling wether the VNC server to VM's framebuffer is enabled or not"),
            condition=lambda o: o['type'] == 'GRAPHICS',
        )

        self.add_property(
            descr='VNC server port',
            name='graphics_vnc_port',
            get='properties.vnc_port',
            list=False,
            set=set_vnc_port,
            type=ValueType.NUMBER,
            usage=_(
                "Port to be used for the VNC server (if enabled) of VM. "
                "Please ensure a uniqure port number (one that is not already in use)"),
            condition=lambda o: o['type'] == 'GRAPHICS',
        )

    @staticmethod
    def get_humanized_summary(o):
        return "VGA device with resolution {0}".format(get(o, 'properties.resolution'))


class VMDeviceUsbPropertiesMixin(BaseVariantMixin):
    """
    The VM Device Usb namespace provides commands for managing USB resources
    available on selected virtual machine
    """
    def add_properties(self):
        super(VMDeviceUsbPropertiesMixin, self).add_properties()

        self.add_property(
            descr='Emulated device type',
            name='usb_device_type',
            get='properties.device',
            enum=['tablet'],
            list=False,
            usage=_("Type of emulated usb device (currently only 'tablet' is supported)"),
            condition=lambda o: o['type'] == 'USB',
        )

    @staticmethod
    def get_humanized_summary(o):
        return "USB {0} device".format(get(o, 'properties.device'))


class VMDeviceNicPropertiesMixin(BaseVariantMixin):
    """
    The VM Device Nic namespace provides commands for managing NIC resources
    available on selected virtual machine
    """
    def add_properties(self):
        super(VMDeviceNicPropertiesMixin, self).add_properties()

        self.add_property(
            descr='NIC mode',
            name='nic_mode',
            get='properties.mode',
            enum=['NAT', 'BRIDGED', 'MANAGEMENT'],
            list=False,
            usage=_("Mode of NIC device [NAT|BRIDGED|MANAGEMENT]"),
            condition=lambda o: o['type'] == 'NIC',
        )

        self.add_property(
            descr='Emulated device type',
            name='nic_device_type',
            get='properties.device',
            enum=['VIRTIO', 'E1000', 'NE2K'],
            list=False,
            usage=_("The type of virtual NIC emulation [VIRTIO|E1000|NE2K]"),
            condition=lambda o: o['type'] == 'NIC',
        )

        self.add_property(
            descr='Bridge with',
            name='nic_bridge',
            get='properties.bridge',
            list=False,
            complete=MultipleSourceComplete(
                'nic_bridge=', (
                    EntitySubscriberComplete('bridge=', 'network.interface', lambda i: i['id']),
                    EntitySubscriberComplete('bridge=', 'network.interface', lambda i: i['name'])
                ),
                extra=['default']
            ),
            usage=_("The interface to bridge NIC device with (if this NIC device is in BRIDGED mode)"),
            condition=lambda o: o['type'] == 'NIC',
        )

        self.add_property(
            descr='MAC address',
            name='nic_macaddr',
            get='properties.link_address',
            list=False,
            usage=_("Mac address of NIC device"),
            condition=lambda o: o['type'] == 'NIC',
        )

    @staticmethod
    def get_humanized_summary(o):
        if get(o, 'properties.bridge'):
            return "{0} NIC bridged to {1}".format(get(o, 'properties.device'), get(o, 'properties.bridge'))

        return "{0} NIC".format(get(o, 'properties.device'))


class VMDeviceDiskPropertiesMixin(BaseVariantMixin):
    """
    The VM Device Disk namespace provides commands for managing disk resources
    available on selected virtual machine
    """
    def add_properties(self):
        super(VMDeviceDiskPropertiesMixin, self).add_properties()

        self.add_property(
            descr='Disk mode',
            name='disk_mode',
            get='properties.mode',
            enum=['AHCI', 'VIRTIO'],
            list=False,
            usage=_("The virtual disk emulation mode [AHCI|VIRTIO]"),
            condition=lambda o: o['type'] == 'DISK',
        )

        self.add_property(
            descr='Disk size',
            name='disk_size',
            get='properties.size',
            type=ValueType.SIZE,
            list=False,
            usage=_("States the size of the disk"),
            condition=lambda o: o['type'] == 'DISK',
        )

        self.add_property(
            descr='Target type',
            name='target_type',
            get='properties.target_type',
            list=False,
            enum=['ZVOL', 'FILE', 'DISK'],
            condition=lambda o: o['type'] == 'DISK',
        )

        self.add_property(
            descr='Target path',
            name='target_path',
            get='properties.target_path',
            list=False,
            condition=lambda o: o['type'] == 'DISK',
        )

    @staticmethod
    def get_humanized_summary(o):
        return "{0} {1} DISK".format(
            get_humanized_size(get(o, 'properties.size')),
            get(o, 'properties.mode')
        )


class VMDeviceCdromPropertiesMixin(BaseVariantMixin):
    """
    The VM Device Cdrom namespace provides commands for managing cdrom device resources
    available on selected virtual machine
    """
    def add_properties(self):
        self.add_property(
            descr='Image path',
            name='cdrom_image_path',
            get='properties.path',
            list=False,
            usage=_("The path on the filesystem where the image file(iso, img, etc.) for this CDROM device lives"),
            condition=lambda o: o['type'] == 'CDROM',
        )

    @staticmethod
    def get_humanized_summary(o):
        return "CDROM with image: {0}".format(get(o, 'properties.path'))


class VMDeviceNamespace(
    NestedObjectLoadMixin, NestedObjectSaveMixin, EntityNamespace,
    VMDeviceGraphicsPropertiesMixin, VMDeviceDiskPropertiesMixin,
    VMDeviceUsbPropertiesMixin, VMDeviceNicPropertiesMixin, VMDeviceCdromPropertiesMixin,
    BaseVariantMixin
):
    """
    VM Device namespace contains sub-namespaces for each of available VM Device types
    """
    def __init__(self, name, context, parent):
        def get_humanized_summary(o):
            return self.humanized_summaries[o['type']](o)

        super(VMDeviceNamespace, self).__init__(name, context)
        self.primary_key_name = 'name'
        self.parent = parent
        self.parent_path = 'devices'
        self.extra_query_params = [('type', 'in', ('GRAPHICS', 'CDROM', 'NIC', 'USB', 'DISK'))]
        self.required_props = ['name']
        self.skeleton_entity = {
            'name': None,
            'type': None,
            'properties': {},
        }

        self.humanized_summaries = {
            'DISK': VMDeviceDiskPropertiesMixin.get_humanized_summary,
            'CDROM': VMDeviceCdromPropertiesMixin.get_humanized_summary,
            'NIC': VMDeviceNicPropertiesMixin.get_humanized_summary,
            'USB': VMDeviceUsbPropertiesMixin.get_humanized_summary,
            'GRAPHICS': VMDeviceGraphicsPropertiesMixin.get_humanized_summary
        }

        self.localdoc['CreateEntityCommand'] = ("""\
                   Usage: create name=<device-name> property=<value>

                   Examples:
                       create name=framebuffer type=GRAPHICS graphics_resolution=1280,1024
                       create name=mynic type=NIC nic_mode=NAT nic_device_type=E1000
                       create name=mydisk type=DISK disk_mode=AHCI disk_size=1G
                       create name=mycdrom type=CDROM cdrom_image_path=/path/to/image
                       create name=mytablet type=USB usb_device_type=tablet

                   Creates device with selected properties.
                   For full list of propertise type 'help properties'""")

        self.entity_localdoc['DeleteEntityCommand'] = ("""\
                    Usage: delete

                    Deletes the specified device.""")

        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all VM devices. Optionally, filter or sort by property.

            Examples:
                show
                show | search name == foo""")

        self.add_property(
            descr='Device name',
            name='name',
            get='name',
            set='name',
            list=True,
            usage=_("The path on the filesystem where the image file(iso, img, etc.) for this CDROM device lives")
        )

        self.add_property(
            descr='Device type',
            name='type',
            get='type',
            set='type',
            list=True,
            enum=['GRAPHICS', 'NIC', 'DISK', 'CDROM', 'USB']
        )

        self.add_property(
            descr="Device summary",
            name='device_summary',
            get=get_humanized_summary,
            set=None,
            list=True,
        )

        self.add_properties()
        self.primary_key = self.get_mapping('name')

    def save(self, this, new=False):
        types = {
            'DISK': 'vm-device-disk',
            'CDROM': 'vm-device-cdrom',
            'NIC': 'vm-device-nic',
            'USB': 'vm-device-usb',
            'GRAPHICS': 'vm-device-graphics'
        }

        if new:
            this.entity['properties']['%type'] = types[this.entity['type']]

        return super(VMDeviceNamespace, self).save(this, new)


class VMVolumeNamespace(NestedObjectLoadMixin, NestedObjectSaveMixin, EntityNamespace):
    """
    The VM Volume namespace provides commands for creating and managing volume resources
    available on selected virtual machine
    """
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
        self.required_props = ['name']
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
            get='name',
            usage=_("Name of the Volume")
        )

        self.add_property(
            descr='Volume type',
            name='type',
            get='properties.type',
            enum=['VT9P'],
            usage=_("I'd tell you, but then I'd have to kill you")
        )

        self.add_property(
            descr='Destination path',
            name='destination',
            get='properties.destination',
            usage=_("The path on the filesystem where the volume is stored")
        )

        self.add_property(
            descr='Automatically create storage',
            name='auto',
            get='properties.auto',
            type=ValueType.BOOLEAN,
            usage=_("Flag which controls automatic creation of storage")
        )

        self.primary_key = self.get_mapping('name')


class VMSnapshotsNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The VM Snapshoot namespace provides commands for creating and managing snapshots of the
    selected VM. It also provides commands to either publish a particular snapshot as well
    as rollback to a selected one.
    """
    def __init__(self, name, context, parent=None):
        super(VMSnapshotsNamespace, self).__init__(name, context)
        self.parent = parent
        self.entity_subscriber_name = 'vm.snapshot'
        self.create_task = 'vm.snapshot.create'
        self.update_task = 'vm.snapshot.update'
        self.delete_task = 'vm.snapshot.delete'
        self.required_props = ['name']
        self.primary_key_name = 'name'
        if self.parent and self.parent.entity:
            self.extra_query_params = [('parent.id', '=', self.parent.entity.get('id'))]

        self.skeleton_entity = {
            'description': ''
        }

        self.add_property(
            descr='VM snapshot name',
            name='name',
            get='name',
            list=True,
            usage=_("Name of the VM snapshot")
        )

        self.add_property(
            descr='Description',
            name='description',
            get='description',
            list=True,
            usage=_("Description of the VM snapshot")
        )

        self.primary_key = self.get_mapping('name')

        self.entity_commands = lambda this: {
            'publish': PublishVMCommand(this),
            'rollback': RollbackVMCommand(this),
            'clone': CloneVMSnapshotCommand(this)
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
            raise CommandException(_(
                "create requires more arguments, see 'help create' for more information"
            ))
        if len(args) > 1:
            raise CommandException(_(
                "Wrong syntax for create, see 'help create' for more information"
            ))

        if len(args) == 1:
            if 'name' in kwargs:
                raise CommandException(_(
                    "Both implicit and explicit 'name' parameters are specified."
                ))
            else:
                kwargs[self.parent.primary_key.name] = args.pop(0)

        if 'name' not in kwargs:
            raise CommandException(_('Please specify a name for your snapshot'))
        else:
            name = kwargs.pop('name')

        descr = kwargs.pop('description', '')

        ns = get_item_stub(context, self.parent, name)

        tid = context.submit_task(
            self.parent.create_task,
            self.parent.parent.entity['id'],
            name,
            descr,
            callback=lambda s, t: post_save(ns, s, t)
        )

        return EntityPromise(context, tid, ns)

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
            raise CommandException(_(
                "publish requires more arguments, see 'help publish' for more information"
            ))
        if len(args) > 1:
            raise CommandException(_(
                "Wrong syntax for publish, see 'help publish' for more information"
            ))

        if len(args) == 1:
            if 'name' in kwargs:
                raise CommandException(_(
                    "Both implicit and explicit 'name' parameters are specified."
                ))
            else:
                kwargs['name'] = args.pop(0)

        if 'name' not in kwargs:
            raise CommandException(_('Please specify a name for your template'))

        tid = context.submit_task(
            'vm.snapshot.publish',
            self.parent.entity['id'],
            kwargs.get('name', ''),
            kwargs.get('author', ''),
            kwargs.get('mail', ''),
            kwargs.get('description', ''),
        )

        return TaskPromise(context, tid)

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
        tid = context.submit_task(
            'vm.snapshot.rollback',
            self.parent.entity['id'],
        )

        return TaskPromise(context, tid)


@description("Clones a VM snapshot into a new VM instance")
class CloneVMSnapshotCommand(Command):
    """
    Usage: clone name=<name>

    Example: clone name=test_vm_clone

    Clones a VM snapshot into a new VM instance.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        new_name = kwargs.pop('name')
        if not new_name:
            raise CommandException(_('Name of a new VM has to be specified'))

        tid = context.submit_task(
            'vm.snapshot.clone',
            self.parent.entity['id'],
            new_name
        )

        return TaskPromise(context, tid)


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
            list=True,
            usage=_("Name of the template")
        )

        self.add_property(
            descr='Description',
            name='description',
            get='template.description',
            usersetable=False,
            list=True,
            usage=_("Description of template")
        )

        self.add_property(
            descr='Source',
            name='source',
            get='template.driver',
            usersetable=False,
            list=True,
            usage=_("The source of the template's json file (i.e. git, ipfs, etc.)")
        )

        self.add_property(
            descr='Size',
            name='size',
            get='template.fetch_size',
            usersetable=False,
            list=True,
            type=ValueType.SIZE,
            usage=_("Size of the template")
        )

        self.add_property(
            descr='IPFS hash',
            name='hash',
            get='template.hash',
            usersetable=False,
            list=False,
            condition=lambda e: get(e, 'template.driver') == 'ipfs',
            usage=_("The IPFS has of temaplate")
        )

        self.add_property(
            descr='Created at',
            name='created_at',
            get='template.created_at',
            usersetable=False,
            list=False,
            type=ValueType.TIME,
            usage=_("Date and time of template's creation)")
        )

        self.add_property(
            descr='Updated at',
            name='updated_at',
            get='template.updated_at',
            usersetable=False,
            list=True,
            type=ValueType.TIME,
            usage=_("Date and time template was last updated)")
        )

        self.add_property(
            descr='Author',
            name='author',
            get='template.author',
            usersetable=False,
            list=False,
            usage=_("Person who penned this template")
        )

        self.add_property(
            descr='Memory size (MB)',
            name='memsize',
            get='config.memsize',
            usersetable=False,
            list=False,
            type=ValueType.NUMBER,
            usage=_("Size of the Memory to be used by template")
        )

        self.add_property(
            descr='CPU cores',
            name='cores',
            get='config.ncpus',
            usersetable=False,
            list=False,
            type=ValueType.NUMBER,
            usage=_("Number of cpu cores to be used by template")
        )

        self.add_property(
            descr='Boot device',
            name='boot_device',
            get='config.boot_device',
            usersetable=False,
            list=False,
            usage=_("Specifies the boot device (from the list of template devices)"),
        )

        self.add_property(
            descr='Bootloader type',
            name='bootloader',
            get='config.bootloader',
            list=False,
            usersetable=False,
            enum=['BHYVELOAD', 'GRUB', 'UEFI', 'UEFI_CSM'],
            usage=_("Type of Bootloader"),
        )

        self.add_property(
            descr='Template images cached on',
            name='cached_on',
            get='template.cached_on',
            usersetable=False,
            list=False,
            type=ValueType.SET,
            usage=_("List of datastores which store the template in their local cache")
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = self.get_entity_commands

    def get_entity_commands(self, this):
        this.load() if hasattr(this, 'load') else None
        commands = {
            'download': DownloadImagesCommand(this),
            'readme': ReadmeCommand(this, 'template')
        }

        if hasattr(this, 'entity') and this.entity is not None:
            template = this.entity.get('template')
            if template:
                if template.get('cached', False):
                    commands['delete_cache'] = DeleteImagesCommand(this)

                if template.get('driver') != 'git':
                    commands['delete'] = DeleteTemplateCommand(this)

        return commands

    def commands(self):
        commands = super(TemplateNamespace, self).commands()
        commands['flush_cache'] = FlushImagesCommand(self)
        return commands


@description("Downloads VM images to the local cache")
class DownloadImagesCommand(Command):
    """
    Usage: download volume=<volume>

    Example: download volume=tank

    Downloads VM template images to the local cache.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs, filtering=None):
        volume = kwargs.get('volume')
        if not volume:
            raise CommandException(_('Target volume has to be specified'))
        tid = context.submit_task('vm.cache.update', self.parent.entity['template']['name'], volume)
        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            EntitySubscriberComplete('volume=', 'volume', lambda i: i['id'])
        ]


@description("Shows readme entry of selected VM template")
class ReadmeCommand(Command):
    """
    Usage: readme

    Examples: readme

    Shows readme entry of selected VM
    """
    def __init__(self, parent, key):
        self.key = key
        self.parent = parent

    def run(self, context, args, kwargs, opargs, filtering=None):
        return Sequence(self.parent.entity[self.key].get('readme', 'Selected template does not have readme entry'))


class ShowGuestInfoCommand(Command):
    """
    Usage: show_guest_info
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        guest_info = context.call_sync('vm.get_guest_info', self.parent.entity['id'])

        if guest_info:
            addresses = []
            for name, config in guest_info['interfaces'].items():
                if name.startswith('lo'):
                    continue

                addresses += [i['address'] for i in config['aliases'] if i['af'] != 'LINK']

            return Object(
                Object.Item('Load average', 'load_avg', guest_info['load_avg'], ValueType.ARRAY),
                Object.Item('Network configuration', 'interfaces', addresses, ValueType.SET)
            )


class GuestLsCommand(Command):
    """
    Usage: ls <path>
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        result = context.call_sync('vm.guest_ls', self.parent.entity['id'], args[0])
        return Table(result, [
            Table.Column('Name', 'name'),
            Table.Column('Type', 'type'),
            Table.Column('Size', 'size', ValueType.SIZE)
        ])


class GuestCatCommand(Command):
    """
    Usage: ls <path>
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        return


class GuestExecCommand(Command):
    """
    Usage: ls <path>
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        return context.call_sync('vm.guest_exec', self.parent.entity['id'], args[0], args[1:])


@description("Deletes unused VM images from the local cache")
class DeleteImagesCommand(Command):
    """
    Usage: delete_cache

    Examples: delete_cache

    Deletes unused VM template images from the local cache.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs, filtering=None):
        tid = context.submit_task('vm.cache.delete', self.parent.entity['template']['name'])
        return TaskPromise(context, tid)


@description("Deletes all unused VM images from the local cache")
class FlushImagesCommand(Command):
    """
    Usage: flush_cache

    Examples: flush_cache

    Deletes all unused VM template images from the local cache.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs, filtering=None):
        tid = context.submit_task('vm.cache.flush')
        return TaskPromise(context, tid)


@description("Deletes VM images and VM template from the local cache")
class DeleteTemplateCommand(Command):
    """
    Usage: delete

    Examples: delete

    Deletes VM template images and VM template from the local cache.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs, filtering=None):
        tid = context.submit_task('vm.template.delete', self.parent.entity['template']['name'])
        context.ml.cd_up()
        return TaskPromise(context, tid)


def _init(context):
    context.attach_namespace('/', VMNamespace('vm', context))
    context.map_tasks('vm.*', VMNamespace)
    context.map_tasks('vm.config.*', VMConfigNamespace)
