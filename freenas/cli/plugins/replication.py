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
import six
import gettext
from freenas.cli.namespace import (
    SingleItemNamespace, Command, CommandException, EntityNamespace, TaskBasedSaveMixin,
    EntitySubscriberBasedLoadMixin, Namespace, description
)
from freenas.cli.complete import NullComplete, EnumComplete
from freenas.cli.output import ValueType, read_value
from freenas.cli.utils import post_save
from freenas.utils import query

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description(_("Triggers replication process"))
class SyncCommand(Command):
    """
    Usage: sync encrypt=<encrypt> compress=<fast/default/best> throttle=<throttle>

    Example: sync
             sync encrypt=AES128
             sync compress=best
             sync throttle=10MiB
             sync encrypt=AES128 compress=best throttle=10MiB

    Triggers replication process.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        name = self.parent.entity['name']
        compress = kwargs.pop('compress', None)
        encrypt = kwargs.pop('encrypt', None)
        throttle = kwargs.pop('throttle', None)
        transport_plugins = []

        if compress:
            if compress not in ['fast', 'default', 'best']:
                raise CommandException('Compression level must be selected as one of: fast, default, best')
            transport_plugins.append({
                'name': 'compress',
                'level': compress.upper()
            })

        if throttle:
            if not isinstance(throttle, int):
                raise CommandException('Throttle must be a number representing maximum transfer per second')
            transport_plugins.append({
                'name': 'throttle',
                'buffer_size': throttle
            })

        if encrypt:
            if encrypt not in ['AES128', 'AES192', 'AES256']:
                raise CommandException('Encryption type must be selected as one of: AES128, AES192, AES256')
            transport_plugins.append({
                'name': 'encrypt',
                'type': encrypt
            })

        context.submit_task(
            'replication.sync',
            name,
            transport_plugins,
            callback=lambda s, t: post_save(self.parent, s, t)
        )


@description(_("Switch roles of partners in bi-directional replication"))
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


@description(_("Creates a replication link"))
class CreateReplicationCommand(Command):
    """
    Usage: create <name> master=<master> slave=<slave> recursive=<recursive>
            bidirectional=<bidirectional> replicate_services=<replicate_services>

    Example: create my_replication master=10.0.0.2 slave=10.0.0.3
                                   datasets=mypool,mypool/dataset
             create my_replication master=10.0.0.2 slave=10.0.0.3
                                   datasets=mypool recursive=yes
             create my_replication master=10.0.0.2 slave=10.0.0.3 datasets=mypool
                                   bidirectional=yes
             create my_replication master=10.0.0.2 slave=10.0.0.3
                                   datasets=mypool,mypool2 bidirectional=yes
                                   recursive=yes
             create my_replication master=10.0.0.2 slave=10.0.0.3
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

        for ip in context.call_sync('network.config.get_my_ips'):
            if ip in partners:
                break
        else:
            raise CommandException(_(
                'None of provided replication link partners {0}, {1} match any of machine\'s IPs'.format(master, slave)
            ))

        datasets = kwargs.pop('datasets', [])
        if isinstance(datasets, six.string_types):
            datasets = [datasets]
        bidirectional = read_value(kwargs.pop('bidirectional', False), ValueType.BOOLEAN)
        recursive = read_value(kwargs.pop('recursive', False), ValueType.BOOLEAN)
        replicate_services = read_value(kwargs.pop('replicate_services', False), ValueType.BOOLEAN)

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
        ns.entity['bidirectional'] = bidirectional
        ns.entity['recursive'] = recursive
        ns.entity['replicate_services'] = replicate_services

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


