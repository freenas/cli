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
from pathlib import PurePath, Path
from freenas.cli.namespace import (
    Command, EntityNamespace, TaskBasedSaveMixin,
    EntitySubscriberBasedLoadMixin, description, CommandException
)
from freenas.cli.output import ValueType
from freenas.cli.complete import EnumComplete, NullComplete, EntitySubscriberComplete


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description("Imports Certificate/CA")
class ImportCertificateCommand(Command):
    """
    Imports a Certificate / CA.
    It is possible to either import certificate from existing file or create an empty certificate entry in database
    and edit it's properties 'certificate' and/or 'privatekey' in external editor.
    Both cases are shown in the 'examples' section

    Usage:
        import name=<name> certificate_path=<value or ""> privatekey_path=<value or "">

    Examples:
    Import existing server certificate from files:
        import type=CERT_EXISTINGS name=importedFromFiles
        certificate_path=/abs/path/cert.crt privatekey_path=/abs/path/cert.key
    Import existing CA from files:
        import type=CA_EXISTING name=importedFromFiles
        certificate_path=/abs/path/cert.crt privatekey_path=/abs/path/cert.key
    Import by creating empty certificate entry and editing the 'certificate' and 'privatekey' fields:
        import type=CERT_EXISTING name=importedByCpyPaste
        importedByCpyPaste edit certificate
        importedByCpyPaste edit privatekey
    """

    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not kwargs:
            raise CommandException(_("Import requires more arguments. For help see 'help import'"))
        if 'type' not in kwargs:
            raise CommandException(_("Please specify type of the imported Certificate. For help see 'help import'"))
        if 'name' not in kwargs:
            raise CommandException(_("Please specify name of the imported Certificate. For help see 'help import'"))

        context.submit_task(self.parent.import_task, kwargs)

    def complete(self, context, **kwargs):
        return [
            NullComplete('name='),
            EnumComplete('type=', ['CERT_EXISTING', 'CA_EXISTING']),
            NullComplete('certificate_path='),
            NullComplete('privatekey_path='),
        ]


