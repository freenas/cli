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
from datetime import datetime
from freenas.cli.namespace import (
    Command, CommandException, EntityNamespace, TaskBasedSaveMixin,
    EntitySubscriberBasedLoadMixin, description
)
from freenas.cli.complete import NullComplete, RpcComplete
from freenas.cli.output import ValueType, Sequence, Table
from freenas.cli.utils import TaskPromise
from freenas.utils import first_or_default

t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description(_("Exchange keys with remote host and create known FreeNAS peer entry at both sides"))
class CreateFreeNASPeerCommand(Command):
    """
    Usage: create name=<name> address=<address> username=<username>
                  password=<password> token=<token>

    Example: create address=freenas-2.local username=root password=secret
             create address=10.0.0.1 username=my_username password=secret
             create address=my_username@10.0.0.1 password=secret
             create address=my_username@10.0.0.1 password=secret port=1234
             create address=freenas-2.local token=123456

    Exchange keys with remote host and create known FreeNAS host entry
    at both sides.

    FreeNAS peer name always equals to the remote host name.

    User name and password are used only once to authorize key exchange.
    Default SSH port is 22.

    Peer creation using authentication tokens have two steps:
    before issuing actual 'create' command, one has to generate
    a temporary token on remote machine via 'get_token' command.

    User used for pairing purposes must belong to 'wheel' group at remote host.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args and not kwargs:
            raise CommandException(_("Create requires more arguments, see 'help create' for more information"))
        if len(args) > 0:
            raise CommandException(_("Wrong syntax for create, see 'help create' for more information"))

        if 'address' not in kwargs:
            raise CommandException(_('Please specify an address of your remote'))
        else:
            address = kwargs.pop('address')

        port = kwargs.pop('port', 22)

        token = kwargs.get('token')

        if token:
            tid = context.submit_task(
                self.parent.create_task,
                {
                    'type': 'freenas',
                    'credentials': {
                        'port': port,
                        'type': 'freenas-auth',
                        'address': address,
                        'auth_code': token
                    }
                }
            )
        else:
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

            tid = context.submit_task(
                self.parent.create_task,
                {
                    'type': 'freenas',
                    'credentials': {
                        'username': username,
                        'password': password,
                        'port': port,
                        'type': 'freenas-auth',
                        'address': address
                    }
                }
            )

        return TaskPromise(context, tid)

    def complete(self, context, **kwargs):
        return [
            NullComplete('name='),
            NullComplete('address='),
            NullComplete('username='),
            NullComplete('password='),
            NullComplete('port='),
            NullComplete('token=')
        ]


@description(_("Generate FreeNAS peer one-time authentication token"))
class FreeNASPeerGetAuthTokenCommand(Command):
    """
    Usage: create_token

    Example: create_token

    Creates an authentication token which is valid for 5 minutes.
    This token can be used on other FreeNAS machine to set up a FreeNAS peer.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        return Sequence(
            'One time authentication code:',
            context.call_sync('peer.freenas.create_auth_code')
        )


@description(_("Invalidate selected FreeNAS peer one-time authentication token"))
class FreeNASPeerInvalidateTokenCommand(Command):
    """
    Usage: invalidate_token token=<token>

    Example: invalidate_token token=123456
             invalidate_token 123456
             invalidate_token 12****
             invalidate_token 12

    Invalidates selected FreeNAS peer one-time authentication token.
    You have to enter at least two first digits of a valid token.
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not args and not kwargs:
            raise CommandException(_("Command invalidate_token requires more arguments."))
        if len(args) > 1:
            raise CommandException(_("Wrong syntax for invalidate_token."))

        if len(args) == 1 and not kwargs.get('token'):
            kwargs['token'] = args.pop(0)

        if 'token' not in kwargs:
            raise CommandException(_('Please specify a valid token'))
        else:
            token = str(kwargs.pop('token'))

        try:
            if token.index('*') < 2:
                raise CommandException(_('You have to enter at least first two digits of a valid token.'))
        except ValueError:
            pass

        match = first_or_default(
            lambda c: c['code'][:2] == token[:2],
            context.call_sync('peer.freenas.get_auth_codes')
        )
        if not match:
            return Sequence(
                'No matching code found. You might have entered wrong token, or it has already expired.'
            )
        else:
            if match['code'] == token:
                token = match

            context.call_sync('peer.freenas.invalidate_code', token)

    def complete(self, context, **kwargs):
        return [
            RpcComplete('token=', 'peer.freenas.get_auth_codes', lambda c: c['code'])
        ]


@description(_("List valid FreeNAS authentication tokens"))
class FreeNASPeerListTokensCommand(Command):
    """
    Usage: list_tokens

    Example: list_tokens

    Lists valid FreeNAS authentication tokens.
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        codes = list(context.call_sync('peer.freenas.get_auth_codes'))
        for c in codes:
            remaining_time = c['expires_at'] - datetime.now()
            remaining_time = int(remaining_time.total_seconds())
            if remaining_time < 0:
                c['lifetime'] = 'Expired {0} seconds ago'.format(abs(remaining_time))
            else:
                c['lifetime'] = 'Expires in {0} seconds'.format(remaining_time)

        return Table(
            codes, [
                Table.Column('Token', 'code', ValueType.STRING),
                Table.Column('Lifetime', 'lifetime', ValueType.STRING)
            ]
        )


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
        self.required_props = ['name', ['type', 'credentials']]

        self.skeleton_entity = {
            'type': type_name,
            'credentials': {
                'type': type_name
            }
        }

        self.add_property(
            descr='Peer Name',
            name='name',
            get='name',
            usage=_('Name of a peer.')
        )

        self.add_property(
            descr='Peer Type',
            name='type',
            get='type',
            usersetable=False,
            usage=_('Type of a peer.')
        )

        self.primary_key = self.get_mapping('name')
        self.primary_key_name = 'name'
        self.save_key_name = 'id'


