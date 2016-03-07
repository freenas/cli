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

import copy
import gettext
from freenas.cli.namespace import (
    SingleItemNamespace, Command, CommandException, EntityNamespace, TaskBasedSaveMixin,
    EntitySubscriberBasedLoadMixin, description
)
from freenas.cli.complete import NullComplete, EnumComplete
from freenas.cli.output import ValueType
from freenas.cli.utils import post_save
from freenas.utils import query

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Triggers replication process")
class SyncCommand(Command):
    """
    Usage: sync

    Example: sync

    Triggers replication process.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        name = self.parent.entity['name']
        context.submit_task('replication.sync', name, callback=lambda s, t: post_save(self.parent, s, t))


@description("Switch roles of partners in bi-directional replication")
class SwitchCommand(Command):
    """
    Usage: switch_roles

    Example: switch_roles

    Switch roles of partners in bi-directional replication.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not self.parent.entity.get('bidirectional'):
            raise CommandException('This replication link is not bi-directional')

        name = self.parent.entity['name']
        partners = self.parent.entity['partners']
        master = self.parent.entity['master']
        for partner in partners:
            if partner != master:
                master = partner

        context.submit_task(
            'replication.update',
            name,
            {'master': master},
            callback=lambda s, t: post_save(self.parent, s, t)
        )


@description("Creates a replication link")
class CreateReplicationCommand(Command):
    """
    Usage: create <name> master=<master> slave=<slave> recursive=<recursive>
            bidirectional=<bidirectional> replicate_services=<replicate_services>

    Example: create my_replication master=user@10.0.0.2 slave=user2@10.0.0.3
                                   datasets=mypool,mypool/dataset
             create my_replication master=user@10.0.0.2 slave=user2@10.0.0.3
                                   datasets=mypool recursive=yes
             create my_replication master=10.0.0.2 slave=10.0.0.3 datasets=mypool
                                   bidirectional=yes
             create my_replication master=user@10.0.0.2 slave=user2@10.0.0.3
                                   datasets=mypool,mypool2 bidirectional=yes
                                   recursive=yes
             create my_replication master=user@10.0.0.2 slave=user2@10.0.0.3
                                   datasets=mypool,mypool2 bidirectional=yes
                                   recursive=yes replicate_services=yes

    Creates a replication link entry. Link contains configuration data
    used in later replication process.

    Created replication is implicitly: unidirectional, non-recursive
    and does not replicate services along with datasets.

    One of: master, slave parameters must represent one of current machine's
    IP addresses. Both these parameters must be defined,
    because unidirectional replication link can be promoted
    to become bi-directional link.

    Recursive parameter set to 'yes' informs that every child dataset
    of datasets defined in 'datasets' parameter will be replicated
    along with provided parents.

    Only in bi-directional replication service replication is available.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args and not kwargs:
            raise CommandException(_("Create requires more arguments, see 'help create' for more information"))
        if len(args) > 1:
            raise CommandException(_("Wrong syntax for create, see 'help create' for more information"))

        if len(args) == 1:
            kwargs[self.parent.primary_key.name] = args.pop(0)

        if 'name' not in kwargs:
            raise CommandException(_('Please specify a name for your replication link'))
        else:
            name = kwargs.pop('name')

        master = kwargs.pop('master')
        slave = kwargs.pop('slave')
        partners = [master, slave]
        split_master = master.split('@')
        split_slave = slave.split('@')

        try:
            partners_ips = [split_master[1], split_slave('@')[1]]
        except IndexError:
            raise CommandException(_('Type link partners in user@host schema'))

        for ip in context.call_sync('network.config.get_my_ips'):
            if ip in partners_ips:
                break
        else:
            raise CommandException(_(
                'None of provided replication link partners {0}, {1} match any of machine\'s IPs'.format(master, slave)
            ))

        if context.call_sync('user.query', [('username', '=', split_master[0])], {'single': True}):
            pass
        elif not context.call_sync('user.query', [('username', '=', split_slave[0])], {'single': True}):
            raise CommandException(_(
                'None of provided replication link partners {0}, {1} match any of current machine user names'.format(
                    master, slave
                )
            ))

        datasets = kwargs.pop('datasets')
        bidirectional = kwargs.pop('bidirectional')
        recursive = kwargs.pop('recursive')
        replicate_services = kwargs.pop('replicate_services')

        if replicate_services and not bidirectional:
            raise CommandException(_(
                'Replication of services is available only when bi-directional replication is selected'
            ))

        ns = SingleItemNamespace(None, self.parent)
        ns.orig_entity = query.wrap(copy.deepcopy(self.parent.skeleton_entity))
        ns.entity = query.wrap(copy.deepcopy(self.parent.skeleton_entity))

        ns.entity['name'] = name
        ns.entity['master'] = master
        ns.entity['partners'] = partners
        ns.entity['datasets'] = datasets
        if bidirectional:
            ns.entity['bidirectional'] = True
        if recursive:
            ns.entity['recursive'] = True
        if replicate_services:
            ns.entity['replicate_services'] = True

        context.submit_task(
            self.parent.create_task,
            ns.entity,
            callback=lambda s, t: post_save(ns, s, t)
        )

    def complete(self, context):
        return [
            NullComplete('name='),
            NullComplete('master='),
            NullComplete('slave='),
            NullComplete('datasets='),
            EnumComplete('recursive=', ['yes', 'no']),
            EnumComplete('bidirectional=', ['yes', 'no']),
            EnumComplete('replicate_services=', ['yes', 'no'])
        ]


class ReplicationNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The replication namespace provides commands for listing and managing replication tasks.
    """
    def __init__(self, name, context):
        super(ReplicationNamespace, self).__init__(name, context)

        self.primary_key_name = 'name'
        self.save_key_name = 'name'
        self.entity_subscriber_name = 'replication.link'
        self.create_task = 'replication.create'
        self.update_task = 'replication.update'
        self.delete_task = 'replication.delete'

        self.skeleton_entity = {
            'bidirectional': False,
            'recursive': False,
            'replicate_services': False
        }

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            set='name',
            list=True)

        self.add_property(
            descr='Partners',
            name='partners',
            get='partners',
            usersetable=False,
            type=ValueType.SET,
            list=True)

        self.add_property(
            descr='Master',
            name='master',
            get='master',
            set='master',
            list=False)

        self.add_property(
            descr='Datasets',
            name='datasets',
            get='datasets',
            set='datasets',
            list=False,
            type=ValueType.SET)

        self.add_property(
            descr='Bi-directional',
            name='bidirectional',
            get='bidirectional',
            set='bidirectional',
            list=False,
            type=ValueType.BOOLEAN)

        self.add_property(
            descr='Recursive',
            name='recursive',
            get='recursive',
            set='recursive',
            list=False,
            type=ValueType.BOOLEAN)

        self.add_property(
            descr='Services replication',
            name='replicate_services',
            get='replicate_services',
            set='replicate_services',
            list=False,
            type=ValueType.BOOLEAN)

        self.primary_key = self.get_mapping('name')

        self.entity_commands = self.get_entity_commands

    def commands(self):
        cmds = super(ReplicationNamespace, self).commands()
        cmds.update({'create': CreateReplicationCommand(self)})
        return cmds

    def get_entity_commands(self, this):
        this.load()
        commands = {
            'sync': SyncCommand(this)
        }

        if this.entity:
            if this.entity.get('bidirectional'):
                commands['switch_roles'] = SwitchCommand(this)

        return commands


def _init(context):
    context.attach_namespace('/', ReplicationNamespace('replication', context))
