#!/usr/bin/env python
from __future__ import print_function

import sys, os
import subprocess
import json
import tempfile
import hashlib
import base64

def main(argv):
    USAGE = '{} <args>' \
        'Runs command line in <args> and writes metadata to task files'
    #(global_json_file, task_json_file) = sys.argv[1:3]
    prefix = argv[1]
    cmd = ' '.join(argv[2:])

    cmdline_hash = base64.urlsafe_b64encode(hashlib.md5(cmd).digest())

    # TODO input checking
    print('\n    '.join(argv[2:]))
    proc = subprocess.Popen(argv[2:], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

    (stdout, stderr) = proc.communicate()
    retcode = proc.returncode

    summary = {'stdout': stdout, 'stderr': stderr, 'retcode': retcode}
    # redundancy for convenience: these shouldn't be THAT big anyway
    with open(prefix + '_summary.json', 'w') as f:
        json.dump(summary, f)
    with open(prefix + '_stdout', 'w') as f:
        f.write(stdout)
    with open(prefix + '_stderr', 'w') as f:
        f.write(stderr)
    with open(prefix + '_retcode', 'w') as f:
        f.write(str(retcode))
    print(stdout)
    print(stderr, file=sys.stderr)

    sys.exit(retcode)

if __name__ == '__main__':
    main(sys.argv)
