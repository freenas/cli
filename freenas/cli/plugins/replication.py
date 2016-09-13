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
    EntitySubscriberBasedLoadMixin, description
)
from freenas.cli.complete import NullComplete, EnumComplete
from freenas.cli.output import ValueType, read_value
from freenas.cli.utils import post_save, parse_timedelta
from freenas.utils import query as q

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description(_("Triggers replication process"))
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

        context.submit_task(
            'replication.sync',
            name,
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
                break

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
            bidirectional=<bidirectional> auto_recover=<auto_recover>
            replicate_services=<replicate_services> encrypt=<encrypt>
            compress=<fast/default/best> throttle=<throttle>
            snapshot_lifetime=<snapshot_lifetime> follow_delete=<follow_delete>

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
             create my_replication master=10.0.0.2 slave=10.0.0.3
                                   datasets=mypool,mypool2 bidirectional=yes
                                   recursive=yes replicate_services=yes
                                   auto_recover=yes
             create my_replication master=10.0.0.2 slave=10.0.0.3
                                   datasets=mypool encrypt=AES128
             create my_replication master=10.0.0.2 slave=10.0.0.3
                                   datasets=mypool compress=best
             create my_replication master=10.0.0.2 slave=10.0.0.3
                                   datasets=mypool throttle=10MiB
             create my_replication master=10.0.0.2 slave=10.0.0.3
                                   datasets=mypool encrypt=AES128 compress=best
                                   throttle=10MiB
             create my_replication master=10.0.0.2 slave=10.0.0.3
                                   datasets=mypool snapshot_lifetime=1:10:10
                                   followdelete=yes

    Creates a replication link entry. Link contains configuration data
    used in later replication process.

    All ZFS pools referenced in 'datasets' property must exist on both
    slave and master at creation time. They also need to have the same names.

    Created replication is implicitly: unidirectional, non-recursive,
    does not recover automatically and does not replicate services
    along with datasets.

    One of: master, slave parameters must represent one of current machine's
    IP addresses. Both these parameters must be defined,
    because unidirectional replication link can be promoted
    to become bi-directional link.

    Recursive parameter set to 'yes' informs that every child dataset
    of datasets defined in 'datasets' parameter will be replicated
    along with provided parents.

    Only in bi-directional replication service replication
    and automatic recovery are available.

    When automatic recovery is selected it is not possible to switch
    hosts roles manually. It's being done automatically each time
    'master' goes down or up again.
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
        auto_recover = read_value(kwargs.pop('auto_recover', False), ValueType.BOOLEAN)
        recursive = read_value(kwargs.pop('recursive', False), ValueType.BOOLEAN)
        replicate_services = read_value(kwargs.pop('replicate_services', False), ValueType.BOOLEAN)

        if not bidirectional:
            if replicate_services:
                raise CommandException(_(
                    'Replication of services is available only when bi-directional replication is selected'
                ))

            if auto_recover:
                raise CommandException(_(
                    'Automatic recovery is available only when bi-directional replication is selected'
                ))

        ns = SingleItemNamespace(None, self.parent, context)
        ns.orig_entity = copy.deepcopy(self.parent.skeleton_entity)
        ns.entity = copy.deepcopy(self.parent.skeleton_entity)

        ns.entity['name'] = name
        ns.entity['master'] = master
        ns.entity['partners'] = partners
        ns.entity['datasets'] = datasets
        ns.entity['bidirectional'] = bidirectional
        ns.entity['auto_recover'] = auto_recover
        ns.entity['recursive'] = recursive
        ns.entity['replicate_services'] = replicate_services

        compress = kwargs.pop('compress', None)
        encrypt = kwargs.pop('encrypt', 'AES128')
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
            if encrypt not in ['no', 'AES128', 'AES192', 'AES256']:
                raise CommandException('Encryption type must be selected as one of: no, AES128, AES192, AES256')
            if encrypt != 'no':
                transport_plugins.append({
                    'name': 'encrypt',
                    'type': encrypt.upper()
                })

        ns.entity['transport_options'] = transport_plugins

        ns.entity['snapshot_lifetime'] = parse_timedelta(kwargs.get('snapshot_lifetime', 365 * 24 * 60 * 60)).seconds
        ns.entity['followdelete'] = kwargs.get('followdelete', False)

        context.submit_task(
            self.parent.create_task,
            ns.entity,
            callback=lambda s, t: post_save(ns, s, t)
        )

    def complete(self, context, **kwargs):
        return [
            NullComplete('name='),
            NullComplete('master='),
            NullComplete('slave='),
            NullComplete('datasets='),
            NullComplete('throttle='),
            NullComplete('snapshot_lifetime='),
            EnumComplete('recursive=', ['yes', 'no']),
            EnumComplete('followdelete=', ['yes', 'no']),
            EnumComplete('bidirectional=', ['yes', 'no']),
            EnumComplete('auto_recover=', ['yes', 'no']),
            EnumComplete('replicate_services=', ['yes', 'no']),
            EnumComplete('compress=', ['fast', 'default', 'best']),
            EnumComplete('encrypt=', ['no', 'AES128', 'AES192', 'AES256'])
        ]


@description(_("List and manage replication tasks"))
class ReplicationNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The replication namespace provides commands for listing and managing replication tasks.
    """
    def __init__(self, name, context):
        super(ReplicationNamespace, self).__init__(name, context)

        self.primary_key_name = 'name'
        self.save_key_name = 'name'
        self.entity_subscriber_name = 'replication'
        self.create_task = 'replication.create'
        self.update_task = 'replication.update'
        self.delete_task = 'replication.delete'

        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete scrub=<scrub>

            Examples: delete
                      delete scrub=yes

             Delete current entity. Scrub allows to delete related datasets at slave side.""")

        self.skeleton_entity = {
            'bidirectional': False,
            'recursive': False,
            'replicate_services': False,
            'transport_options': []
        }

        def get_transport_option(obj, name):
            options = obj['transport_options']
            for o in options:
                if o['name'] == name:
                    return o

            return None

        def get_compress(obj):
            compress = get_transport_option(obj, 'compress')
            if compress:
                return compress['level']
            else:
                return None

        def get_throttle(obj):
            throttle = get_transport_option(obj, 'throttle')
            if throttle:
                return throttle['buffer_size']
            else:
                return None

        def get_encrypt(obj):
            encrypt = get_transport_option(obj, 'encrypt')
            if encrypt:
                return encrypt['type']
            else:
                return None

        def set_transport_option(obj, oldval, val):
            if oldval:
                obj['transport_options'].remove(oldval)
            if val:
                obj.append(val)

        def set_compress(obj, val):
            opt = {
                'name': 'compress',
                'level': val
            }
            set_transport_option(obj, get_transport_option(obj, 'compress'), opt)

        def set_throttle(obj, val):
            opt = {
                'name': 'throttle',
                'buffer_size': val
            }
            set_transport_option(obj, get_transport_option(obj, 'throttle'), opt)

        def set_encrypt(obj, val):
            opt = None
            if val != 'no':
                opt = {
                    'name': 'encrypt',
                    'type': val
                }
            set_transport_option(obj, get_transport_option(obj, 'encrypt'), opt)

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            usersetable=False,
            list=True)


        self.add_property(
            descr='Master',
            name='master',
            get='master',
            set='master',
            list=False)

        self.add_property(
            descr='Slave',
            name='slave',
            get='slave',
            usersetable=False,
            type=ValueType.SET,
            list=True,
        )
        
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
            descr='Automatic recovery',
            name='auto_recover',
            get='auto_recover',
            set='auto_recover',
            list=False,
            type=ValueType.BOOLEAN)

        self.add_property(
            descr='Initial master side',
            name='initial_master',
            get='initial_master',
            usersetable=False,
            list=False)

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

        self.add_property(
            descr='Transfer encryption',
            name='encryption',
            get=get_encrypt,
            set=set_encrypt,
            enum=['no', 'AES128', 'AES192', 'AES256'],
            list=False)

        self.add_property(
            descr='Transfer throttle',
            name='throttle',
            get=get_throttle,
            set=set_throttle,
            list=False,
            type=ValueType.SIZE)

        self.add_property(
            descr='Transfer compression',
            name='compression',
            get=get_compress,
            set=set_compress,
            enum=['fast', 'default', 'best'],
            list=False)

        self.add_property(
            descr='Snapshot lifetime',
            name='snapshot_lifetime',
            get='snapshot_lifetime',
            set=lambda o, v: q.set(o, 'snapshot_lifetime', parse_timedelta(str(v)).seconds),
            list=False,
            type=ValueType.NUMBER)

        self.add_property(
            descr='Follow delete',
            name='followdelete',
            get='followdelete',
            set='followdelete',
            list=False,
            type=ValueType.BOOLEAN)

        self.add_property(
            descr='Last result',
            name='result',
            get='status.status',
            usersetable=False,
            list=False,
            type=ValueType.STRING)

        self.add_property(
            descr='Last output message',
            name='message',
            get='status.message',
            usersetable=False,
            list=False,
            type=ValueType.STRING)

        self.add_property(
            descr='Last transfer size',
            name='size',
            get='status.size',
            usersetable=False,
            list=False,
            type=ValueType.SIZE)

        self.add_property(
            descr='Last transfer speed per second',
            name='speed',
            get='status.speed',
            usersetable=False,
            list=False,
            type=ValueType.SIZE)

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
            if this.entity.get('bidirectional') and not this.entity.get('auto_recover'):
                commands['switch_roles'] = SwitchCommand(this)

        return commands

    def delete(self, this, kwargs):
        self.context.submit_task(self.delete_task, this.entity[self.save_key_name], kwargs.get('scrub', False))


def _init(context):
    context.attach_namespace('/', ReplicationNamespace('replication', context))
