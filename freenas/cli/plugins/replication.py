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

import gettext
from freenas.cli.namespace import (
    Command, CommandException, EntityNamespace, TaskBasedSaveMixin,
    EntitySubscriberBasedLoadMixin, description
)
from freenas.cli.complete import EntitySubscriberComplete, MultipleSourceComplete, RpcComplete
from freenas.cli.output import ValueType, Table
from freenas.cli.utils import TaskPromise, post_save, parse_timedelta
from freenas.utils import query as q, human_readable_bytes


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
        tid = context.submit_task(
            'replication.sync',
            name,
            callback=lambda s, t: post_save(self.parent, s, t)
        )

        return TaskPromise(context, tid)


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

        tid = context.submit_task(
            'replication.update',
            name,
            {'master': master},
            callback=lambda s, t: post_save(self.parent, s, t)
        )

        return TaskPromise(context, tid)


@description(_("Delete replication status history"))
class DeleteHistoryCommand(Command):
    """
    Usage: clean_history

    Example: clean_history

    Deletes replication status history.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        tid = context.submit_task(
            'replication.clean_history',
            self.parent.entity['id']
        )

        return TaskPromise(context, tid)


@description(_("Displays history of replication results"))
class HistoryCommand(Command):
    """
    Usage: history

    Example: history

    Display history of replication results
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        return Table(
            self.parent.entity['status'],
            [
                Table.Column('Started', 'started_at', ValueType.TIME),
                Table.Column('Ended', 'ended_at', ValueType.TIME),
                Table.Column('Status', 'status'),
                Table.Column('Send size', lambda row: human_readable_bytes(row['size'])),
                Table.Column('Transfer speed', lambda row: human_readable_bytes(row['speed'], '/s')),
            ]
        )


