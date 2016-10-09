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
    RpcBasedLoadMixin, TaskBasedSaveMixin, description, CommandException, ConfigNamespace
)
from freenas.cli.output import ValueType, get_humanized_size
from freenas.cli.utils import TaskPromise, post_save, EntityPromise
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
        try:
            name = args[0]
        except IndexError:
            raise CommandException(_("Please specify the name of VM."))
        volume = kwargs.get('volume', None)
        if not volume:
            raise CommandException(_("Please specify which volume is containing a VM being imported."))

        tid = context.submit_task('vm.import', name, volume, callback=lambda s, t: post_save(self.parent, s, t))
        return EntityPromise(context, tid, self.parent)


@description("Configure system-wide virtualization behavior")
class VMConfigNamespace(ConfigNamespace):
    def __init__(self, name, context):
        super(VMConfigNamespace, self).__init__(name, context)
        self.config_call = "vm.config.get_config"
        self.update_task = 'vm.config.update'

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
            descr='Volume',
            name='volume',
            get='target',
            createsetable=True,
            usersetable=False,
            complete=EntitySubscriberComplete('volume=', 'volume', lambda i: i['id']),
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
            usage=_("Displays the natted ip address of the VM")
        )

        self.primary_key = self.get_mapping('name')
        self.entity_namespaces = self.get_entity_namespaces
        self.entity_commands = self.get_entity_commands

        self.extra_commands = {
            'import': ImportVMCommand(self)
        }

    def namespaces(self):
        yield TemplateNamespace('template', self.context)
        yield VMConfigNamespace('config', self.context)
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
            'readme': ReadmeCommand(this, 'config')
        }

        if hasattr(this, 'entity') and this.entity is not None:
            if first_or_default(lambda d: d['type'] == 'GRAPHICS', this.entity['devices']):
                commands['console_vga'] = ConsoleVGACommand(this)

        return commands


