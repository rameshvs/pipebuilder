ROBEXPATH = config.get('Binaries', 'DEMONSPATH')

class ROBEXCommand(Command):
    def __init__(self, comment, **kwargs):
        """
        Command to run ROBEX (robust brain extraction tool)

        Keyword arguments:
        ------------------
        input, output: input and brain-extracted output
        out_mask: output mask (binary image) marking where the brain is
        """
        self.cmd = '/data/vision/polina/shared_software/ROBEX/runROBEX.sh %(input)s %(output)s %(out_mask)s'
        self.outfiles = [kwargs['output'], kwargs['out_mask']]
        Command.__init__(self, comment, **kwargs)