@description(_("Manage FreeNAS peers"))
class FreeNASPeerNamespace(BasePeerNamespace):
    """
    The FreeNAS peer namespace provides commands for listing and managing FreeNAS peers.
    """
    def __init__(self, name, context):
        super(FreeNASPeerNamespace, self).__init__(name, 'freenas', context)

        self.add_property(
            descr='Port',
            name='port',
            get='credentials.port',
            list=False,
            type=ValueType.NUMBER,
            usage=_('SSH port used to reach a FreeNAS peer.')
        )

        self.add_property(
            descr='Public key',
            name='pubkey',
            get='credentials.pubkey',
            list=False,
            usage=_('Public SSH key of a FreeNAS peer.')
        )

        self.add_property(
            descr='Host key',
            name='hostkey',
            get='credentials.hostkey',
            list=False,
            usage=_('SSH host key of a FreeNAS peer.')
        )

        self.add_property(
            descr='Peer address',
            name='address',
            get='credentials.address',
            usersetable=False,
            usage=_('Address of a FreeNAS peer.')
        )

        name_mapping = self.get_mapping('name')
        name_mapping.usersetable = False

    def commands(self):
        cmds = super(FreeNASPeerNamespace, self).commands()
        cmds.update({
            'create': CreateFreeNASPeerCommand(self),
            'create_token': FreeNASPeerGetAuthTokenCommand(self),
            'invalidate_token': FreeNASPeerInvalidateTokenCommand(self),
            'list_tokens': FreeNASPeerListTokensCommand(self)
        })
        return cmds


@description(_("Manage SSH peers"))
class SSHPeerNamespace(BasePeerNamespace):
    """
    The SSH peer namespace provides commands for listing and managing SSH peers.
    """
    def __init__(self, name, context):
        super(SSHPeerNamespace, self).__init__(name, 'ssh', context)

        self.add_property(
            descr='Peer address',
            name='address',
            get='credentials.address',
            usage=_('Address of a SSH peer.')
        )

        self.add_property(
            descr='Username',
            name='username',
            get='credentials.username',
            list=False,
            usage=_('Username used to connect to a SSH peer.')
        )

        self.add_property(
            descr='Password',
            name='password',
            get='credentials.password',
            list=False,
            usage=_('Password used to connect to a SSH peer.')
        )

        self.add_property(
            descr='Port',
            name='port',
            get='credentials.port',
            list=False,
            type=ValueType.NUMBER,
            usage=_('SSH port used to connect to a SSH peer.')
        )

        self.add_property(
            descr='Private key',
            name='privkey',
            get='credentials.privkey',
            list=False,
            usage=_('Private SSH peer used to connect to SSH peer.')
        )

        self.add_property(
            descr='Host key',
            name='hostkey',
            get='credentials.hostkey',
            list=False,
            usage=_('SSH host key of a SSH peer.')
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
            list=False,
            usage=_('Access key to Amazon S3.')
        )

        self.add_property(
            descr='Secret key',
            name='secret_key',
            get='credentials.secret_key',
            list=False,
            usage=_('Secret key to Amazon S3.')
        )

        self.add_property(
            descr='Region',
            name='region',
            get='credentials.region',
            list=False,
            usage=_('Region property used to connect to Amazon S3 peer.')
        )

        self.add_property(
            descr='Bucket',
            name='bucket',
            get='credentials.bucket',
            list=False,
            usage=_('Bucket property used to connect to Amazon S3 peer.')
        )

        self.add_property(
            descr='Folder',
            name='folder',
            get='credentials.folder',
            list=False,
            usage=_('Folder property used to connect to Amazon S3 peer.')
        )


@description("Configure and manage peers")
class PeerNamespace(EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The peer namespace contains the namespaces
    for managing SSH, FreeNAS and Amazon S3
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
            usersetable=False,
            usage=_('Name of a peer.')
        )

        self.add_property(
            descr='Peer Type',
            name='type',
            get='type',
            set=None,
            createsetable=False,
            usersetable=False,
            usage=_('Type of a peer.')
        )

    def namespaces(self):
        return [
            FreeNASPeerNamespace('freenas', self.context),
            SSHPeerNamespace('ssh', self.context),
            AmazonS3Namespace('amazons3', self.context)
        ]


def _init(context):
    context.attach_namespace('/', PeerNamespace('peer', context))
