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

from freenas.cli.namespace import Namespace, EntityNamespace, EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin


class VMwareNamespace(Namespace):
    def __init__(self, name, context):
        super(VMwareNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            VMwareDatasetsNamespace('dataset', self.context)
        ]


class VMwareDatasetsNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context):
        super(VMwareDatasetsNamespace, self).__init__(name, context)
        self.entity_subscriber_name = 'vmware.dataset'
        self.create_task = 'vmware.dataset.create'
        self.update_task = 'vmware.dataset.update'
        self.delete_task = 'vmware.dataset.delete'
        self.primary_key_name = 'name'

        self.add_property(
            descr='Mapping name',
            name='name',
            get='name',
            list=True
        )

        self.add_property(
            descr='Dataset name',
            name='dataset',
            get='dataset',
            list=True
        )

        self.add_property(
            descr='Datastore name',
            name='datastore',
            get='datastore',
            list=True
        )

        self.add_property(
            descr='VMware peer',
            name='peer',
            get='peer',
            list=True
        )

        self.primary_key = self.get_mapping('name')


def _init(context):
    context.attach_namespace('/', VMwareNamespace('vmware', context))
    context.map_tasks('vmware.dataset', VMwareDatasetsNamespace)
