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

from freenas.cli.output import format_value


class NullComplete(object):
    def __init__(self, name, **kwargs):
        self.name = name
        self.list = kwargs.pop('list', False)

    def choices(self, context, token):
        return []


class EnumComplete(NullComplete):
    def __init__(self, name, choices, **kwargs):
        def quote(s):
            if s is None:
                return 'none'

            for c in ' \t\n`~!@#$%^&*()-=+[{]}\\|;:\'",<>/?':
                if c in s:
                    return '"{0}"'.format(s)

            return s

        super(EnumComplete, self).__init__(name, **kwargs)
        self.data = list(map(quote, choices))

    def choices(self, context, token):
        return [format_value(i) for i in self.data]


class EntitySubscriberComplete(NullComplete):
    def __init__(self, name, datasource, mapper=None, extra=None, **kwargs):
        super(EntitySubscriberComplete, self).__init__(name, **kwargs)
        self.datasource = datasource
        self.mapper = mapper or (lambda x: x['id'])
        self.extra = extra or []

    def choices(self, context, token):
        return context.entity_subscribers[self.datasource].query(callback=self.mapper) + self.extra


class RpcComplete(EntitySubscriberComplete):
    def __init__(self, name, datasource, mapper=None, extra=None, **kwargs):
        super(RpcComplete, self).__init__(name, datasource, mapper, extra, **kwargs)

    def choices(self, context, token):
        result = []
        for o in list(context.call_sync(self.datasource)) + self.extra:
            r = self.mapper(o)
            if isinstance(r, (list, tuple)):
                result.extend(r)
            else:
                result.append(r)

        return result
