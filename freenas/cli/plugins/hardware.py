#+
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
from freenas.cli.namespace import Namespace, Command, CommandException, description, ConfigNamespace
from freenas.cli.output import ValueType, Sequence, Object
from freenas.cli.complete import RpcComplete
from freenas.cli.plugins.disks import DisksNamespace
from freenas.cli.plugins.network import InterfacesNamespace, IPMINamespace


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext

@description("Provides information about hardware")
class ShowHardwareCommand(Command):
    """
    Usage: show

    Displays information about the hardware.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        namespaces = self.parent.namespaces()
        output_dict = {}
        output = Sequence()
        hw_info_dict = context.call_sync('system.info.hardware')
        parent_commands = self.parent.commands()

        def get_show(obj):
            if isinstance(obj, ConfigNamespace):
                obj.load()
            commands = obj.commands()
            if 'show' in commands:
                instance = commands['show']
                return instance.run(context, '', '', '')
            else:
                raise CommandException(_("Namespace {0} does not have 'show' command".format(obj.name)))

        def append_out(key):
            if key == 'ipmi' or len(output_dict[key]) > 0:
                output.append("\nData about {0}:".format(key))
                output.append(output_dict[key])


        for namespace in namespaces:
            output_dict[namespace.name] = get_show(namespace)
            append_out(namespace.name)

        output_dict['memory'] = Object(
            Object.Item("Memory size", 'memory_size', hw_info_dict['memory_size'], vt=ValueType.SIZE)
        )
        output_dict['cpu'] = parent_commands['cpu'].run(context, '', '', '')

        append_out('memory')
        append_out('cpu')

        return output


@description("Provides information about the CPU")
class ShowCPUInfoCommand(Command):
    """
    Usage: cpu

    Displays information about the hardware.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        cpu_data = context.call_sync('vm.get_hw_vm_capabilities')
        cpu_data.update(context.call_sync('system.info.hardware'))

        return Object(
            Object.Item("CPU Clockrate", 'cpu_clockrate', cpu_data['cpu_clockrate']),
            Object.Item("CPU Model", 'cpu_model', cpu_data['cpu_model']),
            Object.Item("CPU Cores", 'cpu_cores', cpu_data['cpu_cores']),
            Object.Item("VM Guest", 'vm_guest', cpu_data['vm_guest']),
            Object.Item("VTX capabilitie", 'vtx_enabled', cpu_data['vtx_enabled']),
            Object.Item("SVM Featuress", 'svm_features', cpu_data['svm_features']),
            Object.Item("Unrestricted Guest", 'unrestricted_guest', cpu_data['unrestricted_guest'])
        )


@description("Serial port namespace")
class SerialPortNamespace(ConfigNamespace):
    def __init__(self, name, context):
        super(SerialPortNamespace, self).__init__(name, context)
        self.config_call = 'system.advanced.get_config'
        self.update_call = 'system.advanced.update'

        self.add_property(
            descr='Enable Serial Console',
            name='serial_console',
            usage=_("""\
            Can be set to yes or no. Only set to yes,
            if the system has an active serial port and
            you want to access the system using that serial
            port."""),
            get='serial_console',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Serial Console Port',
            name='serial_port',
            usage=_("""\
            Use set or edit to specify the serial port
            to use for console access."""),
            get='serial_port',
            set='serial_port',
            complete=RpcComplete(
                'serial_port=',
                'system.device.get_devices',
                lambda o: o['name'],
                call_args=('serial_port',)
            )
        )

        self.add_property(
            descr='Serial Port Speed',
            name='serial_speed',
            usage=_("""\
            Use set to specify the speed of the serial port
            used for console access."""),
            get='serial_speed',
            set='serial_speed',
            enum=['110', '300', '600', '1200', '2400', '4800',
                  '9600', '14400', '19200', '38400', '57600', '115200'],
            type=ValueType.NUMBER
        )


@description("Configure and manage hardware")
class HardwareNamespace(Namespace):

    def __init__(self, name, context):
        super(HardwareNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        ret = [
            DisksNamespace('disks', self.context),
            InterfacesNamespace('network_interfaces', self.context),
            SerialPortNamespace('serial_port', self.context)
        ]
        if self.context.call_sync('ipmi.is_ipmi_loaded'):
            ret.append(IPMINamespace('ipmi', self.context))
        return ret

    def commands(self):
        return {
            'show': ShowHardwareCommand(self),
            'cpu': ShowCPUInfoCommand(self)
        }

def _init(context):
    context.attach_namespace('/', HardwareNamespace('hardware', context))