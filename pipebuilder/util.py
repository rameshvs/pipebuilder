import os
import collections
import ConfigParser

THIS_DIR = os.path.dirname(os.path.realpath(__file__))

config = ConfigParser.ConfigParser()
config.read(os.path.join(THIS_DIR, '..', 'site.cfg'))

def get_filebase(filename):
    """
    Returns a file's base name without an extension:
    e.g., takes '/foo/bar/hello.nii.gz' and returns 'hello'
    """
    base_ext = filename.split(os.path.sep)[-1]
    return base_ext.split('.')[0]

def ordered_unique(items):
    items = [x for x in items if x is not None]
    return list(collections.OrderedDict.fromkeys(items))

def add_extension(str):
    ex = '{extension}'
    if str.endswith(ex):
        return str
    else:
        return str + ex

