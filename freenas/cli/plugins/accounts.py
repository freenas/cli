# coding=utf-8
#
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

import errno
import gettext
from freenas.cli.namespace import (
    Command, Namespace, EntityNamespace, TaskBasedSaveMixin,
    EntitySubscriberBasedLoadMixin, description, CommandException,
    ConfigNamespace, ItemNamespace, NestedEntityMixin
)
from freenas.cli.output import ValueType, Sequence
from freenas.utils.query import get


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Gets a list of valid shells")
class ShellsCommand(Command):
    """
    Usage: shells

    Examples: shells

    Displays a list of valid shells for user accounts.
    """

    def run(self, context, args, kwargs, opargs):
        return Sequence(*context.call_sync('shell.get_shells'))


@description(_("Manage local users"))
class UsersNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The user namespace provides commands for listing and managing local user accounts.
    """
    shells = None

    def __init__(self, name, context):
        super(UsersNamespace, self).__init__(name, context)

        self.primary_key_name = 'username'
        self.entity_subscriber_name = 'user'
        self.create_task = 'user.create'
        self.update_task = 'user.update'
        self.delete_task = 'user.delete'
        self.save_key_name = 'id'
        self.required_props = ['name', ['password', 'password_disabled']]
        self.extra_query_params = [['or', [('builtin', '=', False), ('username', '=', 'root')]]]

        if not UsersNamespace.shells:
            UsersNamespace.shells = context.call_sync('shell.get_shells')

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> password=<password> <property>=<value> ...

            Examples: create myuser password=mypassword home=/mnt/mypool/myuserhome
                      create someuser group=somegroup password_disabled=true

            Creates a user account. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set group=users
                      set password_disabled=True
                      set groups=wheel, ftp, operator

            Sets a user property. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete <property>=<value> ...

            Examples: delete
                      delete delete_home_directory=yes delete_own_group=yes

            Deletes the specified user.
            Note that built-in user accounts can not be deleted.""")

        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all users. Optionally, filter or sort by property.
            Use 'help account user properties' to list available properties.

            Examples:
                show
                show | search username == root
                show | search uid > 1000
                show | search fullname~=John | sort fullname""")
        self.entity_localdoc['GetEntityCommand'] = ("""\
            Usage: get <field>

            Examples:
                get username
                get uid
                get fullname

            Display value of specified field.""")
        self.entity_localdoc['EditEntityCommand'] = ("""\
            Usage: edit <field>

            Examples: edit username

            Opens the default editor for the specified property. The default editor
            is inherited from the shell's $EDITOR which can be set from the shell.
            For a list of properties for the current namespace, see 'help properties'.""")
        self.entity_localdoc['ShowEntityCommand'] = ("""\
            Usage: show

            Examples: show

            Display the property values for user.""")

        self.skeleton_entity = {
            'username': None,
            'group': None
        }

        self.createable = lambda entity: not entity['builtin']

        self.add_property(
            width=5,
            descr='User ID',
            name='uid',
            get='uid',
            list=True,
            usage=_("An unused number greater than 1000 and less than 65535."),
            type=ValueType.NUMBER
        )

        self.add_property(
            width=15,
            descr='User name',
            name='name',
            get='username',
            usage=_("""\
            Maximum 16 characters, though a maximum of 8 is recommended for
            interoperability. Can not begin with a hyphen or contain a space,
            a tab, a double quote, or any of these characters:
            , : + & # % ^ & ( ) ! @ ~ * ? < > =
            If a $ is used, it can only be the last character."""),
            list=True
        )

        self.add_property(
            width=20,
            descr='Full name',
            name='fullname',
            get='full_name',
            usage=_("Place within double quotes if contains a space."),
            list=True
        )

        self.add_property(
            width=20,
            descr='Primary group',
            name='group',
            get_name='group',
            get=self.display_group,
            usage=_("""\
            By default when a user is created, a primary group
            with the same name as the user is also created.
            When specifying a different group name, that group
            must already exist."""),
            set=self.set_group
        )

        self.add_property(
            descr='Auxiliary groups',
            name='groups',
            get=self.display_aux_groups,
            get_name='groups',
            usage=_("""\
            List of additional groups the user is a member of. To add
            the user to other groups, enclose a space delimited list
            between double quotes and ensure the groups already exist."""),
            set=self.set_aux_groups,
            type=ValueType.SET,
            list=False
        )

        self.add_property(
            descr='Login shell',
            name='shell',
            get='shell',
            usage=_("""\
            Default is "/bin/sh". Can be set to full path of an
            existing shell. Type 'shells' to see the list of
            available shells."""),
            list=False,
            enum=UsersNamespace.shells
        )

        self.add_property(
            descr='Home directory',
            name='home',
            get='home',
            usage=_("""\
            By default when a user is created, their home
            directory is not created. To create one, specify the
            full path to an existing dataset between double quotes."""),
            list=False
        )

        self.add_property(
            descr='Password',
            name='password',
            type=ValueType.PASSWORD,
            get='password',
            usage=_("""\
            Mandatory unless "password_disabled=true" is
            specified when creating the user. Passwords
            cannot contain a question mark."""),
            list=False
        )

        self.add_property(
            width=20,
            descr='Password Disabled',
            name='password_disabled',
            get='password_disabled',
            set='password_disabled',
            usage=_("""\
            Can be set to true or false. When set
            to true, disables password logins and
            authentication to CIFS shares but still
            allows key-based logins."""),
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Locked',
            name='locked',
            get='locked',
            usage=_("""\
            Can be set to true or false. While set
            to true, the account is disabled."""),
            list=False,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Email address',
            name='email',
            get='email',
            usage=_("""\
            Specify email address, enclosed between double quotes,
            to send that user's notifications to."""),
            list=False
        )

        self.add_property(
            descr='Administrator privileges',
            name='administrator',
            get='sudo',
            usage=_("""\
            Can be set to true or false. When set to true, the
            user is allowed to use sudo to run commands
            with administrative permissions."""),
            list=False,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='SSH public key',
            name='pubkey',
            get='sshpubkey',
            usage=_("""\
            To configure key-based authentication, use the 'set' command
            to paste the user's SSH public key."""),
            type=ValueType.STRING,
            list=False
        )

        self.add_property(
            width=20,
            descr='Domain',
            name='domain',
            get='origin.domain',
            set=None,
            type=ValueType.STRING,
            list=True
        )

        self.add_property(
            descr='Delete own group',
            name='delete_own_group',
            get=None,
            list=False,
            set='0.delete_own_group',
            delete_arg=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Delete home directory',
            name='delete_home_directory',
            get=None,
            list=False,
            set='0.delete_home_directory',
            delete_arg=True,
            type=ValueType.BOOLEAN
        )

        self.primary_key = self.get_mapping('name')
        self.extra_commands = {
            'shells': ShellsCommand()
        }

    def display_group(self, entity):
        group = self.context.entity_subscribers['group'].query(
            ('id', '=', entity['group']),
            single=True
        )
        return group['name'] if group else '<unknown group>'

    def set_group(self, entity, value):
        group = self.context.call_sync('group.query', [('name', '=', value)], {'single': True})
        if group:
            entity['group'] = group['id']
        else:
            raise CommandException(_('Group {0} does not exist.'.format(value)))

    def display_aux_groups(self, entity):
        for group in self.context.entity_subscribers['group'].query(('id', 'in', entity['groups'])):
            yield group['name'] if group else '<unknown group>'

    def set_aux_groups(self, entity, value):
        groups = list(self.context.entity_subscribers['group'].query(('name', 'in', list(value))))
        diff_groups = set.difference(set(value), set(x['name'] for x in groups))
        if len(diff_groups):
            raise CommandException(_('Groups {0} do not exist.'.format(', '.join(diff_groups))))

        entity['groups'] = [group['id'] for group in groups]


