#+
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
from namespace import (
    Namespace, EntityNamespace, Command, IndexCommand,
    RpcBasedLoadMixin, TaskBasedSaveMixin, description,
    CommandException
    )
from output import ValueType, Table
from fnutils import first_or_default


t = icu.Transliterator.createInstance("Any-Accents", icu.UTransDirection.FORWARD)
_ = t.transliterate


@description("Lists users connected to particular share")
class ConnectedUsersCommand(Command):
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        result = context.call_sync('shares.get_connected_clients', self.parent.entity['id'])
        return Table(result, [
            Table.Column(_("IP address"), 'host', ValueType.STRING),
            Table.Column(_("User"), 'user', ValueType.STRING),
            Table.Column(_("Connected at"), 'connected_at', ValueType.STRING)
        ])


@description("Configure and manage shares")
class SharesNamespace(Namespace):
    def __init__(self, name, context):
        super(SharesNamespace, self).__init__(name)
        self.context = context

    def commands(self):
        return {
            '?': IndexCommand(self)
        }

    def namespaces(self):
        return [
            NFSSharesNamespace('nfs', self.context),
            AFPSharesNamespace('afp', self.context),
            SMBSharesNamespace('smb', self.context),
            ISCSISharesNamespace('iscsi', self.context)
        ]


class BaseSharesNamespace(TaskBasedSaveMixin, RpcBasedLoadMixin, EntityNamespace):
    def __init__(self, name, type_name, context):
        super(BaseSharesNamespace, self).__init__(name, context)

        self.type_name = type_name
        self.query_call = 'shares.query'
        self.create_task = 'share.create'
        self.update_task = 'share.update'
        self.delete_task = 'share.delete'
        self.required_props = ['name', 'volume']

        self.skeleton_entity = {
            'type': type_name,
            'properties': {}
        }

        self.add_property(
            descr='Share name',
            name='name',
            get='name',
            list=True
        )

        self.add_property(
            descr='Share type',
            name='type',
            get='type',
            list=False
        )

        self.add_property(
            descr='Target volume',
            name='volume',
            get='target',
            set='target',
            list=True
        )

        self.primary_key = self.get_mapping('name')
        self.primary_key_name = 'name'
        self.save_key_name = 'id'
        self.entity_commands = lambda this: {
            'clients': ConnectedUsersCommand(this)
        }

    def query(self, params, options):
        params.append(('type', '=', self.type_name))
        return self.context.call_sync('shares.query', params)


@description("NFS shares")
class NFSSharesNamespace(BaseSharesNamespace):
    def __init__(self, name, context):
        super(NFSSharesNamespace, self).__init__(name, 'nfs', context)
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create name=<name> volume=<volume> <property>=<value> ...

            Examples:
                create name=foo volume=tank
                create name=foo volume=tank read_only=true

            Creates an NFS share. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set alldirs=true
                      set read_only=true
                      set root_user=tom
                      set hosts=192.168.1.1, foobar.local

            Sets an NFS share property. For a list of properties, see 'help properties'.""")

        self.add_property(
            descr='All directories',
            name='alldirs',
            get='properties.alldirs',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Read only',
            name='read_only',
            get='properties.read_only',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Root user',
            name='root_user',
            get='properties.maproot_user',
            list=False
        )

        self.add_property(
            descr='Root group',
            name='root_group',
            get='properties.maproot_group',
            list=False
        )

        self.add_property(
            descr='All user',
            name='all_user',
            get='properties.mapall_user',
            list=False
        )

        self.add_property(
            descr='All group',
            name='all_group',
            get='properties.mapall_group',
            list=False
        )

        self.add_property(
            descr='Allowed hosts/networks',
            name='hosts',
            get='properties.hosts',
            list=True,
            type=ValueType.SET
        )

        self.add_property(
            descr='Security',
            name='security',
            get='properties.security',
            list=True,
            type=ValueType.SET
        )


@description("AFP shares")
class AFPSharesNamespace(BaseSharesNamespace):
    def __init__(self, name, context):
        super(AFPSharesNamespace, self).__init__(name, 'afp', context)
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create name=<name> volume=<volume> <property>=<value> ...

            Examples:
                create name=foo volume=tank
                create name=foo volume=tank read_only=true

            Creates an AFP share. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set time_machine=true
                      set read_only=true
                      set users_allow=tom, frank
                      set hosts_allow=192.168.1.1, foobar.local

            Sets an AFP share property. For a list of properties, see 'help properties'.""")

        self.add_property(
            descr='Allowed hosts/networks',
            name='hosts_allow',
            get='properties.hosts_allow',
            type=ValueType.SET
        )

        self.add_property(
            descr='Denied hosts/networks',
            name='hosts_deny',
            get='properties.hosts_deny',
            type=ValueType.SET
        )

        self.add_property(
            descr='Allowed users/groups',
            name='users_allow',
            get='properties.users_allow',
            type=ValueType.SET
        )

        self.add_property(
            descr='Denied users/groups',
            name='users_deny',
            get='properties.users_deny',
            type=ValueType.SET
        )

        self.add_property(
            descr='Read only',
            name='read_only',
            get='properties.read_only',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Time machine',
            name='time_machine',
            get='properties.time_machine',
            list=True,
            type=ValueType.BOOLEAN
        )