class VMDeviceNamespace(NestedObjectLoadMixin, EntityNamespace):
    """
    VM Device namespace contains sub-namespaces for each of available VM Device types
    """
    def __init__(self, name, context, parent):
        def get_humanized_summary(o):
            return self.humanized_summaries[o['type']](o)

        super(VMDeviceNamespace, self).__init__(name, context)
        self.parent = parent
        self.parent_path = 'devices'
        self.allow_create = False
        self.extra_query_params = [('type', 'in', ('GRAPHICS', 'CDROM', 'NIC', 'USB', 'DISK'))]
        self.has_entities_in_subnamespaces_only = True

        self.humanized_summaries = {
            'DISK': VMDeviceDiskNamespace.get_humanized_summary,
            'CDROM': VMDeviceCdromNamespace.get_humanized_summary,
            'NIC': VMDeviceNicNamespace.get_humanized_summary,
            'USB': VMDeviceUsbNamespace.get_humanized_summary,
            'GRAPHICS': VMDeviceGraphicsNamespace.get_humanized_summary
        }

        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all VM devices of all types. Optionally, filter or sort by property.

            Examples:
                show
                show | search name == foo""")

        self.add_property(
            descr='Device type',
            name='type',
            get=lambda obj: obj['type'].lower(),
            set=None,
            usage=_("Type of VM device (i.e. DISK, CDROM, USB, etc.)")
        )

        self.add_property(
            descr='Device name',
            name='name',
            get='name',
            set=None,
            usage=_("Name of the device")
        )

        self.add_property(
            descr="Device summary",
            name='device_summary',
            get=get_humanized_summary,
            set=None,
            usage=_("Brief Summary of the VM device")
        )

    def load(self):
        pass

    def namespaces(self):
        return [
            VMDeviceGraphicsNamespace('graphics', self.context, self.parent),
            VMDeviceUsbNamespace('usb', self.context, self.parent),
            VMDeviceNicNamespace('nic', self.context, self.parent),
            VMDeviceDiskNamespace('disk', self.context, self.parent),
            VMDeviceCdromNamespace('cdrom', self.context, self.parent)
        ]


class VMDeviceNamespaceBaseClass(NestedObjectLoadMixin, NestedObjectSaveMixin, EntityNamespace):
    def __init__(self, name, context, parent):
        super(VMDeviceNamespaceBaseClass, self).__init__(name, context)
        self.parent = parent
        self.primary_key_name = 'name'
        self.parent_path = 'devices'
        self.required_props = ['name']
        self.skeleton_entity = {
            'properties': {}
        }

        self.entity_localdoc['DeleteEntityCommand'] = ("""\
                    Usage: delete

                    Deletes the specified device.""")

        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all VM devices of given type. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")

        self.add_property(
            descr='Device name',
            name='name',
            get='name',
            set='name',
            usage=_("Name of the device")
        )

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
            this.entity['properties']['@type'] = types[this.entity['type']]

        super(VMDeviceNamespaceBaseClass, self).save(this, new)


class VMDeviceGraphicsNamespace(VMDeviceNamespaceBaseClass):
    """
    The VM Device Graphics namespace provides commands for managing graphics resources
    available on selected virtual machine
    """
    def __init__(self, name, context, parent):
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

        super(VMDeviceGraphicsNamespace, self).__init__(name, context, parent)
        self.extra_query_params = [('type', 'in', 'GRAPHICS')]
        self.required_props.extend(['resolution'])
        self.skeleton_entity['type'] = 'GRAPHICS'

        self.localdoc['CreateEntityCommand'] = ("""\
                   Usage: create name=<device-name> property=<value>

                   Examples:
                       create name=framebuffer resolution=1280x1024

                   Creates device with selected properties.
                   For full list of propertise type 'help properties'""")

        self.add_property(
            descr='Framebuffer resolution',
            name='resolution',
            get=lambda o: list(o['properties']['resolution'].split('x')),
            set=set_resolution,
            list=True,
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
            usage=_("Resolution of the graphics device attached to the VM (example: 1024x768)")
        )

        self.add_property(
            descr='VNC server enabled',
            name='vnc_enabled',
            get='properties.vnc_enabled',
            list=True,
            type=ValueType.BOOLEAN,
            usage=_("Flag controlling wether the VNC server to VM's framebuffer is enabled or not")
        )

        self.add_property(
            descr='VNC server port',
            name='vnc_port',
            get='properties.vnc_port',
            list=True,
            set=set_vnc_port,
            type=ValueType.NUMBER,
            usage=_("Port to be used for the VNC server (if enabled) of VM. Please ensure a uniqure port number (one that is not already in use)")
        )

    @staticmethod
    def get_humanized_summary(o):
        return "VGA device with resolution {0}".format(get(o, 'properties.resolution'))


class VMDeviceUsbNamespace(VMDeviceNamespaceBaseClass):
    """
    The VM Device Usb namespace provides commands for managing USB resources
    available on selected virtual machine
    """
    def __init__(self, name, context, parent):
        super(VMDeviceUsbNamespace, self).__init__(name, context, parent)
        self.extra_query_params = [('type', 'in', 'USB')]
        self.required_props.extend(['device_type'])
        self.skeleton_entity['type'] = 'USB'

        self.localdoc['CreateEntityCommand'] = ("""\
                   Usage: create name=<device-name> property=<value>

                   Examples:
                       create name=mytablet device_type=tablet

                   Creates device with selected properties.
                   For full list of propertise type 'help properties'""")

        self.add_property(
            descr='Emulated device type',
            name='device_type',
            get='properties.device',
            enum=['tablet'],
            list=True,
            usage=_("Type of emulated usb device (currently only 'tablet' is supported)")
        )

    @staticmethod
    def get_humanized_summary(o):
        return "USB {0} device".format(get(o, 'properties.device'))


class VMDeviceNicNamespace(VMDeviceNamespaceBaseClass):
    """
    The VM Device Nic namespace provides commands for managing NIC resources
    available on selected virtual machine
    """
    def __init__(self, name, context, parent):
        super(VMDeviceNicNamespace, self).__init__(name, context, parent)
        self.extra_query_params = [('type', 'in', 'NIC')]
        self.required_props.extend(['mode', 'device_type'])
        self.skeleton_entity['type'] = 'NIC'

        self.localdoc['CreateEntityCommand'] = ("""\
                   Usage: create name=<device-name> property=<value>

                   Examples:
                       create name=mynic mode=NAT device_type=E1000

                   Creates device with selected properties.
                   For full list of propertise type 'help properties'""")

        self.add_property(
            descr='NIC mode',
            name='mode',
            get='properties.mode',
            enum=['NAT', 'BRIDGED', 'MANAGEMENT'],
            list=True,
            usage=_("Mode of NIC device [NAT|BRIDGED|MANAGEMENT]")
        )

        self.add_property(
            descr='Emulated device type',
            name='device_type',
            get='properties.device',
            enum=['VIRTIO', 'E1000', 'NE2K'],
            list=True,
            usage=_("The type of virtual NIC emulation [VIRTIO|E1000|NE2K]")
        )

        self.add_property(
            descr='Bridge with',
            name='bridge',
            get='properties.bridge',
            list=True,
            complete=MultipleSourceComplete(
                'bridge=', (
                    EntitySubscriberComplete('bridge=', 'network.interface', lambda i: i['id']),
                    EntitySubscriberComplete('bridge=', 'network.interface', lambda i: i['name'])
                ),
                extra=['default']
            ),
            usage=_("The interface to bridge NIC device with (if this NIC device is in BRIDGED mode)")
        )

        self.add_property(
            descr='MAC address',
            name='macaddr',
            get='properties.link_address',
            list=True,
            usage=_("Mac address of NIC device")
        )

    @staticmethod
    def get_humanized_summary(o):
        if get(o, 'properties.bridge'):
            return "{0} NIC bridged to {1}".format(get(o, 'properties.device'), get(o, 'properties.bridge'))

        return "{0} NIC".format(get(o, 'properties.device'))


class VMDeviceDiskNamespace(VMDeviceNamespaceBaseClass):
    """
    The VM Device Disk namespace provides commands for managing disk resources
    available on selected virtual machine
    """
    def __init__(self, name, context, parent):
        super(VMDeviceDiskNamespace, self).__init__(name, context, parent)
        self.extra_query_params = [('type', 'in', ('DISK'))]
        self.required_props.extend(['mode', 'size'])
        self.skeleton_entity['type'] = 'DISK'

        self.localdoc['CreateEntityCommand'] = ("""\
                   Usage: create name=<device-name> property=<value>

                   Examples:
                       create name=mydisk mode=AHCI size=1G

                   Creates device with selected properties.
                   For full list of propertise type 'help properties'""")

        self.add_property(
            descr='Disk mode',
            name='mode',
            get='properties.mode',
            enum=['AHCI', 'VIRTIO'],
            list=True,
            usage=_("The virtual disk emulation mode [AHCI|VIRTIO]")
        )

        self.add_property(
            descr='Disk size',
            name='size',
            get='properties.size',
            type=ValueType.SIZE,
            list=True,
            usage=_("States the size of the disk")
        )

    @staticmethod
    def get_humanized_summary(o):
        return "{0} {1} DISK".format(
            get_humanized_size(get(o, 'properties.size')),
            get(o, 'properties.mode')
        )


class VMDeviceCdromNamespace(VMDeviceNamespaceBaseClass):
    """
    The VM Device Cdrom namespace provides commands for managing cdrom device resources
    available on selected virtual machine
    """
    def __init__(self, name, context, parent):
        super(VMDeviceCdromNamespace, self).__init__(name, context, parent)
        self.extra_query_params = [('type', 'in', ('CDROM'))]
        self.required_props.extend(['image_path'])
        self.skeleton_entity['type'] = 'CDROM'

        self.localdoc['CreateEntityCommand'] = ("""\
                   Usage: create name=<device-name> property=<value>

                   Examples:
                       create name=mycdrom image_path=/path/to/image

                   Creates device with selected properties.
                   For full list of propertise type 'help properties'""")

        self.add_property(
            descr='Image path',
            name='image_path',
            get='properties.path',
            list=True,
            usage=_("The path on the filesystem where the image file(iso, img, etc.) for this CDROM device lives")
        )

    @staticmethod
    def get_humanized_summary(o):
        return "CDROM with image: {0}".format(get(o, 'properties.path'))


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
        self.required_props = ['name', 'destination']
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
        tid = context.submit_task(
            self.parent.create_task,
            self.parent.parent.entity['id'],
            name,
            descr
        )

        return EntityPromise(context, tid, self.parent)

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
            descr='Template images cached',
            name='cached',
            get='template.cached',
            usersetable=False,
            list=False,
            type=ValueType.BOOLEAN,
            usage=_("Flag describing wehter template's images are cached or not")
        )

        self.primary_key = self.get_mapping('name')
        self.entity_commands = self.get_entity_commands
        self.extra_commands = {
            'flush_cache': FlushCacheCommand(self)
        }

    def get_entity_commands(self, this):
        this.load() if hasattr(this, 'load') else None
        commands = {
            'readme': ReadmeCommand(this, 'template')
        }

        if hasattr(this, 'entity') and this.entity is not None:
            template = this.entity.get('template')
            if template:
                if template.get('cached', False):
                    commands['delete_cache'] = DeleteImagesCommand(this)
                else:
                    commands['download'] = DownloadImagesCommand(this)

                if template.get('source') != 'github':
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
        tid = context.submit_task(
            'vm.cache.update',
            self.parent.entity['template']['name'],
            callback=lambda s, t: post_save(self.parent, s, t)
        )
        return TaskPromise(context, tid)


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


@description("Deletes VM images from the local cache")
class DeleteImagesCommand(Command):
    """
    Usage: delete_cache

    Examples: delete_cache

    Deletes VM template images from the local cache.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs, filtering=None):
        tid = context.submit_task(
            'vm.cache.delete',
            self.parent.entity['template']['name'],
            callback=lambda s, t: post_save(self.parent, s, t)
        )
        return TaskPromise(context, tid)


@description("Deletes all VM images from the local cache")
class FlushCacheCommand(Command):
    """
    Usage: flush_cache

    Examples: flush_cache

    Deletes all VM template images from the local cache.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs, filtering=None):
        tid = context.submit_task(
            'vm.cache.flush',
            callback=lambda s, t: post_save(self.parent, s, t)
        )
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
