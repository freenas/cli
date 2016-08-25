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

import copy
import gettext
from freenas.cli.output import ValueType
from freenas.cli.namespace import (
    Command,
    Namespace,
    ConfigNamespace,
    ItemNamespace,
    EntityNamespace,
    EntitySubscriberBasedLoadMixin,
    TaskBasedSaveMixin,
    NestedEntityMixin,
    description
)


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


class DirectoryStatusCommand(Command):
    def __init__(self, parent):
        super(DirectoryStatusCommand, self).__init__()
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        pass


@description("Configure and manage directory services")
class DirectoryServiceNamespace(Namespace):
    def __init__(self, name, context):
        super(DirectoryServiceNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            DirectoryServicesConfigNamespace('config', self.context),
            DirectoriesNamespace('directories', self.context),
            KerberosNamespace('kerberos', self.context)
        ]


class DirectoryServicesConfigNamespace(ConfigNamespace):
    def __init__(self, name, context):
        super(DirectoryServicesConfigNamespace, self).__init__(name, context)
        self.config_call = "directoryservice.get_config"
        self.update_task = 'directoryservice.update'

        self.add_property(
            descr='Search order',
            name='search_order',
            get='search_order',
            type=ValueType.SET
        )

        self.add_property(
            descr='Cache TTL',
            name='cache_ttl',
            get='cache_ttl',
            type=ValueType.NUMBER
        )


class DirectoriesNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context):
        super(DirectoriesNamespace, self).__init__(name, context)

        self.primary_key_name = 'name'
        self.entity_subscriber_name = 'directory'
        self.create_task = 'directory.create'
        self.update_task = 'directory.update'
        self.delete_task = 'directory.delete'

        self.add_property(
            descr='Directory name',
            name='name',
            get='name',
            list=True
        )

        self.add_property(
            descr='Type',
            name='type',
            get='type',
            list=True
        )

        self.add_property(
            descr='Enabled',
            name='enabled',
            get='enabled',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Enumerate users and groups',
            name='enumerate',
            get='enumerate',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='State',
            name='state',
            get='status.state',
            set=None,
            list=True,
        )

        self.add_property(
            descr='Minimum UID',
            name='uid_min',
            get='uid_range.0',
            list=False
        )

        self.add_property(
            descr='Maximum UID',
            name='uid_max',
            get='uid_range.1',
            list=False
        )

        self.add_property(
            descr='Minimum GID',
            name='gid_min',
            get='gid_range.0',
            list=False
        )

        self.add_property(
            descr='Maximum GID',
            name='gid_max',
            get='gid_range.1',
            list=False
        )

        def get_entity_namespaces(this):
            PROVIDERS = {
                'winbind': ActiveDirectoryPropertiesNamespace,
                'freeipa': FreeIPAPropertiesNamespace,
                'ldap': LDAPPropertiesNamespace
            }

            this.load()
            if this.entity and this.entity.get('type'):
                provider = PROVIDERS.get(this.entity['type'])
                if provider:
                    return [provider('properties', self.context, this)]

            if getattr(self, 'is_docgen_instance', False):
                return [namespace('<entity=={0}>properties'.format(name), self.context, this) for name, namespace in
                        PROVIDERS.items()]

            return []

        self.entity_namespaces = get_entity_namespaces
        self.primary_key = self.get_mapping('name')


class BaseDirectoryPropertiesNamespace(NestedEntityMixin, ItemNamespace):
    def __init__(self, name, context, parent):
        super(BaseDirectoryPropertiesNamespace, self).__init__(name)
        self.context = context
        self.parent = parent
        self.parent_entity_path = 'parameters'


class ActiveDirectoryPropertiesNamespace(BaseDirectoryPropertiesNamespace):
    def __init__(self, name, context, parent):
        super(ActiveDirectoryPropertiesNamespace, self).__init__(name, context, parent)

        self.add_property(
            descr='Realm',
            name='realm',
            get='realm'
        )

        self.add_property(
            descr='Username',
            name='username',
            get='username'
        )

        self.add_property(
            descr='Password',
            name='password',
            get=None,
            set='password'
        )


class FreeIPAPropertiesNamespace(BaseDirectoryPropertiesNamespace):
    def __init__(self, name, context, parent):
        super(FreeIPAPropertiesNamespace, self).__init__(name, context, parent)

        self.add_property(
            descr='Realm',
            name='realm',
            get='realm'
        )

        self.add_property(
            descr='Username',
            name='username',
            get='username'
        )

        self.add_property(
            descr='Password',
            name='password',
            get=None,
            set='password'
        )

        self.add_property(
            descr='Server address',
            name='server',
            get='server'
        )


class LDAPPropertiesNamespace(BaseDirectoryPropertiesNamespace):
    def __init__(self, name, context, parent):
        super(LDAPPropertiesNamespace, self).__init__(name, context, parent)

        self.add_property(
            descr='Server address',
            name='server',
            get='server'
        )

        self.add_property(
            descr='Base DN',
            name='base_dn',
            get='base_dn'
        )

        self.add_property(
            descr='Bind DN',
            name='bind_dn',
            get='bind_dn'
        )

        self.add_property(
            descr='Bind password',
            name='password',
            get=None,
            set='password'
        )

        self.add_property(
            descr='User suffix',
            name='user_suffix',
            get='user_suffix',
        )

        self.add_property(
            descr='Group suffix',
            name='group_suffix',
            get='group_suffix',
        )


class KerberosNamespace(Namespace):
    def __init__(self, name, context):
        super(KerberosNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            KerberosRealmsNamespace('realm', self.context),
            KerberosKeytabsNamespace('keytab', self.context)
        ]


class KerberosRealmsNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(KerberosRealmsNamespace, self).__init__(name, context)

        self.primary_key_name = 'realm'
        self.entity_subscriber_name = 'kerberos.realm'
        self.create_task = 'kerberos.realm.create'
        self.update_task = 'kerberos.realm.update'
        self.delete_task = 'kerberos.realm.delete'

        self.add_property(
            descr='Realm name',
            name='realm',
            get='realm',
            list=True
        )

        self.add_property(
            descr='KDC',
            name='kdc',
            get='kdc_address',
            list=True
        )

        self.add_property(
            descr='Admin server',
            name='admin_server',
            get='admin_server_address',
            list=True
        )

        self.add_property(
            descr='Password server',
            name='password_server',
            get='password_server_address',
            list=True
        )

        self.primary_key = self.get_mapping('realm')


class KerberosKeytabsNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(KerberosKeytabsNamespace, self).__init__(name, context)

        self.primary_key_name = 'name'
        self.entity_subscriber_name = 'kerberos.keytab'
        self.create_task = 'kerberos.keytab.create'
        self.update_task = 'kerberos.keytab.update'
        self.delete_task = 'kerberos.keytab.delete'

        self.add_property(
            descr='Keytab name',
            name='name',
            get='name',
            list=True
        )

        self.add_property(
            descr='Keytab file',
            name='keytab',
            get=None,
            set=self.set_keytab_file,
            list=False
        )

        self.add_property(
            descr='Keytab entries',
            name='entries',
            get=self.get_keytab_entries,
            set=None,
            type=ValueType.SET,
            list=False
        )

        self.primary_key = self.get_mapping('name')

    def set_keytab_file(self, obj, path):
        with open(path, 'rb') as f:
            obj['keytab'] = f.read()

    def get_keytab_entries(self, obj):
        return ['{principal} ({enctype}, vno {vno})'.format(**i) for i in obj['entries']]


def _init(context):
    context.attach_namespace('/', DirectoryServiceNamespace('directoryservice', context))