@description("SMB shares")
class SMBSharesNamespace(BaseSharesNamespace):
    def __init__(self, name, context):
        super(SMBSharesNamespace, self).__init__(name, 'cifs', context)
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create name=<name> volume=<volume> <property>=<value> ...

            Examples:
                create name=foo volume=tank
                create name=foo volume=tank read_only=true

            Creates a SMB share. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set guest_ok=false
                      set read_only=true
                      set browseable=true
                      set hosts_allow=192.168.1.1, foobar.local

            Sets a SMB share property. For a list of properties, see 'help properties'.""")

        self.add_property(
            descr='Allowed hosts',
            name='hosts_allow',
            get='properties.hosts_allow',
            type=ValueType.SET
        )

        self.add_property(
            descr='Denied hosts',
            name='hosts_deny',
            get='properties.hosts_deny',
            type=ValueType.SET
        )

        self.add_property(
            descr='Read only',
            name='read_only',
            get='properties.read_only',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Guest OK',
            name='guest_ok',
            get='properties.guest_ok',
            list=True,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Guest only',
            name='guest_only',
            get='properties.guest_only',
            list=False,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Browseable',
            name='browseable',
            get='properties.browseable',
            list=False,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='Show hidden files',
            name='show_hidden_files',
            get='properties.show_hidden_files',
            list=False,
            type=ValueType.BOOLEAN
        )


@description("iSCSI portals")
class ISCSIPortalsNamespace(RpcBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context):
        super(ISCSIPortalsNamespace, self).__init__(name, context)
        self.query_call = 'shares.iscsi.portal.query'
        self.create_task = 'share.iscsi.portal.create'
        self.update_task = 'share.iscsi.portal.update'
        self.delete_task = 'share.iscsi.portal.delete'
        self.required_props = ['name', 'listen']
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create name=<name> listen=<hostname>:<port>,<hostname>:<port> <property>=<value> ...

            Examples:
                create name=foo listen=192.168.1.10
                create name=bar listen=127.0.0.1,foobar.local:8888 

            Creates an iSCSI portal. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set discovery_auth_group=somegroup
                      set discovery_auth_method=CHAP
                      set listen=hostname,127.0.0.1,192.168.1.10:8888

            Sets a iSCSI portal property. For a list of properties, see 'help properties'.""")

        self.add_property(
            descr='Group name',
            name='name',
            get='id'
        )

        self.add_property(
            descr='Discovery auth group',
            name='discovery_auth_group',
            get='discovery_auth_group',
            type=ValueType.STRING,
        )

        self.add_property(
            descr='Discovery auth method',
            name='discovery_auth_method',
            get='discovery_auth_method',
            type=ValueType.STRING,
            enum=['NONE', 'CHAP', 'CHAP_MUTUAL']
        )

        self.add_property(
            descr='Listen addresses and ports',
            name='listen',
            get=self.get_portals,
            set=self.set_portals,
            type=ValueType.SET
        )

        self.primary_key = self.get_mapping('name')

    def get_portals(self, obj):
        return ['{address}:{port}'.format(**i) for i in obj['portals']]

    def set_portals(self, obj, value):
        def pack(item):
            ret = item.split(':', 2)
            if not ret[1].isdigit():
                raise CommandException(_("Invalid port number: {0}").format(ret[1]))
            return {
                'address': ret[0],
                'port': int(ret[1]) if len(ret) == 2 else 3260
            }

        obj['portals'] = list(map(pack, value))


