# +
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


import icu
from freenas.cli.namespace import (
    Namespace, EntityNamespace, IndexCommand, TaskBasedSaveMixin,
    RpcBasedLoadMixin, description, CommandException
    )
from freenas.cli.output import ValueType

t = icu.Transliterator.createInstance("Any-Accents", icu.UTransDirection.FORWARD)
_ = t.transliterate


@description(_("System users"))
class UsersNamespace(TaskBasedSaveMixin, RpcBasedLoadMixin, EntityNamespace):

    def __init__(self, name, context):
        super(UsersNamespace, self).__init__(name, context)

        self.primary_key_name = 'username'
        self.query_call = 'users.query'
        self.create_task = 'users.create'
        self.update_task = 'users.update'
        self.delete_task = 'users.delete'
        self.save_key_name = 'id'
        self.required_props = ['username', ['password','password_disabled']]

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> password=<password> <property>=<value> ...

            Examples: create foo password=bar home=/tank/foo
                      create bar group=bar password_disabled=true

            Creates a user account. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set fullname="John Smith"
                      set group=users
                      set password_disabled=True
                      set groups=wheel, ftp, operator

            Sets a user property. For a list of properties, see 'help properties'.""")


        self.skeleton_entity = {
            'username': None,
            'group': None
        }

        self.add_property(
            descr='User ID',
            name='uid',
            get='id',
            set=None,
            list=True,
            type=ValueType.NUMBER)

        self.add_property(
            descr='User name',
            name='username',
            get='username',
            list=True)

        self.add_property(
            descr='Full name',
            name='fullname',
            get='full_name',
            list=True)

        self.add_property(
            descr='Primary group',
            name='group',
            get_name='group',
            get=self.display_group,
            set=self.set_group)

        self.add_property(
            descr='Auxilliary groups',
            name='groups',
            get=self.display_aux_groups,
            get_name='groups',
            set=self.set_aux_groups,
            type=ValueType.SET
            )

        self.add_property(
            descr='Login shell',
            name='shell',
            get='shell')

        self.add_property(
            descr='Home directory',
            name='home',
            get='home',
            list=True)

        self.add_property(
            descr='Password',
            name='password',
            get=None,
            set='password',
            list=False
        )

        self.add_property(
            descr='Password Disabled',
            name='password_disabled',
            get='password_disabled',
            set='password_disabled',
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Locked',
            name='locked',
            get='locked',
            list=False,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Email address',
            name='email',
            get='email',
            list=False
        )

        self.add_property(
            descr='Sudo allowed',
            name='sudo',
            get='sudo',
            list=False,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='SSH public key',
            name='pubkey',
            get='sshpubkey',
            type=ValueType.STRING,
            list=False
        )

        self.primary_key = self.get_mapping('username')

    def display_group(self, entity):
        group = self.context.call_sync(
            'groups.query', [('id', '=', entity['group'])], {'single': True}
            )
        return group['name'] if group else 'GID:{0}'.format(entity['group'])

    def set_group(self, entity, value):
        group = self.context.call_sync('groups.query', [('name', '=', value)], {'single': True})
        if group:
            entity['group'] = group['id']
        else:
            raise CommandException(_('Group {0} does not exist.'.format(value)))

    def display_aux_groups(self, entity):
        groups = self.context.call_sync(
            'groups.query', [('id', 'in', entity['groups'])]
            )
        for group in groups:
            yield group['name'] if group else 'GID:{0}'.format(group['id'])

    def set_aux_groups(self, entity, value):
        groups = self.context.call_sync('groups.query', [('name', 'in', list(value))])
        diff_groups = set.difference(set([x['name'] for x in groups]), set(value))
        if len(diff_groups):
            raise CommandException(_('Groups {0} do not exist.'.format(diff_groups)))
        entity['groups'] = [group['id'] for group in groups]


@description(_("System groups"))
class GroupsNamespace(TaskBasedSaveMixin, RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, context):
        super(GroupsNamespace, self).__init__(name, context)

        self.primary_key_name = 'name'
        self.query_call = 'groups.query'
        self.create_task = 'groups.create'
        self.update_task = 'groups.update'
        self.delete_task = 'groups.delete'
        self.required_props = ['name']
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name>

            Examples: create foo

            Creates a group.""")
        self.entity_localdoc["SetEntityCommand"] = ("""\
            Usage: set name=<newname>

            Examples: set name=bar

            Allows renaming a group.""")

        self.skeleton_entity = {
            'name': None,
        }

        self.add_property(
            descr='Group name',
            name='name',
            get='name',
            list=True)

        self.add_property(
            descr='Group ID',
            name='gid',
            get='id',
            set=None,
            list=True)

        self.add_property(
            descr='Builtin group',
            name='builtin',
            get='builtin',
            set=None,
            list=True,
            type=ValueType.BOOLEAN)

        self.primary_key = self.get_mapping('name')


@description(_("Manage system users and groups"))
class AccountNamespace(Namespace):
    def __init__(self, name, context):
        super(AccountNamespace, self).__init__(name)
        self.context = context

    def commands(self):
        return {
            '?': IndexCommand(self)
        }

    def namespaces(self):
        return [
            UsersNamespace('user', self.context),
            GroupsNamespace('group', self.context)
        ]


def _init(context):
    context.attach_namespace('/', AccountNamespace('account', context))
