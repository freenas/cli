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


def parse_query_args(args, kwargs):
    filters = []
    params = {}

    if 'limit' in kwargs:
        params['limit'] = int(kwargs['limit'])

    return filters, params


def list_split(lst, delimiter):
    """
    Simple helper function to split list by the specified delimiter (e.g: '\n')
    This function returns two lists. The first contains the sublist from the
    beginning of the supplied list to the very fist occurence of the delimiter.
    The second contains the the later half of the supplied list. (delimiter
    not included).

    In the event of the delimiter not being found it returns the first list
    as is and the second as an empty list ([])
    """
    try:
        idx = lst.index(delimiter)
        return lst[:idx], lst[idx+1:]
    except ValueError:
        return lst, []


def iterate_vdevs(topology):
    for group in list(topology.values()):
        for vdev in group:
            if vdev['type'] == 'disk':
                yield vdev
            elif 'children' in vdev:
                for subvdev in vdev['children']:
                    yield subvdev


def post_save(this, status):
    """
    Generic post-save callback for EntityNamespaces
    """
    if status == 'FINISHED':
        this.saved = True
    if status in ['FINISHED', 'FAILED', 'ABORTED', 'CANCELLED']:
        this.modified = False
        this.load()