@description("iSCSI authentication groups")
class ISCSIAuthGroupsNamespace(RpcBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context):
        super(ISCSIAuthGroupsNamespace, self).__init__(name, context)
        self.query_call = 'shares.iscsi.auth.query'
        self.create_task = 'share.iscsi.auth.create'
        self.update_task = 'share.iscsi.auth.update'
        self.delete_task = 'share.iscsi.auth.delete'
        self.required_props = ['name', 'policy']
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create name=<name> policy=<policy>

            Examples:
                create name=foo policy=NONE
                create name=bar policy=DENY 

            Creates an iSCSI auth group. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set name=newname
                      set policy=CHAP

            Sets a iSCSI auth group property. For a list of properties, see 'help properties'.""")
        
        self.add_property(
            descr='Portal name',
            name='name',
            get='id'
        )

        self.add_property(
            descr='Group policy',
            name='policy',
            get='type',
            type=ValueType.STRING,
            enum=['NONE', 'DENY', 'CHAP', 'CHAP_MUTUAL']
        )

        self.primary_key = self.get_mapping('name')
        self.entity_namespaces = lambda this: [
            ISCSIUsersNamespace('users', self.context, this)
        ]


@description("iSCSI auth users")
class ISCSIUsersNamespace(EntityNamespace):
    def __init__(self, name, context, parent):
        super(ISCSIUsersNamespace, self).__init__(name, context)
        self.parent = parent
        self.required_props = ['name', 'secret']
        self.extra_required_props = [['peer_name', 'peer_secret']]
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create name=<name> secret=<secret>
                   create name=<name> secret=<secret> peer_name<name> peer_secret=<secret>

            Examples:
                create name=foo secret=abcdefghijkl
                create name=bar secret=mnopqrstuvwx peer_name=foo peer_secret=abcdefghijkl

            Creates an iSCSI auth user. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set name=newname
                      set secret=yzabcdefghij
                      set peer_name=bob
                      set peer_secret=klmnopqrstuv

            Sets a iSCSI auth user property. For a list of properties, see 'help properties'.""")

        self.add_property(
            descr='User name',
            name='name',
            get='name'
        )

        self.add_property(
            descr='User secret',
            name='secret',
            get='secret'
        )

        self.add_property(
            descr='Peer user name',
            name='peer_name',
            get='peer_name'
        )

        self.add_property(
            descr='Peer secret',
            name='peer_secret',
            get='peer_secret'
        )

        self.primary_key = self.get_mapping('name')

    def get_one(self, name):
        return first_or_default(lambda a: a['name'] == name, self.parent.entity.get('users', []))

    def query(self, params, options):
        return self.parent.entity['users'] or []

    def save(self, this, new=False):
        if new:
            if self.parent.entity['users'] is None:
                 self.parent.entity['users'] = []
            self.parent.entity['users'].append(this.entity)
        else:
            entity = first_or_default(lambda a: a['name'] == this.entity['name'], self.parent.entity['users'])
            entity.update(this.entity)

        self.parent.save()

    def delete(self, name):
        self.parent.entity['users'] = [a for a in self.parent.entity['users'] if a['name'] == name]
        self.parent.save()


