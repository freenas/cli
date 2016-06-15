import sys
if not getattr(sys, 'frozen', False):
    # this is a namespace package
    __import__('pkg_resources').declare_namespace(__name__)
