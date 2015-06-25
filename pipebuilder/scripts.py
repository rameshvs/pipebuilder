
from .core import Command
from .util import config

###############################
# Commands for simple scripts #
###############################
class InputOutputShellCommand(Command):
    def __init__(self, comment, **kwargs):
        """
        Runs a simple command of the form <cmdName> <input> <output> <extra_args>

        Parameters:
        -----------
        comment : a short string describing what your command does

        Keyword arguments:
        ------------------
        input, output : filenames
        cmdName : name of command/script (must be on PATH or fully qualified)
        extra_args: additional command line arguments (*not* outputs)

        Example:
        converter = InputOutputShellCommand('/path/to/freesurfer/bin/mri_convert',
                                            input='/path/to/data/img1.mgz',
                                            output='/path/to/data/img2.nii.gz')
        """
        self.cmd = "%(cmdName)s %(input)s %(output)s %(extra_args)s"
        if 'extra_args' not in kwargs:
            kwargs['extra_args'] = ''
        Command.__init__(self, comment, **kwargs)

class PyFunctionCommand(Command):
    def __init__(self, comment, function, args, output_positions=[]):
        """
        Command to run a python function. Function must passed as
        a string of the form 'module.function', and the module must
        be on the current path.

        args is a list of strings with the arguments to the function (right
        now only strings are supported). Strings with quotes of any kind in them
        may not work properly (untested).

        output_positions is an optional list of indices into args that
        say which ones are output files.

        All of the function's parameters and all of the arguments must be
        strings (this limitation will hopefully be removed in a future
        version).
        """
        import sys
        (module, funcname) = function.rsplit('.', 1)
        # TODO trim this to where the module is
        path = sys.path + [os.getcwd()]
        self.cmd =\
            "python -c \"import sys; sys.path.extend(%(path)s);" \
            "import %(module)s; %(module)s.%(func)s(%(arg)s)\""

        self.outfiles = [args[i] for i in output_positions]
        newargs = []
        for arg in args:
            newargs.append(str(arg))
        Command.__init__(self, comment, path=path, module=module, func=funcname,
                arg=','.join(["'"+arg+"'" for arg in newargs]))

