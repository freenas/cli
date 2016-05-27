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
from freenas.cli.output import ValueType


t = gettext.translation('freenas-cli', fallback=True)
_ = t.gettext


@description(_("Provides access to Cryptography options"))
class CryptoNamespace(Namespace):
    """
    The cryptography namespace is used to manage crypthography related
    aspects of the system.
    """
    def __init__(self, name, context):
        super(CryptoNamespace, self).__init__(name)
        self.context = context

    def namespaces(self):
        return [
            CertificateNamespace('certificate', self.context),
            CertificateAuthorityNamespace('ca', self.context)
        ]


@description(_("Provides access to Certificate Authority actions"))
class CertificateAuthorityNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The Certificate Authority namespace provides commands for listing and managing CAs.
    """
    def __init__(self, name, context):
        super(CertificateAuthorityNamespace, self).__init__(name, context)

        self.entity_subscriber_name = 'crypto.certificate'
        self.create_task = 'crypto.certificate.create'
        self.update_task = 'crypto.certificate.update'
        self.import_task = 'crypto.certificate.import'
        self.delete_task = 'crypto.certificate.delete'
        self.primary_key_name = 'name'

        self.localdoc['CreateEntityCommand'] = ("""\
            Examples: create type=CA_INTERNAL name=myCA key_length=2048 digest_algorithm=SHA256
            lifetime=3650 country=PL state=Slaskie city=Czerwionka-Leszczyny organization=myorg email=a@b.c
            common=MyCommonName

            Crates a Certificate Authority. For a list of properties, see 'help properties'.""")

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            set='name',
            list=True)

        self.add_property(
            descr='Type',
            name='type',
            get='type',
            set='type',
            enum=[
                'CA_EXISTING',
                'CA_INTERMEDIATE',
                'CA_INTERNAL'
            ],
            list=True)

        self.add_property(
            descr='Certificate',
            name='certificate',
            get='certificate',
            set='certificate',
            condition=lambda e: e['type'] == 'CA_EXISTING',
            list=True)

        self.add_property(
            descr='Private Key',
            name='privatekey',
            get='privatekey',
            set='privatekey',
            condition=lambda e: e['type'] == 'CA_EXISTING',
            list=True)

        self.add_property(
            descr='Serial',
            name='serial',
            get='serial',
            set='serial',
            condition=lambda e: e['type'] == 'CA_EXISTING',
            list=True)

        self.add_property(
            descr='Key length',
            name='key_length',
            get='key_length',
            set='key_length',
            type=ValueType.NUMBER,
            condition=lambda e: e['type'] != 'CA_EXISTING',
            list=True)

        self.add_property(
            descr='Digest algorithm',
            name='digest_algorithm',
            get='digest_algorithm',
            set='digest_algorithm',
            enum=['SHA1', 'SHA224', 'SHA256', 'SHA384', 'SHA512'],
            condition=lambda e: e['type'] != 'CA_EXISTING',
            list=True)

        self.add_property(
            descr='Lifetime',
            name='lifetime',
            get='lifetime',
            set='lifetime',
            condition=lambda e: e['type'] != 'CA_EXISTING',
            type=ValueType.NUMBER,
            list=True)

        self.add_property(
            descr='Country Code',
            name='country',
            get='country',
            set='country',
            condition=lambda e: e['type'] != 'CA_EXISTING',
            list=True)

        self.add_property(
            descr='State',
            name='state',
            get='state',
            set='state',
            condition=lambda e: e['type'] != 'CA_EXISTING',
            list=True)

        self.add_property(
            descr='City',
            name='city',
            get='city',
            set='city',
            condition=lambda e: e['type'] != 'CA_EXISTING',
            list=True)

        self.add_property(
            descr='Organization',
            name='organization',
            get='organization',
            set='organization',
            condition=lambda e: e['type'] != 'CA_EXISTING',
            list=True)

        self.add_property(
            descr='Common Name',
            name='common',
            get='common',
            set='common',
            condition=lambda e: e['type'] != 'CA_EXISTING',
            list=True)

        self.add_property(
            descr='Email',
            name='email',
            get='email',
            set='email',
            condition=lambda e: e['type'] != 'CA_EXISTING',
            list=True)

        self.add_property(
            descr='Signing CA',
            name='signedby',
            get='signedby',
            set='signedby',
            condition=lambda e: e['type'] == 'CA_INTERMEDIATE',
            list=True)

        self.primary_key = self.get_mapping('name')


@description(_("Provides access to Certificate actions"))
class CertificateNamespace(TaskBasedSaveMixin, EntitySubscriberBasedLoadMixin, EntityNamespace):
    """
    The certificates namespace provides commands for listing and managing cryptography certificates.
    """
    def __init__(self, name, context):
        super(CertificateNamespace, self).__init__(name, context)

        self.entity_subscriber_name = 'crypto.certificate'
        self.create_task = 'crypto.certificate.create'
        self.update_task = 'crypto.certificate.update'
        self.import_task = 'crypto.certificate.import'
        self.delete_task = 'crypto.certificate.delete'
        self.primary_key_name = 'name'

        self.localdoc['CreateEntityCommand'] = ("""\
            Examples: create type=CERT_INTERNAL name=myCert signedby=myCA key_length=2048
            digest_algorithm=SHA256 lifetime=3650 country=PL state=Slaskie city=Czerwionka-Leszczyny
            organization=myorg email=a@b.c common=MyCommonName

            Crates a certificate. For a list of properties, see 'help properties'.""")

        self.add_property(
            descr='Name',
            name='name',
            get='name',
            set='name',
            list=True)

        self.add_property(
            descr='Type',
            name='type',
            get='type',
            set='type',
            enum=[
                'CERT_CSR',
                'CERT_EXISTING',
                'CERT_INTERMEDIATE',
                'CERT_INTERNAL',
            ],
            list=True)

        self.add_property(
            descr='Certificate',
            name='certificate',
            get='certificate',
            set='certificate',
            condition=lambda e: e['type'] == 'CERT_EXISTING',
            list=True)

        self.add_property(
            descr='Private Key',
            name='privatekey',
            get='privatekey',
            set='privatekey',
            condition=lambda e: e['type'] == 'CERT_EXISTING',
            list=True)

        self.add_property(
            descr='Signing CA',
            name='signedby',
            get='signedby',
            set='signedby',
            usage=_("""\
            Signing CA's name, accepts string values"""),
            condition=lambda e: e['type'] != 'CERT_EXISTING' and e['type'] != 'CERT_CSR',
            list=True)

        self.add_property(
            descr='Key length',
            name='key_length',
            get='key_length',
            set='key_length',
            type=ValueType.NUMBER,
            condition=lambda e: e['type'] != 'CERT_EXISTING',
            list=True)

        self.add_property(
            descr='Digest algorithm',
            name='digest_algorithm',
            get='digest_algorithm',
            set='digest_algorithm',
            enum=['SHA1', 'SHA224', 'SHA256', 'SHA384', 'SHA512'],
            condition=lambda e: e['type'] != 'CERT_EXISTING',
            list=True)

        self.add_property(
            descr='Lifetime',
            name='lifetime',
            get='lifetime',
            set='lifetime',
            type=ValueType.NUMBER,
            condition=lambda e: e['type'] != 'CERT_EXISTING',
            list=True)

        self.add_property(
            descr='Country',
            name='country',
            get='country',
            set='country',
            condition=lambda e: e['type'] != 'CERT_EXISTING',
            list=True)

        self.add_property(
            descr='State',
            name='state',
            get='state',
            set='state',
            condition=lambda e: e['type'] != 'CERT_EXISTING',
            list=True)

        self.add_property(
            descr='City',
            name='city',
            get='city',
            set='city',
            condition=lambda e: e['type'] != 'CERT_EXISTING',
            list=True)

        self.add_property(
            descr='Organization',
            name='organization',
            get='organization',
            set='organization',
            condition=lambda e: e['type'] != 'CERT_EXISTING',
            list=True)

        self.add_property(
            descr='Common Name',
            name='common',
            get='common',
            set='common',
            condition=lambda e: e['type'] != 'CERT_EXISTING',
            list=True)

        self.add_property(
            descr='Email',
            name='email',
            get='email',
            set='email',
            condition=lambda e: e['type'] != 'CERT_EXISTING',
            list=True)

        self.primary_key = self.get_mapping('name')


def _init(context):
    #context.attach_namespace('/', CryptoNamespace('crypto', context))
    pass
