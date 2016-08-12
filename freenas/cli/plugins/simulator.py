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
from freenas.cli.namespace import Namespace, EntityNamespace, RpcBasedLoadMixin, TaskBasedSaveMixin, description
from freenas.cli.output import ValueType
from freenas.cli.utils import post_save


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Tools for simulating disks")
class DisksNamespace(RpcBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    """
    The disk namespace provides tools for creating and managing simulated disks for testing.
    """
    def __init__(self, name, context):
        super(DisksNamespace, self).__init__(name, context)

        self.query_call = 'simulator.disk.query'
        self.create_task = 'simulator.disk.create'
        self.update_task = 'simulator.disk.update'
        self.delete_task = 'simulator.disk.delete'
        self.required_props = ['name', 'mediasize']

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> mediasize=<size> <property>=<value> ...

            Examples:
                create mydisk mediasize=20G
                create mydisk mediasize=1T rpm=7200 vendor=Quantum model=Fireball
                create mydisk mediasize=150G rpm=SSD

            Creates a simulated disk for testing. For a list of
            properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] =  ("""\
            Usage: set <property>=<value> ...

            Examples: set online=false
                      set serial=abc123
                      set mediasize=30G
                      set rpm=15000

            Sets a simulated disk property. For a list of
            properties, see 'help properties'.""")
        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete <name>

            Example:
                delete mydisk

            Deletes a simulated disk.""")

        self.add_property(
            descr='Disk name',
            name='name',
            usage=_("""\
            Mandatory. Name of simulated disk."""),
            get='id',
            list=True
        )

        self.add_property(
            descr='Disk path',
            name='path',
            get='path',
            list=True
        )

        self.add_property(
            descr='Online',
            name='online',
            usage=_("""\
            Can be set to yes or no. When set to yes,
            simulates a disk that is online."""),
            get='online',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Size',
            name='mediasize',
            usage=_("""\
            Mandatory. specify a number and the alphabetic
            value. For example, 20G sets a size of 20GiB."""),
            get='mediasize',
            list=True,
            type=ValueType.SIZE
        )

        self.add_property(
            descr='Serial number',
            name='serial',
            usage=_("""\
            Optional alphanumeric value."""),
            get='serial',
            list=False
        )

        self.add_property(
            descr='Vendor name',
            name='vendor',
            usage=_("""\
            Optional name. It it contains a space, place it
            within double quotes."""),
            get='vendor',
            list=True
        )

        self.add_property(
            descr='Model name',
            name='model',
            usage=_("""\
            Optional model name. It it contains a space, place
            it within double quotes."""),
            get='model',
            list=True
        )

        self.add_property(
            descr='RPM',
            name='rpm',
            usage=_("""\
            Optional. Can be set to UNKNOWN, SSD, 7200, 10000,
            or 15000."""),
            get='rpm',
            list=False,
            enum=['UNKNOWN', 'SSD', '5400', '7200', '10000', '15000']
        )

        self.primary_key = self.get_mapping('name')

    def save(self, this, new=False):
        if new:
            self.context.submit_task(
                self.create_task,
                this.entity,
                callback=lambda s, t: self.post_save(this, s, t, new))
            return

        self.context.submit_task(
            self.update_task,
            this.orig_entity[self.save_key_name],
            this.get_diff(),
            callback=lambda s, t: self.post_save(this, s, t, new))

    def post_save(self, this, status, task, new):
        service_name = 'simulator'
        if status == 'FINISHED':
            service = self.context.call_sync('service.query', [('name', '=', service_name)], {'single': True})
            if service['state'] != 'RUNNING':
                if new:
                    action = "created"
                else:
                    action = "updated"

                self.context.output_queue.put(_(
                    "Disk '{0}' has been {1} but the service '{2}' is not currently running, "
                    "please enable the service with '/ service {2} config set enable=yes'".format(
                        this.entity['id'],
                        action,
                        service_name
                    )
                ))

        post_save(this, status, task)


@description("NAS simulation tools for testing")
class SimulatorNamespace(Namespace):
    """
    The simulator namespace provides tools for simulating aspects of a NAS for testing.
    """
    def __init__(self, name, context):
        super(SimulatorNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            DisksNamespace('disk', self.context)
        ]


def _init(context):
    context.attach_namespace('/', SimulatorNamespace('simulator', context))


def get_top_namespace(context):
    return SimulatorNamespace('simulator', context)