@description("iSCSI targets")
class ISCSITargetsNamespace(RpcBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    def __init__(self, name, context):
        super(ISCSITargetsNamespace, self).__init__(name, context)
        self.query_call = 'shares.iscsi.target.query'
        self.create_task = 'share.iscsi.target.create'
        self.update_task = 'share.iscsi.target.update'
        self.delete_task = 'share.iscsi.target.delete'
        self.required_props = ['name']
        self.localdoc['CreateEntityCommand'] = ("""\
            Usage: create name=<name> <property>=<value> ...

            Examples:
                create name=foo
                create name=bar description="some share" auth_group=somegroup

            Creates an iSCSI target. For a list of properties, see 'help properties'.""")
        self.entity_localdoc['SetEntityCommand'] = ("""\
            Usage: set <property>=<value> ...

            Examples: set name=newname
                      set description="describe me"
                      set auth_group=group

            Sets a iSCSI target property. For a list of properties, see 'help properties'.""")

        self.add_property(
            descr='Target name',
            name='name',
            get='id'
        )

        self.add_property(
            descr='Target description',
            name='description',
            get='description'
        )

        self.add_property(
            descr='Auth group',
            name='auth_group',
            get='auth_group'
        )

        self.primary_key = self.get_mapping('name')
        self.entity_namespaces = lambda this: [
            ISCSITargetMapingNamespace('luns', self.context, this)
        ]


@description("iSCSI luns")
class ISCSITargetMapingNamespace(EntityNamespace):
    def __init__(self, name, context, parent):
        super(ISCSITargetMapingNamespace, self).__init__(name, context)
        self.parent = parent

        self.add_property(
            descr='LUN number',
            name='number',
            get='number',
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Share name',
            name='name',
            get='name'
        )

        self.primary_key = self.get_mapping('name')

    def get_one(self, name):
        return first_or_default(lambda a: a['name'] == name, self.parent.entity['extents'])

    def query(self, params, options):
        return self.parent.entity.get('extents', [])

    def save(self, this, new=False):
        if new:
            self.parent.entity['extents'].append(this.entity)
        else:
            entity = first_or_default(lambda a: a['name'] == this.entity['name'], self.parent.entity['extents'])
            entity.update(this.entity)
            
        self.parent.save()

    def delete(self, name):
        self.parent.entity['extents'] = [a for a in self.parent.entity['extents'] if a['name'] == name]
        self.parent.save()


@description("iSCSI shares")
class ISCSISharesNamespace(BaseSharesNamespace):
    def __init__(self, name, context):
        super(ISCSISharesNamespace, self).__init__(name, 'iscsi', context)

        self.add_property(
            descr='Serial number',
            name='serial',
            get='properties.serial',
            list=True
        )

        self.add_property(
            descr='Size',
            name='size',
            get='properties.size',
            list=True
        )

        self.add_property(
            descr='Block size',
            name='block_size',
            get='properties.block_size'
        )

        self.add_property(
            descr='Physical block size reporting',
            name='physical_block_size',
            get='properties.physical_block_size',
            list=False,
            type=ValueType.BOOLEAN
        )

        self.add_property(
            descr='RPM',
            name='rpm',
            get='properties.rpm',
            list=False,
            enum=['UNKNOWN', 'SSD', '5400', '7200', '10000', '15000']
        )

    def namespaces(self):
        return list(super(ISCSISharesNamespace, self).namespaces()) + [
            ISCSIPortalsNamespace('portals', self.context),
            ISCSITargetsNamespace('targets', self.context),
            ISCSIAuthGroupsNamespace('auth', self.context)
        ]


def _init(context):
    context.attach_namespace('/', SharesNamespace('share', context))