@description("Exports private key for selected Certificate/CA to a file")
class ExportPrivatekeyCommand(Command):
    """
    Exports privatekey of selected Certificate / CA to a user specified location.
    Name of the privatekey file will be the same as certificate name with suffix '.key'

    Usage:
        export_privatekey path=/abs/path/to/target/dir

    Examples:
        /crypto mycert export_privatekey path=/mnt/mypool/myexported_certs/
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not kwargs:
            raise CommandException(_("Export requires more arguments."
                                     " For help see '/ crypto <certname> help export_privatekey'"))
        if 'path' not in kwargs:
            raise CommandException(_("Please specify path where the certificate should be exported. "
                                     "For help see '/ crypto <certname> help export_privatekey'"))
        if self.parent.entity['privatekey']:
            p = Path(PurePath(kwargs['path']).joinpath(self.parent.entity['name']).with_suffix('.key'))
            with p.open('w') as f:
                f.writelines(self.parent.entity['privatekey'])

    def complete(self, context, **kwargs):
        return [
            NullComplete('path='),
        ]


@description("Exports Certificate/CA")
class ExportCertificateCommand(Command):
    """
    Exports a Certificate / CA to a user specified location.
    Name of the certificate file will be the same as certificate name with suffix '.crt'

    Usage:
        export_certificate path=/abs/path/to/target/dir

    Examples:
        /crypto mycert export_certificate path=/mnt/mypool/myexported_certs/
    """
    def __init__(self, parent):
        self.parent = parent

    def run(self, context, args, kwargs, opargs):
        if not kwargs:
            raise CommandException(_("Export requires more arguments."
                                     " For help see '/ crypto <certname> help export_certificate'"))
        if 'path' not in kwargs:
            raise CommandException(_("Please specify path where the certificate should be exported. "
                                     "For help see '/ crypto <certname> help export_certificate'"))
        if self.parent.entity['certificate']:
            p = Path(PurePath(kwargs['path']).joinpath(self.parent.entity['name']).with_suffix('.crt'))
            with p.open('w') as f:
                f.writelines(self.parent.entity['certificate'])

    def complete(self, context, **kwargs):
        return [
            NullComplete('path='),
        ]


@description(_("Provides access to Cryptography options"))
class CryptoNamespace(EntitySubscriberBasedLoadMixin, TaskBasedSaveMixin, EntityNamespace):
    """
    The cryptography namespace provides commands for management of the Certificates and Certificate Authorities.
    """
    def __init__(self, name, context):
        super(CryptoNamespace, self).__init__(name, context)
        self.context = context
        self.entity_subscriber_name = 'crypto.certificate'
        self.primary_key_name = 'name'
        self.create_task = 'crypto.certificate.create'
        self.update_task = 'crypto.certificate.update'
        self.import_task = 'crypto.certificate.import'
        self.delete_task = 'crypto.certificate.delete'

        self.localdoc['CreateEntityCommand'] = ("""\
            Crates a Certificate or Certificate Authority. For a list of properties, see 'help properties'.

            Usage:
                create type=<cert-type> name=<cert-name> <property>=<value>

            Examples:
            Create root CA Certificate :
                create type=CA_INTERNAL name=myRootCA selfsigned=yes key_length=2048 digest_algorithm=SHA256
                lifetime=3650 country=PL state=Slaskie city=Czerwionka-Leszczyny
                organization=myCAOrg email=a@b.c common=my_CA_Server
            Create intermediate CA Certificate :
                create type=CA_INTERMEDIATE signing_ca_name=myRootCA name=myInterCA key_length=2048 digest_algorithm=SHA256
                lifetime=365 country=PL state=Slaskie city=Czerwionka-Leszczyny organization=myorg email=a@b.c
                common=MyCommonName
            Create self-signed server certificate without CA:
                create type=CERT_INTERNAL name=mySelfSignedServerCert selfsigned=yes key_length=2048
                digest_algorithm=SHA256 lifetime=365 country=PL state=Slaskie city=Czerwionka-Leszczyny
                organization=myorg email=a@b.c common=www.myserver.com
            Create server certificate signed by internal root CA Certificate:
                create type=CERT_INTERNAL name=myCASignedServerCert signing_ca_name=myRootCA key_length=2048
                digest_algorithm=SHA256 lifetime=365 country=PL state=Slaskie city=Czerwionka-Leszczyny
                organization=myorg email=a@b.c common=www.myserver.com""")

        self.entity_localdoc['DeleteEntityCommand'] = ("""\
            Usage: delete

            Examples: delete

            Deletes the specified certificate.

            !WARNING! Deleting the CA certificate will cause recursive delete
            of all the certificates signed by that CA.""")

        self.localdoc['ListCommand'] = ("""\
            Usage: show

            Examples:
                show
                show | search type == CERT_INTERNAL
                show | search type == CA_EXISTING | sort name

            Lists all certificates, optionally doing filtering and sorting.
            """)

        self.entity_commands = lambda this: {
            'export_certificate': ExportCertificateCommand(this),
            'export_privatekey': ExportPrivatekeyCommand(this)
        }

        self.extra_commands = {
            'import': ImportCertificateCommand(self)
        }

        self.skeleton_entity = {
            'type': None,
        }

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            set='name',
            usage=_("""\
            Name of the certificate.
            """),
            list=True,
        )

        self.add_property(
            descr='Type',
            name='type',
            get='type',
            set='type',
            usage=_("""\
            Certificate type
            """),
            enum=[
                 'CERT_CSR',
                 'CERT_INTERMEDIATE',
                 'CERT_INTERNAL',
                 'CA_INTERMEDIATE',
                 'CA_INTERNAL'
            ],
            list=True,
        )

        self.add_property(
            descr='Serial Number',
            name='serial',
            get='serial',
            set=None,
            usage=_("""\
            Unique serial number of the certificate
            """),
            usersetable=False,
            list=True,
        )

        self.add_property(
            descr='Certificate',
            name='certificate',
            get='certificate',
            set='certificate',
            usage=_("""\
            Certificate contents.
            """),
            type=ValueType.TEXT_FILE,
            createsetable=False,
            usersetable=lambda e: e['type'] in ('CA_EXISTING', 'CERT_EXISTING'),
            list=False,
        )

        self.add_property(
            descr='Certificate Path',
            name='certificate_path',
            get='certificate_path',
            set=None,
            usage=_("""\
            Path to the certificate file.
            """),
            type=ValueType.STRING,
            createsetable=False,
            usersetable=False,
            list=False,
        )

        self.add_property(
            descr='Private Key',
            name='privatekey',
            get='privatekey',
            set='privatekey',
            usage=_("""\
            Private key associated with the certificate.
            """),
            type=ValueType.TEXT_FILE,
            createsetable=False,
            usersetable=lambda e: e['type'] in ('CA_EXISTING', 'CERT_EXISTING'),
            list=False,
        )

        self.add_property(
            descr='Private Key Path',
            name='privatekey_path',
            get='privatekey_path',
            set=None,
            usage=_("""\
            Path to the private key associated with the certificate.
            """),
            type=ValueType.STRING,
            createsetable=False,
            usersetable=False,
            list=False,
        )

        self.add_property(
            descr="Self-signed",
            name='selfsigned',
            get='selfsigned',
            set='selfsigned',
            usage=_("""\
            Boolean value. True if the certificate is 'self-signed', meaning that
            the certificate was not signed by any external Certificate Authority.
            """),
            type=ValueType.BOOLEAN,
            createsetable=True,
            usersetable=False,
            list=True,
            condition=lambda e: e['type'] not in (None, 'CERT_CSR', 'CERT_INTERMEDIATE', 'CA_INTERMEDIATE')
        )

        self.add_property(
            descr="Signing CA",
            name='signing_ca_name',
            get='signing_ca_name',
            set='signing_ca_name',
            usage=_("""\
            Name of the CA signing this certificate.
            """),
            complete=EntitySubscriberComplete(
                'signing_ca_name=',
                self.entity_subscriber_name,
                lambda o: o['name'] if o['type'] in ('CA_INTERNAL', 'CA_INTERMEDIATE') else None
            ),
            createsetable=True,
            usersetable=False,
            list=True,
            condition=lambda e: e['type'] in ('CA_INTERMEDIATE', 'CERT_INTERMEDIATE', 'CA_INTERNAL', 'CERT_INTERNAL')
        )

        self.add_property(
            descr="Signing CA's ID",
            name='signing_ca_id',
            get='signing_ca_id',
            set='signing_ca_id',
            usage=_("""\
            ID of the CA signing this certificate. This field is not user-settable.
            """),
            createsetable=False,
            usersetable=False,
            list=False,
        )

        self.add_property(
            descr='Key length',
            name='key_length',
            get='key_length',
            set='key_length',
            usage=_("""\
            Key length, for security reasons minimun of 2048 is recommanded.
            """),
            type=ValueType.NUMBER,
            usersetable=False,
            list=False,
            condition=lambda e: e['type'] not in (None, ),
        )

        self.add_property(
            descr='Digest algorithm',
            name='digest_algorithm',
            get='digest_algorithm',
            set='digest_algorithm',
            usage=_("""\
            Digest alghoritm for the certificate.
            """),
            enum=['SHA1', 'SHA224', 'SHA256', 'SHA384', 'SHA512'],
            usersetable=False,
            list=False,
            condition=lambda e: e['type'] not in (None, ),
        )

        self.add_property(
            descr='Not Before',
            name='not_before',
            get='not_before',
            set='not_before',
            usage=_("""\
            Certificate's lifetime 'valid from' date.
            """),
            usersetable=False,
            list=True,
            condition=lambda e: e['type'] not in (None, ),
        )

        self.add_property(
            descr='Not After',
            name='not_after',
            get='not_after',
            set='not_after',
            usage=_("""\
            Certificate's lifetime 'valid to' date.
            """),
            usersetable=False,
            list=True,
            condition=lambda e: e['type'] not in (None, ),
        )

        self.add_property(
            descr='Lifetime',
            name='lifetime',
            get='lifetime',
            set='lifetime',
            usage=_("""\
            Certificate lifetime in days, accepts number values"""),
            type=ValueType.NUMBER,
            usersetable=False,
            list=False,
            condition=lambda e: e['type'] not in (None, ),
        )

        self.add_property(
            descr='Country',
            name='country',
            get='country',
            set='country',
            usage=_("""\
            Country of the organization"""),
            usersetable=False,
            list=False,
            condition=lambda e: e['type'] not in (None, ),
        )

        self.add_property(
            descr='State',
            name='state',
            get='state',
            set='state',
            usage=_("""\
            State or province of the organization
            """),
            usersetable=False,
            list=False,
            condition=lambda e: e['type'] not in (None, ),
        )

        self.add_property(
            descr='City',
            name='city',
            get='city',
            set='city',
            usage=_("""\
            Location of the organization
            """),
            usersetable=False,
            list=False,
            condition=lambda e: e['type'] not in (None, ),
        )

        self.add_property(
            descr='Organization',
            name='organization',
            get='organization',
            set='organization',
            usage=_("""\
            Name of the company or organization
            """),
            usersetable=False,
            list=False,
            condition=lambda e: e['type'] not in (None, ),
        )

        self.add_property(
            descr='Common Name',
            name='common',
            get='common',
            set='common',
            usage=_("""\
            Fully qualified domain name of FreeNAS system
            """),
            usersetable=False,
            list=False,
            condition=lambda e: e['type'] not in (None, ),
        )

        self.add_property(
            descr='Email',
            name='email',
            get='email',
            set='email',
            usage=_("""\
            Email address of the person responsible for the certificate
            """),
            usersetable=False,
            list=False,
            condition=lambda e: e['type'] not in (None, ),
        )

        self.primary_key = self.get_mapping('name')


def _init(context):
    context.attach_namespace('/', CryptoNamespace('crypto', context))
    context.map_tasks('crypto.certificate.*', CryptoNamespace)
