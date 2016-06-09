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
from freenas.cli.complete import NullComplete
from freenas.cli.output import ValueType

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description(_("Exchange keys with remote host and create known replication peer entry at both sides"))
class CreateReplicationPeerCommand(Command):
    """
    Usage: create <address> username=<username> password=<password>

    Example: create my_peer address=10.0.0.1 username=my_username
                    password=secret
             create my_peer address=my_username@10.0.0.1 password=secret
             create name=my_peer address=my_username@10.0.0.1 password=secret
                    port=1234

    Exchange keys with remote host and create known replication host entry
    at both sides.

    User name and password are used only once to authorize key exchange.
    Default SSH port is 22.

    User used for pairing purposes must belong to 'wheel' group at remote host.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args and not kwargs:
            raise CommandException(_("Create requires more arguments, see 'help create' for more information"))
        if len(args) > 1:
            raise CommandException(_("Wrong syntax for create, see 'help create' for more information"))

        if len(args) == 1:
            kwargs['name'] = args.pop(0)

        if 'name' not in kwargs:
            raise CommandException(_('Please specify a name for your peer'))
        else:
            name = kwargs.pop('name')

        if 'address' not in kwargs:
            raise CommandException(_('Please specify an address of your remote'))
        else:
            address = kwargs.pop('address')

        split_address = address.split('@')
        if len(split_address) == 2:
            kwargs['username'] = split_address[0]
            address = split_address[1]

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
            {
                'name': name,
                'address': address,
                'type': 'replication',
                'credentials': {
                    'username': username,
                    'password': password,
                    'port': port
                }
            }
        )

    def complete(self, context):
        return [
            NullComplete('name='),
            NullComplete('address='),
            NullComplete('username='),
            NullComplete('password='),
            NullComplete('port=')
        ]


class BasePeerNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    def __init__(self, name, type_name, context):
        super(BasePeerNamespace, self).__init__(name, context)

        self.context = context
        self.type_name = type_name
        self.entity_subscriber_name = 'peer'
        self.extra_query_params = [('type', '=', type_name)]
        self.create_task = 'peer.create'
        self.update_task = 'peer.update'
        self.delete_task = 'peer.delete'
        self.required_props = ['name', ['address', 'type', 'credentials']]

        self.skeleton_entity = {
            'type': type_name
        }

        self.add_property(
            descr='Peer Name',
            name='name',
            get='name',
            set=None,
            createsetable=False,
            usersetable=False
        )

        self.add_property(
            descr='Peer Type',
            name='type',
            get='type'
        )

        self.add_property(
            descr='Peer address',
            name='address',
            get='address',
            set=None,
            createsetable=False,
            usersetable=False
        )

        self.primary_key = self.get_mapping('name')
        self.primary_key_name = 'name'
        self.save_key_name = 'id'


@description(_("Manage replication peers"))
class ReplicationPeerNamespace(BasePeerNamespace):
    """
    The replication peer namespace provides commands for listing and managing replication peers.
    """
    def __init__(self, name, context):
        super(ReplicationPeerNamespace, self).__init__(name, 'replication', context)

        self.add_property(
            descr='Port',
            name='port',
            get='credentials.port',
            list=False,
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Public key',
            name='pubkey',
            get='credentials.pubkey',
            list=False
        )

        self.add_property(
            descr='Host key',
            name='hostkey',
            get='credentials.hostkey',
            list=False
        )

    def commands(self):
        cmds = super(ReplicationPeerNamespace, self).commands()
        cmds.update({'create': CreateReplicationPeerCommand(self)})
        return cmds


@description(_("Manage SSH peers"))
class SSHPeerNamespace(BasePeerNamespace):
    """
    The SSH peer namespace provides commands for listing and managing SSH peers.
    """
    def __init__(self, name, context):
        super(SSHPeerNamespace, self).__init__(name, 'ssh', context)

        self.add_property(
            descr='Username',
            name='username',
            get='credentials.username',
            list=False
        )

        self.add_property(
            descr='Password',
            name='password',
            get='credentials.password',
            list=False
        )

        self.add_property(
            descr='Port',
            name='port',
            get='credentials.port',
            list=False,
            type=ValueType.NUMBER
        )

        self.add_property(
            descr='Public key',
            name='pubkey',
            get='credentials.pubkey',
            list=False
        )

        self.add_property(
            descr='Host key',
            name='hostkey',
            get='credentials.hostkey',
            list=False
        )


@description(_("Manage Amazon S3 peers"))
class AmazonS3Namespace(BasePeerNamespace):
    """
    The Amazon S3 peer namespace provides commands for listing and managing Amazon S3 peers.
    """
    def __init__(self, name, context):
        super(AmazonS3Namespace, self).__init__(name, 'amazon-s3', context)

        self.add_property(
            descr='Access key',
            name='access_key',
            get='credentials.access_key',
            list=False
        )

        self.add_property(
            descr='Secret key',
            name='secret_key',
            get='credentials.secret_key',
            list=False
        )

        self.add_property(
            descr='Region',
            name='region',
            get='credentials.region',
            list=False
        )

        self.add_property(
            descr='Bucket',
            name='bucket',
            get='credentials.bucket',
            list=False
        )

        self.add_property(
            descr='Folder',
            name='folder',
            get='credentials.folder',
            list=False
        )


@description("Configure and manage peers")
class PeerNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The peer namespace contains the namespaces
    for managing SSH, replication and Amazon S3
    peers.
    """
    def __init__(self, name, context):
        super(PeerNamespace, self).__init__(name, context)
        self.context = context
        self.entity_subscriber_name = 'peer'
        self.primary_key_name = 'name'
        self.allow_create = False

        self.add_property(
            descr='Peer Name',
            name='name',
            get='name',
            set=None,
            createsetable=False,
            usersetable=False
        )

        self.add_property(
            descr='Peer Type',
            name='type',
            get='type',
            set=None,
            createsetable=False,
            usersetable=False
        )

        self.add_property(
            descr='Peer address',
            name='address',
            get='address',
            set=None,
            createsetable=False,
            usersetable=False
        )

    def namespaces(self):
        return [
            ReplicationPeerNamespace('replication', self.context),
            SSHPeerNamespace('ssh', self.context),
            AmazonS3Namespace('amazons3', self.context)
        ]


def _init(context):
    context.attach_namespace('/', PeerNamespace('peer', context))
