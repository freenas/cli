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

from namespace import Namespace, EntityNamespace, Command, RpcBasedLoadMixin, TaskBasedSaveMixin, description
from output import ValueType


@description("Provides information about installed disks")
class DisksNamespace(RpcBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context):
        super(DisksNamespace, self).__init__(name, context)

        self.query_call = 'simulator.disks.query'
        self.create_task = 'simulator.disks.create'
        self.update_task = 'simulator.disks.update'
        self.delete_task = 'simulator.disks.delete'

        self.add_property(
            descr='Disk name',
            name='name',
            get='id',
            list=True)

        self.add_property(
            descr='Disk path',
            name='path',
            get='path',
            list=True)

        self.add_property(
            descr='Size',
            name='mediasize',
            get='mediasize',
            list=True,
            type=ValueType.SIZE)

        self.add_property(
            descr='Serial number',
            name='serial',
            get='serial',
            list=False)

        self.add_property(
            descr='Vendor name',
            name='vendor',
            get='online',
            set=None,
            list=True,
            type=ValueType.BOOLEAN)

        self.add_property(
            descr='Model name',
            name='model',
            get='model',
            list=True
        )

        self.add_property(
            descr='RPM',
            name='rpm',
            get='properties.rpm',
            list=False,
            enum=['UNKNOWN', 'SSD', '5400', '7200', '10000', '15000']
        )

        self.primary_key = self.get_mapping('name')


class SimulatorNamespace(Namespace):
    def __init__(self, name, context):
        super(SimulatorNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            DisksNamespace('disk', self.context)
        ]


def _init(context):
    context.attach_namespace('/', SimulatorNamespace('simulator', context))
