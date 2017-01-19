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

import errno
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
    description,
    CommandException,
)
from freenas.utils.query import get


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
    """
    The directoryservice namespace contains namespaces for managing
    the client site of FreeIPA, ActiveDirecory, LDAP and NIS directory services.
    """
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
    """
    The directoryservice config namespace provides commands for listing,
    and managing directory services general settings.
    """
    def __init__(self, name, context):
        super(DirectoryServicesConfigNamespace, self).__init__(name, context)
        self.config_call = "directoryservice.get_config"
        self.update_task = 'directoryservice.update'


        self.add_property(
            descr='Search order',
            name='search_order',
            get='search_order',
            type=ValueType.SET,
            usage=_('''\
            Serach order for the directory service connections
            created within 'directories' namespace.''')
        )

        self.add_property(
            descr='Cache TTL',
            name='cache_ttl',
            get='cache_ttl',
            type=ValueType.NUMBER,
            usage=_('''\
            TTL value of cached data provided by directory service connections
            created within 'directories' namespace.''')
        )


class DirectoriesNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    """
    The directories namespace provides commands for listing,
    creating, and managing directory service connections.
    """
    def __init__(self, name, context):
        def set_type(o, v):
            elem = self.context.entity_subscribers[self.entity_subscriber_name].query(
                ('type', '=', v),
                select='name',
                single=True,
            )
            if elem:
                raise CommandException(_("Only one instance of type: {0} allowed".format(v)))
            o['type'] = v

        super(DirectoriesNamespace, self).__init__(name, context)

        self.primary_key_name = 'name'
        self.entity_subscriber_name = 'directory'
        self.create_task = 'directory.create'
        self.update_task = 'directory.update'
        self.delete_task = 'directory.delete'

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> type=<type> <property>=<value>

            Examples: create LDAP_connection type=ldap enumerate=yes enabled=yes

            For a list of properties, see 'help properties'.""")

        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set name=new_directory_service_connection_name
                      set enabled=yes
                      set enumerate=no

            Sets a directory service connection general property.
            For a list of properties, see 'help properties'.""")

        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Deletes the specified directory service connection.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all directory service connections. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")


        self.add_property(
            descr='Directory name',
            name='name',
            get='name',
            list=True,
            usage=_("The name of the directory service connection.")
        )

        self.add_property(
            descr='Type',
            name='type',
            get='type',
            set=set_type,
            list=True,
            enum=['winbind', 'freeipa', 'ldap', 'nis'],
            usage=_("""\
            Type of the directory service connection type.
            Supported values : 'winbind', 'freeipa', 'ldap', 'nis' """)
        )

        self.add_property(
            descr='Enabled',
            name='enabled',
            get='enabled',
            list=True,
            type=ValueType.BOOLEAN,
            usage=_("Defines whether the directory service connection is enabled ")
        )

        self.add_property(
            descr='Enumerate users and groups',
            name='enumerate',
            get='enumerate',
            list=True,
            type=ValueType.BOOLEAN,
            usage=_("Defines whether the directory service connection enumerates users and groups ")

        )

        self.add_property(
            descr='State',
            name='state',
            get='status.state',
            set=None,
            list=True,
            usage=_("""\
            State of the directory service connection.
            Possible values : 'DISABLED', 'JOINING', 'FAILURE', 'BOUND', 'EXITING' """)
        )

        self.add_property(
            descr='Error code',
            name='error_code',
            get=lambda o: errno.errorcode.get(get(o, 'status.status_code')),
            set=None,
            list=True,
            condition=lambda o: get(o, 'status.state') == 'FAILURE',
            usage=_("Directory service connection error code ")
        )

        self.add_property(
            descr='Error message',
            name='error_message',
            get='status.status_message',
            set=None,
            list=True,
            condition=lambda o: get(o, 'status.state') == 'FAILURE',
            usage=_("Directory service connection status ")
        )

        """
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
        """

        def get_entity_namespaces(this):
            PROVIDERS = {
                'winbind': ActiveDirectoryPropertiesNamespace,
                'freeipa': FreeIPAPropertiesNamespace,
                'ldap': LDAPPropertiesNamespace,
                'nis': NISPropertiesNamespace
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
        super(BaseDirectoryPropertiesNamespace, self).__init__(name, context)
        self.context = context
        self.parent = parent
        self.parent_entity_path = 'parameters'


class ActiveDirectoryPropertiesNamespace(BaseDirectoryPropertiesNamespace):
    def __init__(self, name, context, parent):
        super(ActiveDirectoryPropertiesNamespace, self).__init__(name, context, parent)

        self.add_property(
            descr='Realm',
            name='realm',
            get='realm',
            usage=_("Active Directory realm. For example: 'contoso.com'")

        )

        self.add_property(
            descr='Username',
            name='username',
            get='username',
            usage=_("Active Directory privileged username")
        )

        self.add_property(
            descr='Password',
            name='password',
            get=None,
            set='password',
            usage=_("Active Directory privileged user password")
        )

        self.add_property(
            descr='DC hostname',
            name='dc_address',
            get='dc_address',
            usage=_("Active Directory domain controller hostname")
        )

        self.add_property(
            descr='SASL wrapping',
            name='sasl_wrapping',
            get='sasl_wrapping',
            enum=['PLAIN', 'SIGN', 'SEAL'],
            usage=_("""\
            Active Directory traffic encryption mode.
            Supported values : 'PLAIN', 'SIGN', 'SEAL' """)
        )


class FreeIPAPropertiesNamespace(BaseDirectoryPropertiesNamespace):
    def __init__(self, name, context, parent):
        super(FreeIPAPropertiesNamespace, self).__init__(name, context, parent)

        self.add_property(
            descr='Realm',
            name='realm',
            get='realm',
            usage=_("FreeIPA realm. For example: 'contoso.com'")
        )

        self.add_property(
            descr='Username',
            name='username',
            get='username',
            usage=_("FreeIPA privileged username")
        )

        self.add_property(
            descr='Password',
            name='password',
            get=None,
            set='password',
            usage=_("FreeIPA privileged user password")
        )

        self.add_property(
            descr='Server address',
            name='server',
            get='server',
            usage=_("FreeIPA server IP address")
        )


class LDAPPropertiesNamespace(BaseDirectoryPropertiesNamespace):
    def __init__(self, name, context, parent):
        super(LDAPPropertiesNamespace, self).__init__(name, context, parent)

        self.add_property(
            descr='Server address',
            name='server',
            get='server',
            usage=_("LDAP server IP address")
        )

        self.add_property(
            descr='Base DN',
            name='base_dn',
            get='base_dn',
            usage=_("LDAP Base DN. For example: 'dc=example,dc=com'")
        )

        self.add_property(
            descr='Bind DN',
            name='bind_dn',
            get='bind_dn',
            usage=_("LDAP privileged user. For example: 'cn=admin,dc=example,dc=com'")
        )

        self.add_property(
            descr='Bind password',
            name='password',
            get=None,
            set='password',
            usage=_("LDAP privileged user password")
        )

        self.add_property(
            descr='User suffix',
            name='user_suffix',
            get='user_suffix',
            usage=_("LDAP user suffix. For example: 'ou=users'")
        )

        self.add_property(
            descr='Group suffix',
            name='group_suffix',
            get='group_suffix',
            usage=_("LDAP group suffix. For example: 'ou=groups'")
        )

        self.add_property(
            descr='Encryption',
            name='encryption',
            get='encryption',
            enum=['OFF', 'SSL', 'TLS'],
            usage=_("""\
            LDAP traffic encryption mode.
            Supported values : 'OFF', 'SSL', 'TLS' """)
        )

        self.add_property(
            descr='CA Certificate',
            name='certificate',
            get='certificate',
            usage=_("LDAP server CA certificate")
        )

        self.add_property(
            descr='Verify certificate',
            name='verify_certificate',
            get='verify_certificate',
            type=ValueType.BOOLEAN,
            usage=_("LDAP server CA certificate veryfication")
        )

        self.add_property(
            descr='Kerberos principal',
            name='krb_principal',
            get='krb_principal',
            usage=_("Kerberos principal identity")
        )


class NISPropertiesNamespace(BaseDirectoryPropertiesNamespace):
    def __init__(self, name, context, parent):
        super(NISPropertiesNamespace, self).__init__(name, context, parent)

        self.add_property(
            descr='Domain',
            name='domain',
            get='domain',
            usage=_("NIS domain name. For example: 'radom.pl'")

        )

        self.add_property(
            descr='Server',
            name='server',
            get='server',
            usage=_("NIS server IP address")
        )


class KerberosNamespace(Namespace):
    """
    The kerberos namespace provides namespaces for managing
    kerberos realms and keytabs.
    """
    def __init__(self, name, context):
        super(KerberosNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            KerberosRealmsNamespace('realm', self.context),
            KerberosKeytabsNamespace('keytab', self.context)
        ]


class KerberosRealmsNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The realm namespace provides commands for listing,
    creating, and managing kerberos realms.
    """
    def __init__(self, name, context):
        super(KerberosRealmsNamespace, self).__init__(name, context)

        self.primary_key_name = 'realm'
        self.entity_subscriber_name = 'kerberos.realm'
        self.create_task = 'kerberos.realm.create'
        self.update_task = 'kerberos.realm.update'
        self.delete_task = 'kerberos.realm.delete'

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> kdc=192.168.10.1 <property>=<value>

            Examples: create example.com kdc=192.168.10.1

            For a list of properties, see 'help properties'.""")

        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set name=new_realm_name

            Sets a kerberos realm general property.
            For a list of properties, see 'help properties'.""")

        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Deletes the specified kerberos realm.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all kerberos realms. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")



        self.add_property(
            descr='Realm name',
            name='realm',
            get='realm',
            list=True,
            usage=_("Kerberos realm name")
        )

        self.add_property(
            descr='KDC',
            name='kdc',
            get='kdc_address',
            list=True,
            usage=_("Kerberos distribution key IP address")
        )

        self.add_property(
            descr='Admin server',
            name='admin_server',
            get='admin_server_address',
            list=True,
            usage=_("Kerberos admin server IP address")
        )

        self.add_property(
            descr='Password server',
            name='password_server',
            get='password_server_address',
            list=True,
            usage=_("Kerberos password server IP address")
        )

        self.primary_key = self.get_mapping('realm')


class KerberosKeytabsNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The keytab namespace provides commands for listing,
    creating, and managing kerberos keytabs.
    """
    def __init__(self, name, context):
        super(KerberosKeytabsNamespace, self).__init__(name, context)

        self.primary_key_name = 'name'
        self.entity_subscriber_name = 'kerberos.keytab'
        self.create_task = 'kerberos.keytab.create'
        self.update_task = 'kerberos.keytab.update'
        self.delete_task = 'kerberos.keytab.delete'

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> keytab=<file>

            Examples: create my_key_tab kdc=key_tab_file

            For a list of properties, see 'help properties'.""")

        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set name=new_keytab_name

            Sets a kerberos keytab general property.
            For a list of properties, see 'help properties'.""")

        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Deletes the specified kerberos keytab.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all kerberos keytabs. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")

        self.add_property(
            descr='Keytab name',
            name='name',
            get='name',
            list=True,
            usage=_("Kerberos keytab name")
        )

        self.add_property(
            descr='Keytab file',
            name='keytab',
            get=None,
            set=self.set_keytab_file,
            list=False,
            usage=_("Kerberos keytab file")
        )

        self.add_property(
            descr='Keytab entries',
            name='entries',
            get=self.get_keytab_entries,
            set=None,
            type=ValueType.SET,
            list=False,
            usage=_("Kerberos keytab entries")
        )

        self.primary_key = self.get_mapping('name')

    def set_keytab_file(self, obj, path):
        with open(path, 'rb') as f:
            obj['keytab'] = f.read()

    def get_keytab_entries(self, obj):
        return ['{principal} ({enctype}, vno {vno})'.format(**i) for i in obj['entries']]


def _init(context):
    context.attach_namespace('/', DirectoryServiceNamespace('directoryservice', context))