@description(_("List and manage replication tasks"))
class ReplicationNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The replication namespace provides commands for listing and managing replication tasks.
    """
    def __init__(self, name, context):
        super(ReplicationNamespace, self).__init__(name, context)

        class PeerComplete(MultipleSourceComplete):
            def __init__(self, name):
                super(PeerComplete, self).__init__(
                    name,
                    (
                        EntitySubscriberComplete(name, 'peer', lambda o: o['name'] if o['type'] == 'freenas' else None),
                        RpcComplete(name, 'system.general.get_config', lambda o: o['hostname'])
                    )
                )

        self.primary_key_name = 'name'
        self.save_key_name = 'name'
        self.entity_subscriber_name = 'replication'
        self.create_task = 'replication.create'
        self.update_task = 'replication.update'
        self.delete_task = 'replication.delete'
        self.required_props = ['name', 'datasets', 'master', 'slave']

        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create <name> master=<master> slave=<slave> recursive=<recursive>
                    bidirectional=<bidirectional> auto_recover=<auto_recover>
                    replicate_services=<replicate_services> encrypt=<encrypt>
                    compress=<fast/default/best> throttle=<throttle>
                    snapshot_lifetime=<snapshot_lifetime> follow_delete=<follow_delete>

            Example: create my_replication master=10.0.0.2 slave=10.0.0.3
                                           datasets=mypool,mypool/dataset
                     create my_replication master=freenas-1.local slave=freenas-2.local
                                           datasets=source:target,source2/data:target2
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
            slave and master at creation time. Datasets can be defined as a simple list
            of datasets available on master (source) eg. mypool/mydataset,mypool2/mydataset2,
            or a list of {source}:{target} eg. mypool/ds:targetpool/ds2,otherpool:targetpool2.
            First example could be expanded to:
            mypool/mydataset:mypool/mydataset,mypool2/mydataset2:mypool2mydataset2
            It would have the same meaning.

            Bidirectional replication is accepting only identical master and slave
            (source and target) datasets trees eg mypool:mypool,mypool2:mypool2.

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
            Creates a replication task. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set bidirectional=yes
                      set throttle=1M
                      set encrypt=AES256
                      set datasets=mypool1,mypool2/dataset1

            Sets a replication property. For a list of properties, see 'help properties'.""")

        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Lists all replications. Optionally, filter or sort by property.
            Use 'help properties' to list available properties.

            Examples:
                show
                show | search name == foo""")

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
            opt = None
            if val != 'no':
                opt = {
                    '%type': 'compress-replication-transport-option',
                    'level': val
                }
            set_transport_option(obj, get_transport_option(obj, 'compress'), opt)

        def set_throttle(obj, val):
            opt = {
                '%type': 'throttle-replication-transport-option',
                'buffer_size': val
            }
            set_transport_option(obj, get_transport_option(obj, 'throttle'), opt)

        def set_encrypt(obj, val):
            opt = None
            if val != 'no':
                opt = {
                    '%type': 'encrypt-replication-transport-option',
                    'type': val
                }
            set_transport_option(obj, get_transport_option(obj, 'encrypt'), opt)

        def get_peer(obj, role):
            if obj[role] == self.context.call_sync('system.info.host_uuid'):
                return self.context.call_sync('system.general.get_config')['hostname']
            else:
                return self.context.entity_subscribers['peer'].query(
                    ('id', '=', obj[role]),
                    single=True,
                    select='name'
                )

        def set_peer(obj, val, role):
            if val == self.context.call_sync('system.general.get_config')['hostname']:
                obj[role] = self.context.call_sync('system.info.host_uuid')
            else:
                peer_id = self.context.entity_subscribers['peer'].query(
                    ('name', '=', val),
                    ('type', '=', 'freenas'),
                    single=True,
                    select='id'
                )
                obj[role] = peer_id

        def get_datasets(obj):
            return ['{0}:{1}'.format(i['master'], i['slave']) for i in obj['datasets']]

        def set_datasets(obj, value):
            datasets = []
            for ds in value:
                sp_dataset = ds.split(':', 1)
                datasets.append({
                    'master': sp_dataset[0],
                    'slave': sp_dataset[int(bool(len(sp_dataset) == 2 and sp_dataset[1]))]
                })

            obj['datasets'] = datasets

        def get_initial_master(obj):
            if obj['initial_master'] == obj['master']:
                return get_peer(obj, 'master')
            elif obj['initial_master'] == obj['slave']:
                return get_peer(obj, 'slave')
            else:
                return

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            usersetable=False,
            list=True,
            usage=_('Name of a replication task')
        )

        self.add_property(
            descr='Master',
            name='master',
            get=lambda o: get_peer(o, 'master'),
            set=lambda o, v: set_peer(o, v, 'master'),
            usersetable=False,
            list=False,
            complete=PeerComplete('master='),
            usage=_('Name of FreeNAS machine (peer) acting as a sending side.')
        )

        self.add_property(
            descr='Slave',
            name='slave',
            get=lambda o: get_peer(o, 'slave'),
            set=lambda o, v: set_peer(o, v, 'slave'),
            usersetable=False,
            list=True,
            complete=PeerComplete('slave='),
            usage=_('Name of FreeNAS machine (peer) acting as a receiving side.')
        )

        self.add_property(
            descr='Datasets',
            name='datasets',
            get=get_datasets,
            set=set_datasets,
            list=False,
            strict=False,
            type=ValueType.SET,
            complete=EntitySubscriberComplete('datasets=', 'volume.dataset', lambda o: o['name'] + ':'),
            usage=_('List of datasets to be replicated.')
        )

        self.add_property(
            descr='Bi-directional',
            name='bidirectional',
            get='bidirectional',
            set='bidirectional',
            list=False,
            type=ValueType.BOOLEAN,
            usage=_('Defines if a replication task does support inverting master/slave roles.')
        )

        self.add_property(
            descr='Automatic recovery',
            name='auto_recover',
            get='auto_recover',
            set='auto_recover',
            condition=lambda o: o.get('bidirectional'),
            list=False,
            type=ValueType.BOOLEAN,
            usage=_('''\
            Enables automatic replication stream invert when initial master
            becomes down/unreachable. Once initial master goes back online
            replication streams are being inverted again
            to match initial direction.''')
        )

        self.add_property(
            descr='Initial master side',
            name='initial_master',
            get=get_initial_master,
            usersetable=False,
            createsetable=False,
            list=False,
            usage=_('Informs which host was initially selected a replication master.')
        )

        self.add_property(
            descr='Recursive',
            name='recursive',
            get='recursive',
            set='recursive',
            list=False,
            type=ValueType.BOOLEAN,
            usage=_('Defines if selected datasets should be replicated recursively.')
        )

        self.add_property(
            descr='Services replication',
            name='replicate_services',
            get='replicate_services',
            set='replicate_services',
            condition=lambda o: o.get('bidirectional'),
            list=False,
            type=ValueType.BOOLEAN,
            usage=_('''\
            When set, in bidirectional replication case,
            enables FreeNAS machines to attempt to recreate services
            (such as shares) on new master after role swap.''')
        )

        self.add_property(
            descr='Transfer encryption',
            name='encryption',
            get=get_encrypt,
            set=set_encrypt,
            enum=['no', 'AES128', 'AES192', 'AES256'],
            list=False,
            usage=_('''\
            Encryption algorithm used during replication stream send operation.
            Can be one of: 'no', 'AES128', 'AES192', 'AES256'.''')
        )

        self.add_property(
            descr='Transfer throttle',
            name='throttle',
            get=get_throttle,
            set=set_throttle,
            list=False,
            type=ValueType.SIZE,
            usage=_('Maximum transfer speed during replication. Value in B/s.')
        )

        self.add_property(
            descr='Transfer compression',
            name='compression',
            get=get_compress,
            set=set_compress,
            enum=['no', 'fast', 'default', 'best'],
            list=False,
            usage=_('''\
            Compression algorithm used during replication stream send operation.
            Can be one of: 'no', 'fast', 'default', 'best'.''')
        )

        self.add_property(
            descr='Snapshot lifetime',
            name='snapshot_lifetime',
            get='snapshot_lifetime',
            set=lambda o, v: q.set(o, 'snapshot_lifetime', parse_timedelta(str(v)).seconds),
            list=False,
            type=ValueType.NUMBER,
            usage=_('Lifetime of snapshots created for replication purposes.')
        )

        self.add_property(
            descr='Follow delete',
            name='followdelete',
            get='followdelete',
            set='followdelete',
            list=False,
            type=ValueType.BOOLEAN,
            usage=_('''\
            Defines if replication should automatically remove
            stale snapshots at slave side.''')
        )

        self.add_property(
            descr='Current status',
            name='status',
            get='current_state.status',
            usersetable=False,
            createsetable=False,
            list=False,
            type=ValueType.STRING,
            usage=_('Current status of replication.')
        )

        self.add_property(
            descr='Current progress',
            name='progress',
            get=lambda o: '{0:.2f}'.format(round(q.get(o, 'current_state.progress'), 2)) + '%',
            usersetable=False,
            createsetable=False,
            list=False,
            type=ValueType.STRING,
            condition=lambda o: q.get(o, 'current_state.status') == 'RUNNING',
            usage=_('Current progress of replication.')
        )

        self.add_property(
            descr='Last speed',
            name='speed',
            get='current_state.speed',
            usersetable=False,
            createsetable=False,
            list=False,
            type=ValueType.STRING,
            condition=lambda o: q.get(o, 'current_state.status') == 'RUNNING',
            usage=_('Transfer speed of current replication run.')
        )

        self.primary_key = self.get_mapping('name')

        self.entity_commands = self.get_entity_commands

    def get_entity_commands(self, this):
        this.load()
        commands = {
            'sync': SyncCommand(this),
            'history': HistoryCommand(this),
            'clean_history': DeleteHistoryCommand(this)
        }

        if this.entity:
            if this.entity.get('bidirectional') and not this.entity.get('auto_recover'):
                commands['switch_roles'] = SwitchCommand(this)

        return commands

    def delete(self, this, kwargs):
        return self.context.submit_task(self.delete_task, this.entity[self.save_key_name], kwargs.get('scrub', False))


def _init(context):
    context.attach_namespace('/', ReplicationNamespace('replication', context))
    context.map_tasks('replication.*', ReplicationNamespace)

