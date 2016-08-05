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


import gettext
from freenas.cli.namespace import (
    Command, Namespace, EntityNamespace, TaskBasedSaveMixin,
    EntitySubscriberBasedLoadMixin, description, CommandException
)
from freenas.cli.output import ValueType, Sequence

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Gets a list of valid shells")
class ShellsCommand(Command):
    """
    Usage: shells

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
        self.required_props = ['username', ['password', 'password_disabled']]
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
            Usage: delete <username>

            Example: delete myuser

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

        self.skeleton_entity = {
            'username': None,
            'group': None
        }

        self.createable = lambda entity: not entity['builtin']

        self.add_property(
            display_width_percentage=15,
            descr='User ID',
            name='uid',
            get='uid',
            list=True,
            usage=_("An unused number greater than 1000 and less than 65535."),
            type=ValueType.NUMBER
        )

        self.add_property(
            display_width_percentage=25,
            descr='User name',
            name='username',
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
            display_width_percentage=25,
            descr='Full name',
            name='fullname',
            get='full_name',
            usage=_("Place within double quotes if contains a space."),
            list=True
        )

        self.add_property(
            display_width_percentage=25,
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
            get=None,
            set='password',
            usage=_("""\
            Mandatory unless "password_disabled=true" is
            specified when creating the user. Passwords
            cannot contain a question mark."""),
            list=False
        )

        self.add_property(
            display_width_percentage=10,
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
            descr='Sudo allowed',
            name='sudo',
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

        self.primary_key = self.get_mapping('username')
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
        groups = self.context.entity_subscribers['group'].query(
            ('id', 'in', entity['groups'])
        )
        for group in groups:
            yield group['name'] if group else '<unknown group>'

    def set_aux_groups(self, entity, value):
        groups = self.context.entity_subscribers['group'].query(('name', 'in', list(value)))
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
            Usage: delete <groupname>

            Example: delete smbusers

            Deletes a group.""")
        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists groups, optionally doing filtering and sorting.

            Examples:
                show
                show | search name == wheel
                show | search gid > 1000
                show | search builtin == no""")

        self.skeleton_entity = {
            'name': None,
        }

        self.createable = lambda entity: not entity['builtin']

        self.add_property(
            descr='Group name',
            name='name',
            get='name',
            usersetable = lambda entity: not entity['builtin'],
            usage=_("""\
            Group name. Editable, unless the group was
            installed by the operating system."""),
            list=True)

        self.add_property(
            descr='Group ID',
            name='gid',
            get='gid',
            set='gid',
            usersetable=False,
            type=ValueType.NUMBER,
            usage=_("""\
            Group ID. Read-only value assigned by operating
            system."""),
            list=True)

        self.add_property(
            descr='Builtin group',
            name='builtin',
            get='builtin',
            set=None,
            list=True,
            usage=_("""\
            Read-only value that indicates whether or not
            the group was created by the operating system."""),
            type=ValueType.BOOLEAN)

        self.primary_key = self.get_mapping('name')


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
            GroupsNamespace('group', self.context)
        ]


def _init(context):
    context.attach_namespace('/', AccountNamespace('account', context))
    context.map_tasks('user.*', UsersNamespace)
    context.map_tasks('group.*', GroupsNamespace)