@description(_("List and manage replication tasks"))
class ReplicationTaskNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The replication namespace provides commands for listing and managing replication tasks.
    """
    def __init__(self, name, context):
        super(ReplicationTaskNamespace, self).__init__(name, context)

        self.primary_key_name = 'name'
        self.save_key_name = 'name'
        self.entity_subscriber_name = 'replication.link'
        self.create_task = 'replication.create'
        self.update_task = 'replication.update'
        self.delete_task = 'replication.delete'

        self.localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete scrub=<scrub>

            Examples: delete
                      delete scrub=yes

             Delete current entity. Scrub allows to delete related datasets at slave side.""")

        self.skeleton_entity = {
            'bidirectional': False,
            'recursive': False,
            'replicate_services': False
        }

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            usersetable=False,
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
        cmds = super(ReplicationTaskNamespace, self).commands()
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

    def delete(self, this, kwargs):
        self.context.submit_task(self.delete_task, this.entity[self.save_key_name], kwargs.get('scrub', False))


@description(_("Exchange keys with remote host and create known replication host entry at both sides"))
class CreateHostsPairCommand(Command):
    """
    Usage: create <address> username=<username> password=<password>

    Example: create 10.0.0.1 username=my_username password=secret
             create my_username@10.0.0.1 password=secret
             create my_username@10.0.0.1 password=secret port=1234

    Exchange keys with remote host and create known replication host entry
    at both sides.

    User name and password are used only once to authorize key exchange.
    Default SSH port is 22.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args and not kwargs:
            raise CommandException(_("Create requires more arguments, see 'help create' for more information"))
        if len(args) > 1:
            raise CommandException(_("Wrong syntax for create, see 'help create' for more information"))

        if len(args) == 1:
            kwargs['address'] = args.pop(0)

        if 'address' not in kwargs:
            raise CommandException(_('Please specify an address of remote machine'))
        else:
            name = kwargs.pop('address')

        split_name = name.split('@')
        if len(split_name) == 2:
            kwargs['username'] = split_name[0]
            name = split_name[1]

        if 'username' not in kwargs:
            raise CommandException(_('Please specify a valid user name'))
        else:
            username = kwargs.pop('username')

        if 'password' not in kwargs:
            raise CommandException(_('Please specify a valid password'))
        else:
            password = kwargs.pop('password')

        port = kwargs.pop('port', 22)

        context.submit_task(
            self.parent.create_task,
            username,
            name,
            password,
            port
        )

    def complete(self, context):
        return [
            NullComplete('address='),
            NullComplete('username='),
            NullComplete('password='),
            NullComplete('port=')
        ]


@description(_("Manage replication hosts"))
class ReplicationHostNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The replication namespace provides commands for listing and managing replication tasks.
    """
    def __init__(self, name, context):
        super(ReplicationHostNamespace, self).__init__(name, context)

        self.primary_key_name = 'name'
        self.save_key_name = 'name'
        self.entity_subscriber_name = 'replication.host'
        self.create_task = 'replication.hosts_pair.create'
        self.allow_edit = False
        self.delete_task = 'replication.hosts_pair.delete'

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            usersetable=False,
            list=True)

        self.add_property(
            descr='Public key',
            name='pubkey',
            get='pubkey',
            usersetable=False,
            list=False)

        self.add_property(
            descr='Host key',
            name='hostkey',
            get='hostkey',
            usersetable=False,
            list=False)

        self.add_property(
            descr='Port',
            name='port',
            get='port',
            usersetable=False,
            list=False)

        self.primary_key = self.get_mapping('name')

    def commands(self):
        cmds = super(ReplicationHostNamespace, self).commands()
        cmds.update({'create': CreateHostsPairCommand(self)})
        return cmds


@description(_("Manage replication tasks and known replication hosts"))
class ReplicationNamespace(Namespace):
    """
    The replication namespace is used to manage replication tasks and
    known replication hosts.
    """
    def __init__(self, name, context):
        super(ReplicationNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            ReplicationTaskNamespace('task', self.context),
            ReplicationHostNamespace('host', self.context)
        ]


def _init(context):
    context.attach_namespace('/', ReplicationNamespace('replication', context))