@description(_("Manage local groups"))
class GroupsNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The group namespace provides commands for listing and managing local groups.
    """
    def __init__(self, name, context):
        super(GroupsNamespace, self).__init__(name, context)

        self.primary_key_name = 'name'
        self.entity_subscriber_name = 'group'
        self.create_task = 'group.create'
        self.update_task = 'group.update'
        self.delete_task = 'group.delete'
        self.required_props = ['name']
        self.extra_query_params = [['or', [('builtin', '=', False), ('name', '=', 'wheel')]]]
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name>

            Examples: create somegroup

            Creates a group.""")
        self.entity_localdoc["SetEntityCommand"] = ("""\
            Usage: set name=<newname>

            Examples: set name=mygroup

            Sets the "name" property in order to rename the group. This
            will fail for builtin groups.""")
        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Examples: delete

            Deletes a group.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists groups, optionally doing filtering and sorting.

            Examples:
                show
                show | search name == wheel
                show | search gid > 1000
                show | search builtin == no""")
        self.entity_localdoc['GetEntityCommand'] = ("""\
            Usage: get <field>

            Examples:
                get name
                get gid

            Display value of specified field.""")
        self.entity_localdoc['EditEntityCommand'] = ("""\
            Usage: edit <field>

            Examples: edit name

            Opens the default editor for the specified property. The default editor
            is inherited from the shell's $EDITOR which can be set from the shell.
            For a list of properties for the current namespace, see 'help properties'.""")
        self.entity_localdoc['ShowEntityCommand'] = ("""\
            Usage: show

            Examples: show

            Display the property values for group.""")

        self.skeleton_entity = {
            'name': None,
            'builtin': False,
        }

        self.createable = lambda entity: not entity['builtin']

        self.add_property(
            descr='Group name',
            name='name',
            get='name',
            usersetable=lambda entity: not entity['builtin'],
            usage=_("""\
            Group name. Editable, unless the group was
            installed by the operating system."""),
            list=True
        )

        self.add_property(
            descr='Group ID',
            name='gid',
            get='gid',
            set='gid',
            type=ValueType.NUMBER,
            usage=_("""\
            Group ID. Read-only value assigned by operating
            system."""),
            list=True
        )

        self.add_property(
            descr='Builtin group',
            name='builtin',
            get='builtin',
            set=None,
            list=True,
            usage=_("""\
            Read-only value that indicates whether or not
            the group was created by the operating system."""),
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Domain',
            name='domain',
            get='origin.domain',
            set=None,
            type=ValueType.STRING,
            list=True
        )

        self.primary_key = self.get_mapping('name')


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
                      create AD_connection type=winbind
                      create FreeIPA_connection type=freeipa

            After creating the connection type you may then configure the directory 
            service via the properties namespace for the connection entity, for example 
            go to '/ account directoryservice directories <yourdirectory> properties'
            then do 'help properties' and use the 'set' command to set the properties
            necessary to bind to your server.

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
            type=ValueType.PASSWORD,
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

        self.add_property(
            descr='ID map type',
            name='idmap_type',
            get='idmap_type',
            enum=['RID', 'UNIX']
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
            type=ValueType.PASSWORD,
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
            type=ValueType.PASSWORD,
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


@description(_("Manage local users and groups"))
class AccountNamespace(Namespace):
    """
    The account namespace is used to manage local users and groups.
    """
    def __init__(self, name, context):
        super(AccountNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            UsersNamespace('user', self.context),
            GroupsNamespace('group', self.context),
            DirectoryServiceNamespace('directoryservice', self.context)
        ]


def _init(context):
    context.attach_namespace('/', AccountNamespace('account', context))
    context.map_tasks('user.*', UsersNamespace)
    context.map_tasks('group.*', GroupsNamespace)
