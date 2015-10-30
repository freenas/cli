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

from namespace import (
    Command,
    IndexCommand,
    Namespace,
    ConfigNamespace,
    EntityNamespace,
    RpcBasedLoadMixin,
    TaskBasedSaveMixin,
    description
)

from output import ValueType

@description("Configure and manage directory service")
class DirectoryServiceNamespace(Namespace):
    def __init__(self, name, context):
        super(DirectoryServiceNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            ActiveDirectoryNamespace('activedirectory', self.context),
            LDAPDirectoryNamespace('ldap', self.context)
        ]


class BaseDirectoryServiceNamespace(TaskBasedSaveMixin, RpcBasedLoadMixin, EntityNamespace):
#class BaseDirectoryServiceNamespace(ConfigNamespace):
    def __init__(self, name, type_name, context):
        super(BaseDirectoryServiceNamespace, self).__init__(name, context)

        self.type_name = type_name
        self.query_call = 'directoryservices.query'
        self.create_task = 'directoryservice.create'
        self.update_task = 'directoryservice.update'
        self.delete_task = 'directoryservice.delete'
        self.required_props = ['name']

        self.skeleton_entity = {
            'type': type_name,
            'properties': {}
        }

        self.add_property(
            descr='Directory Service',
            name='name',
            get='name',
            list=True
        )

        self.primary_key = self.get_mapping('name')
        self.primary_key_name = 'name'
        self.save_key_name = 'id'

    def query(self, params, options):
        params.append(('type', '=', self.type_name))
        return self.context.call_sync('directoryservices.query', params)


@description("Active Directory settings")
class ActiveDirectoryNamespace(BaseDirectoryServiceNamespace):
    def __init__(self, name, context):
        super(ActiveDirectoryNamespace, self).__init__(name, 'activedirectory', context)
        self.config_call = "activedirectory.get_config"

        self.add_property(
            descr='Domain',
            name='domain',
            get='domain',
            type=ValueType.STRING,
            list=True
        ) 

        self.add_property(
            descr='Bind Name',
            name='binddn',
            get='binddn',
            type=ValueType.STRING,
            list=True
        ) 

        self.add_property(
            descr='Bind Password',
            name='bindpw',
            get='bindpw',
            type=ValueType.STRING,
            list=True
        ) 


@description("LDAP directory settings")
class LDAPDirectoryNamespace(BaseDirectoryServiceNamespace):
    def __init__(self, name, context):
        super(LDAPDirectoryNamespace, self).__init__(name, 'ldap', context)
        self.config_call = "ldap.get_config"

        self.add_property(
            descr='Hostname',
            name='hostname',
            get='hostname',
            type=ValueType.STRING,
            list=True
        ) 

        self.add_property(
            descr='Bind Name',
            name='bindname',
            get='bindname',
            type=ValueType.STRING,
            list=True
        ) 

        self.add_property(
            descr='Bind Password',
            name='bindpw',
            get='bindpw',
            type=ValueType.STRING,
            list=True
        ) 


def _init(context):
    context.attach_namespace('/', DirectoryServiceNamespace('directoryservice', context))
