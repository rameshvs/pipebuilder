import os
import sys

from .core import Command
from .util import config

MCC_BINARY_PATH = config.get('Binaries', 'MCC_BINARY_PATH')
MCR = config.get('Binaries', 'MCR_PATH')

############################################
# Commands for using MCC-compiled binaries #
############################################
class MCCCommand(Command): # abstract class
    prefix = os.path.join(MCC_BINARY_PATH, 'MCC_%(matlabName)s/run_%(matlabName)s.sh ') + MCR + ' '
    def __init__(self, comment, **kwargs):
        """ Arguments: matlabName, ... """
        self.cmd = self.prefix
        raise NotImplementedError # Abstract class

class MCCInputOutputCommand(MCCCommand):
    def __init__(self, comment, **kwargs):
        """ See MCCCommand. Arguments: matlabName, input, output """
        self.cmd = (self.prefix + '%(input)s %(output)s')
        Command.__init__(self, comment, **kwargs)

class MCCPadCommand(MCCCommand):
    def __init__(self, comment, **kwargs):
        """ See MCCCommand. Arguments: input, output, out_mask """
        kwargs['matlabName'] = 'padNii'
        self.cmd = (self.prefix + '%(input)s %(output)s %(out_mask)s')
        Command.__init__(self, comment, **kwargs)

class MCCHistEqCommand(MCCCommand):
    def __init__(self, comment, **kwargs):
        """ See MCCCommand. Arguments: input, output, ref_hist. does 'cut' only """
        kwargs['matlabName'] = 'doHistogramEqualization'
        self.cmd = (self.prefix + '%(ref_hist)s %(output)s %(input)s cut')
        Command.__init__(self, comment, **kwargs)

class MCCMatchWMCommand(MCCCommand):
    def __init__(self, comment, **kwargs):
        kwargs['matlabName'] = 'matchWM'
        self.cmd = self.prefix + '%(inFile)s %(maskFile)s %(intensity)s %(output)s'
        Command.__init__(self, comment, **kwargs)

class MCCUpsampleNiiCommand(MCCCommand):
    def __init__(self, comment, **kwargs):
        """ See MCCCommand. Arguments input, output, out_mask """
        kwargs['matlabName'] = 'niiUpsample'
        self.cmd = self.prefix + '%(input)s %(output)s %(out_mask)s'
        Command.__init__(self, comment, **kwargs)

