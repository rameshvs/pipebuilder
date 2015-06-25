import os
import sys

from .core import Command
from .util import config

PYTHON = sys.executable
NIITOOLS_PATH = config.get('Binaries', 'NIITOOLS_PATH')

class NiiToolsMaskedThresholdCountCommand(Command):
    def __init__(self, comment, **kwargs):
        kwargs['labels'] = ' '.join(map(str, kwargs['labels']))
        kwargs.setdefault('exclude', '-')
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' masked_threshold_count %(infile)s %(threshold)g %(output)s %(exclude)s %(label)s %(direction)s %(units)s %(labels)s'
        Command.__init__(self, comment, **kwargs)
class NiiToolsMaskedThresholdCommand(Command):
    def __init__(self, comment, **kwargs):
        kwargs['labels'] = ' '.join(map(str, kwargs['labels']))
        kwargs.setdefault('exclude', '-')
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' masked_threshold %(infile)s %(threshold)g %(output)s %(exclude)s %(label)s %(direction)s %(labels)s'
        Command.__init__(self, comment, **kwargs)
class NiiToolsMatchIntensityCommand(Command):
    def __init__(self, comment, **kwargs):
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' scale_intensity %(inFile)s %(maskFile)s %(intensity)s %(output)s'
        Command.__init__(self, comment, **kwargs)

class NiiToolsTrimCommand(Command):
    def __init__(self, comment, **kwargs):
        kwargs['bbox'] = ' '.join(map(str, kwargs.pop('bbox')))
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' trim %(input)s %(output)s %(bbox)s'
        Command.__init__(self, comment, **kwargs)

class NiiToolsConvertTypeCommand(Command):
    def __init__(self, comment, **kwargs):
        kwargs.setdefault('normalization', 'none')
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' convert_type %(input)s %(output)s %(type)s %(normalization)s'
        Command.__init__(self, comment, **kwargs)

class NiiToolsGaussianBlurCommand(Command):
    def __init__(self, comment, **kwargs):
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' gaussian_blur %(input)s %(output)s %(sigma)g'
        Command.__init__(self, comment, **kwargs)

class NiiToolsCountLabelCommand(Command):
    def __init__(self, comment, **kwargs):
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' count_labels %(input)s %(output)s %(labels)s'
        Command.__init__(self, comment, **kwargs)

class NiiToolsWarpSSDCommand(Command):
    def __init__(self, comment, **kwargs):
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' warp_ssd %(in1)s %(in2)s %(template)s %(output)s'
        Command.__init__(self, comment, **kwargs)

class NiiToolsJaccardCommand(Command):
    def __init__(self, comment, **kwargs):
        kwargs.setdefault('labels', '2 3 4 41 42 43')
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' jaccard %(in1)s %(in2)s %(output)s %(labels)s'
        Command.__init__(self, comment, **kwargs)

class NiiToolsDiceCommand(Command):
    def __init__(self, comment, **kwargs):
        kwargs.setdefault('labels', '2 3 4 41 42 43')
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' dice %(in1)s %(in2)s %(output)s %(labels)s'
        Command.__init__(self, comment, **kwargs)

class NiiToolsUpsampleCommand(Command):
    def __init__(self, comment, **kwargs):
        kwargs.setdefault('axis', 2)
        kwargs.setdefault('method', 'linear')
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' upsample %(input)s %(output)s %(out_mask)s %(axis)d %(ratio)g %(method)s'
        Command.__init__(self, comment, **kwargs)

class NiiToolsMergeWarpCommand(Command):
    def __init__(self, comment, **kwargs):
        kwargs.setdefault('dimension', 3)
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' merge %(dimension)s %(in_pattern)s %(template_warp)s %(output)s'
        Command.__init__(self, comment, **kwargs)

class NiiToolsSplitWarpCommand(Command):
    def __init__(self, comment, **kwargs):
        kwargs.setdefault('dimension', 3)
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' split %(dimension)s %(infile)s %(out_template)s'
        self.outfiles = [kwargs['out_template'] % i for i in xrange(kwargs['dimension'])]
        Command.__init__(self, comment, **kwargs)

class NiiToolsMaskCommand(Command):
    def __init__(self, comment, **kwargs):
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' mask %(input)s %(mask)s %(output)s'
        Command.__init__(self, comment, **kwargs)

class NiiToolsSSDCommand(Command):
    def __init__(self, comment, **kwargs):
        self.cmd = PYTHON + ' ' + NIITOOLS_PATH + ' ssd %(in1)s %(in2)s %(output)s'
        Command.__init__(self, comment, **kwargs)
