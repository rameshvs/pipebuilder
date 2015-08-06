import os
import warnings

from .core import Command
from . import util
from .util import config

# image type / file extension: only .nii.gz is currently supported!!
ANTS_EXTENSION = '.nii.gz'

ANTSPATH = config.get('Binaries', 'ANTSPATH')
ANTSPATH = config.get('Binaries', 'DEMONSPATH')
DEMONSPATH = config.get('Binaries', 'DEMONSPATH')

class DemonsCommand(Command):
    descr = "Demons registration"
    def __init__(self, comment, **kwargs):
        """
        Creates an ITK demons registration command.

        Parameters:
        -----------
        comment : string
            a short string describing what your command does

        Keyword arguments:
        ------------------
        fixed : filename
            The fixed/target image for registration

        moving : filename
            The moving image for registration

        output_prefix : string, specify either this OR output_folder
            prefix

        output_folder : string, specify either this OR output_prefix
            folder to store output with default naming.  Default naming uses
            <moving>_TO_<parameters>_<fixed>, and stores registration outputs
            in the provided folder.

        input_affine : filename, optional
            input affine transform to start from

        iterations : string
            string such as '20x15x10x5' specifying how many iterations to
            perform at each scale

        sigma : number
            smoothing kernel size
        """
        warped_suffix = '_warped.nii.gz'
        velocity_suffix = '_vel_field.nii.gz'
        self.cmd = DEMONSPATH + 'LogDomainDemonsRegistration -m %(moving)s -f %(fixed)s' + \
                ' -s %(sigma)f -d 0 ' + \
                ' -i %(iterations)s' + \
                ' -o %(output)s' + warped_suffix  + \
                ' --outputVel-field %(output)s' + velocity_suffix

        if 'input_affine' in kwargs:
            self.cmd += ' -p %(input_affine)'

        if 'output_folder' in kwargs:
            outpath = kwargs.pop('output_folder')

            self.transform_infix = 'DEMONS_' + repr(kwargs['sigma'])
            a = '{moving}_TO_{descr}_{fixed}'.format(
                    moving=util.get_filebase(kwargs['moving']),
                    fixed=util.get_filebase(kwargs['fixed']),
                    descr=self.transform_infix)
            self.output_prefix = os.path.join(outpath, a)

        elif 'output_prefix' in kwargs:
            self.output_prefix = kwargs.pop('output_prefix')
        else:
            raise ValueError("must specify either output_folder or output_folder for demons")

        kwargs['output'] = self.output_prefix
        Command.__init__(self, comment, **kwargs)

        self.warped = self.output_prefix + warped_suffix
        self.velocity_field = self.output_prefix + velocity_suffix
        self.outfiles = [self.warped, self.velocity_field]

class DemonsWarpCommand(Command):
    """
    Command representing a demons warp. Unlike most other commands, the most
    convenient way to make these is using the class methods
    make_from_registration and make_from_registration_sequence.
    """
    descr = "demons warp"

    # Maps (moving, reference) filename pairs to warped image filenames.
    # Warning: not reliable for pairs which have multiple warp paths!
    warp_mapping = {}
    @classmethod
    def make_from_registration(cls, comment, moving, reference,
            registration, output_folder, inversion='forward', **kwargs):
        """
        Creates a warp command from a single registration. See
        `make_from_registration_sequence' for more details.

        moving and reference are filenames; registration is an ANTSCommand
        object, and inversion is a string ('forward' or 'inverse', default
        'forward') describing which way to warp.
        """
        base_folder = output_folder

        output_file = '{moving}_IN_{descr}_{reference}-.nii.gz'.format(
                moving=util.get_filebase(moving),
                descr=registration.transform_infix,
                reference=util.get_filebase(reference))
        return cls(comment,
                moving=moving,
                reference=reference,
                output=os.path.join(base_folder, output_file),
                velfield=registration.velocity_field,
                inversion=inversion,
                **kwargs)

    def __init__(self, comment, **kwargs):
        """
        Creates a demons warp
        """

        if 'inversion' in kwargs:
            inversion = kwargs.pop('inversion')
        else:
            inversion = 'forward'

        if inversion == 'forward':
            kwargs['invert'] = 0
        elif inversion == 'inverse':
            kwargs['invert'] = 1
        else:
            raise ValueError("Can't invert")

        if 'useNN' in kwargs:
            useNN = kwargs.pop('useNN')
            interpolation = 1 if useNN else 2

        else:
            interpolation = 2

        kwargs['interpolation'] = interpolation
        self.cmd = DEMONSPATH + 'ApplyVelocityField %(moving)s %(output)s %(velfield)s %(invert)d %(interpolation)d'

        Command.__init__(self, comment, **kwargs)

class ANTSCommand(Command):
    descr = "ANTS registration"
    def __init__(self, comment, **kwargs):
        """
        Creates an ANTS registration command.

        Parameters:
        -----------
        comment : string
            a short string describing what your command does

        Keyword arguments:
        ------------------
        fixed : filename
            The fixed/target image for registration

        moving : filename
            The moving image for registration

        metric : string ('CC' or 'MI')
            An ANTS similarity metric. Tested/supported options are
            'CC' (corr. coeff.) and 'MI' (mutual information).
            Other ANTS metrics might work but are untested.

        mask : filename
            a mask (binary volume file) over which to compute the metric for
            registration

        method : string ('affine' or 'rigid' or 'nonlinear')

        regularization : string, optional (only req. if method is 'nonlinear')
            An ANTS regularization type. The tested/supported
            option is 'Gauss[__,__]'

        transformation : string, optional
            An ANTS transformation model. Defaults to 'Syn[0.25]'.

        nonlinear_iterations : string, optional (only req. if method is 'nonlinear')
            number of iterations (e.g. '20x20x20')

        affine_iterations : string, optional (defaults to 10000x10000x10000x10000x10000)
            number of affine iterations (e.g. '20x20x20')

        cont : filename, optional
            the name of an affine registration file to initialize and continue
            from

        init : filename, optional
            the name of an affine registration file to initialize from (does
            NOT perform further affine steps)

        radiusBins : integer
            the correlation radius (for CC) or # of bins (for MI)

        output_folder : string, specify either this OR output_prefix
            folder to store output with default naming.  Default naming uses
            <moving>_TO_<parameters>_<fixed>, and stores registration outputs
            in the provided folder.

        output_prefix : string, specify either this OR output_folder
            exact prefix for output files (as with ANTS's -o option)

        other : string
            a string with extra flags for ANTS that aren't listed/handled above.

        """
        kwargs.setdefault('dimension', 3)
        kwargs.setdefault('transformation', 'Syn[0.25]')
        kwargs.setdefault('affine_iterations', '10000x10000x10000x10000x10000')
        self.cmd = ANTSPATH + \
            '/ANTS %(dimension)s ' + \
            '-m %(metric)s[%(fixed)s,%(moving)s,1,%(radiusBins)d] ' + \
            '-t %(transformation)s ' + \
            '-o %(output)s ' + \
            '--number-of-affine-iterations %(affine_iterations)s'
        outfiles = ['Affine.txt']
        if 'nonlinear_iterations' in kwargs:
            if 'method' in kwargs:
                assert kwargs['method'] == 'nonlinear'
            else:
                kwargs['method'] = 'nonlinear'
        if 'method' in kwargs:
            # Allow old deprecated method of specifying #nonlinear iterations
            # as 'method'
            if 'x' in kwargs['method']:
                assert 'nonlinear_iterations' not in kwargs
                kwargs['nonlinear_iterations'] = kwargs['method']
                kwargs['method'] = 'nonlinear'
                warnings.warn('using # iterations in method is deprecated',
                        DeprecationWarning)
            if kwargs['method'] in ['affine', 'rigid']:
                self.cmd += ' -i 0'
                if kwargs['method'] == 'rigid':
                    self.cmd += ' --rigid-affine true'
                    self.method_name = 'RIGID'
                else:
                    self.method_name = 'AFFINE'
            elif kwargs['method'] == 'nonlinear':
                assert 'nonlinear_iterations' in kwargs
                outfiles += ['InverseWarp' + ANTS_EXTENSION, 'Warp' + ANTS_EXTENSION]
                self.cmd += ' -i %(nonlinear_iterations)s -r %(regularization)s '
                # Convert to a form that's appropriate for string naming:
                # "Gauss[4.5,0] becomes "GAUSS_45_0"
                sanitized_regularization = kwargs['regularization'].replace('[','_')\
                    .replace(']','_').replace(',','_').replace('.','').upper()
                self.method_name = 'NONLINEAR_{}_{}'.format(sanitized_regularization, kwargs['nonlinear_iterations'])
        else:
            raise ValueError("You need to specify a method! (affine, rigid, or nonlinear)")
        if 'mask' in kwargs and kwargs['mask']:
            self.cmd += ' -x %(mask)s'
            mask_string = 'MASKED_' + os.path.basename(kwargs['mask']) + '_'
            #mask_string = 'MASKED'
        else:
            mask_string = ''

        if 'cont' in kwargs:
            self.cmd += ' --initial-affine %(cont)s --continue-affine 1'
        if 'init' in kwargs:
            self.cmd += ' --initial-affine %(init)s --continue-affine 0'
        assert not ('cont' in kwargs and 'init' in kwargs), "Should only specify one of init/cont for affine"
        if 'other' in kwargs:
            self.cmd += '%(other)s'

        if 'radiusBins' not in kwargs:
            if kwargs['metric'] == 'CC':
                kwargs['radiusBins'] = 5
            elif kwargs['metric'] == 'MI':
                kwargs['radiusBins'] = 32

        # Set up output name, etc
        if 'output_folder' in kwargs:
            base_folder = kwargs.pop('output_folder')
            outpath = os.path.join(base_folder)

            self.transform_infix = '%s_%s%d_%s' % \
                    (self.method_name, kwargs['metric'], kwargs['radiusBins'], mask_string)

            # file prefix for ANTS: contains all information about the reg
            a = '{moving}_TO_{descr}_{fixed}'.format(
                    moving=util.get_filebase(kwargs['moving']),
                    fixed=util.get_filebase(kwargs['fixed']),
                    descr=self.transform_infix)

            self.output_prefix = os.path.join(outpath, a)
        elif 'output_prefix' in kwargs:
            self.output_prefix = kwargs.pop('output_prefix')
        else:
            raise ValueError("ANTSCommand must have output_prefix or output_folder")
        kwargs['output'] = self.output_prefix
        Command.__init__(self, comment, **kwargs)

        # outfiles could be EITHER aff+warp+invwarp or aff
        self.outfiles = [self.output_prefix + name for name in outfiles]

        self.method = kwargs['method']
        # Figure out the strings for warping using this registration's output
        if len(outfiles) == 1:
            assert kwargs['method'] in ('affine', 'rigid')
            (self.affine,) = self.outfiles
            self.forward_warp_string = ' {0} '.format(self.affine)
            self.backward_warp_string = ' -i {0} '.format(self.affine)
        elif len(outfiles) == 3:
            assert kwargs['method'] not in ('affine', 'rigid')
            # Nonlinear registration: we have Warp, InverseWarp, and Affine
            (self.affine, self.inverse_warp, self.warp) = self.outfiles
            self.forward_warp_string = ' {0} {1} '.format(self.warp, self.affine)
            self.backward_warp_string = ' -i {0} {1} '.format(self.affine, self.inverse_warp)
            self.forward_nonlinear_warp_string = ' {} '.format(self.warp)
            self.backward_nonlinear_warp_string = ' {} '.format(self.inverse_warp)
        else:
            raise ValueError("I expected 1 or 3 outputs from ANTS, not %d" % len(outfiles))

def get_warped_filename(moving, reference, reg_sequence, inversion_sequence, output_folder,
        ignore_affine_sequence=None, affine_only_sequence=None):
    """
    Utility function for combining ANTS registrations. See
    `ANTSWarpCommand.make_from_registration_sequence' for more details.
    """
    if ignore_affine_sequence is None:
        ignore_affine_sequence = [False] * len(inversion_sequence)
    if affine_only_sequence is None:
        affine_only_sequence = [False] * len(inversion_sequence)

    ## Combine registrations
    transform_infix = ''
    command_sequence = ''
    # construct warps in the format that ANTS wants them
    for (ants, invert, ignore_affine, affine_only) in zip(reg_sequence, inversion_sequence, ignore_affine_sequence, affine_only_sequence):
        assert not (ignore_affine and affine_only)
        # TODO come up with a better way to name files
        #transform_infix += ants.transform_infix
        transform_infix += os.path.basename(ants.output_prefix) + '-'

        if ignore_affine:
            assert ants.method not in ('affine', 'rigid')
            if invert == 'inverse':
                warp_string = ants.backward_nonlinear_warp_string
            elif invert == 'forward':
                warp_string = ants.forward_nonlinear_warp_string
            else:
                raise ValueError
        elif affine_only:
            if invert == 'inverse':
                warp_string =' -i ' + ants.affine + ' '
            elif invert == 'forward':
                warp_string = ' ' + ants.affine + ' '
            else:
                raise ValueError
        else:
            if invert == 'inverse':
                warp_string = ants.backward_warp_string
            elif invert == 'forward':
                warp_string = ants.forward_warp_string
            else:
                raise ValueError
        command_sequence = warp_string + command_sequence
    base_folder = output_folder
    if moving is None:
        output_file = transform_infix + 'Warp.nii.gz'
    else:
        output_file = '{moving}_IN---_{descr}---_{reference}-.nii.gz'.format(
                moving=util.get_filebase(moving),
                descr=transform_infix,
                reference=util.get_filebase(reference))
    output_path = os.path.join(base_folder, output_file)
    return (output_path, command_sequence)

class ANTSComposeTransformCommand(Command):
    """
    Command representing Ants's ComposeMultiTransform"""

    @classmethod
    def make_from_registration_sequence(cls, comment, reference,
            reg_sequence, inversion_sequence, ignore_affine, **kwargs):
        had_output_name = False
        if 'output_folder' not in kwargs and 'output' not in kwargs:
            print("** Warning: you should specify output folder! For now I'll guess it's the parent of the registration output...")
            output_folder = os.path.dirname(os.path.dirname(reg_sequence[0].output_prefix))
        elif 'output_folder' in kwargs:
            output_folder = kwargs.pop('output_folder')
        elif 'output' in kwargs:
            had_output_name = True
            actual_output_path = kwargs.pop('output')
            output_folder = '/'
        (output_path, cmd_sequence) = get_warped_filename(
                None, reference, reg_sequence, inversion_sequence, output_folder,
                ignore_affine_sequence=ignore_affine)
        if had_output_name:
            output_path = actual_output_path

        return cls(comment, reference=reference,
                output=output_path, transforms=cmd_sequence,
                **kwargs)

    def __init__(self, comment, **kwargs):
        """
        Creates a composite warp from multiple input wars. For a more convenient
        interface, see make_from_registration_sequence.

        Parameters:
        -----------
        comment : a short string describing what your command does

        Keyword arguments:
        ------------------
        output, reference (image filenames)
        transforms : string of transforms with spaces just as you would pass
                     to ComposeMultiTransform (or WarpImageMultiTransform)
        """
        if 'dimension' not in kwargs:
            kwargs['dimension'] = 3
        self.cmd = ANTSPATH + '/ComposeMultiTransform %(dimension)d %(output)s -R %(reference)s'
        # add "|| true" at the end because ComposeMultiTransform returns bogus exit statuses
        # see sourceforge.net/p/advants/discussion/840261/thread/73175076/
        self.cmd += ' ' + kwargs['transforms'] + ' || true'

        Command.__init__(self, comment, **kwargs)

class ANTSWarpCommand(Command):
    """
    Command representing an ANTS warp. Unlike most other commands, the most
    convenient way to make these is using the class methods
    make_from_registration and make_from_registration_sequence.
    """
    descr = "ANTS warp"

    # Maps (moving, reference) filename pairs to warped image filenames.
    # Warning: not reliable for pairs which have multiple warp paths!
    warp_mapping = {}
    @classmethod
    def make_from_registration(cls, comment, moving, reference,
            registration, inversion='forward', **kwargs):
        """
        Creates a warp command from a single registration. See
        `make_from_registration_sequence' for more details.

        moving and reference are filenames; registration is an ANTSCommand
        object, and inversion is a string ('forward' or 'inverse', default
        'forward') describing which way to warp.
        """
        return cls.make_from_registration_sequence(comment, moving, reference,
                [registration], [inversion], **kwargs)

    @classmethod
    def make_from_registration_sequence(cls, comment, moving, reference,
            reg_sequence, inversion_sequence, affine_only_sequence=None,
            ignore_affine_sequence=None,
            **kwargs):
        """
        Creates a warp command using the *ordered* sequence of registration
        command objects provided.

        inversion_sequence is a list of strings corresponding to the
        registration command objects in reg_sequence: each one should be
        'inverse' or 'forward'

        kwargs contains extra arguments to the constructor (such as useNN)

        See make_from_registration for a simpler interface when
        multiple warps aren't needed.

        Sample usage:
        -------------
        regA = ANTSCommand("Register 1 to 2", moving=img1, fixed=img2, ...)
        regB = ANTSCommand("Register 2 to 3", moving=img2, fixed=img3, ...)

        # To warp 1 to 3 using these registrations:
        warp_1to3 = ANTSWarpCommand.make_from_registration_sequence(
                        img1, img3, [regA, regB], ['forward', 'forward'])

        # To warp 3 to 1 using these registrations
        warp_3to1 = ANTSWarpCommand.make_from_registration(
                        img3, img1, [regB, regA], ['inverse', 'inverse'])
        """
        # TODO fix hardcoding
        if 'output_folder' not in kwargs:
            print("** Warning: you should specify output folder! For now I'll guess it's the parent of the registration output...")
            output_folder = os.path.dirname(os.path.dirname(reg_sequence[0].output_prefix))
        else:
            output_folder = kwargs.pop('output_folder')
        (output_path, cmd_sequence) = get_warped_filename(
                moving, reference, reg_sequence, inversion_sequence,
                output_folder=output_folder,
                affine_only_sequence=affine_only_sequence,
                ignore_affine_sequence=ignore_affine_sequence)

        if 'output_filename' in kwargs:
            output_path = kwargs.pop('output_filename')

        return cls(comment, moving=moving, reference=reference,
                output=output_path, transforms=cmd_sequence,
                **kwargs)

    def __init__(self, comment, **kwargs):
        """
        Creates a warping command for ANTS warps. For a more convenient
        interface, see make_from_registration.

        Parameters:
        -----------
        comment : a short string describing what your command does

        Keyword arguments:
        ------------------
        moving, output, reference (image filenames)
        transforms : string of transforms with spaces just as you would pass
                     to WarpImageMultiTransform
        useNN : boolean indicating whether to use nearest-neighbor interp
        """
        if 'dimension' not in kwargs:
            kwargs['dimension'] = 3
        self.warp_mapping[(kwargs['moving'], kwargs['reference'])] = kwargs['output']
        self.cmd = ANTSPATH + '/WarpImageMultiTransform %(dimension)d %(moving)s %(output)s -R %(reference)s'
        self.cmd += ' ' + kwargs['transforms']

        if 'useNN' in kwargs and kwargs['useNN']:
            self.cmd += ' --use-NN'

        Command.__init__(self, comment, **kwargs)

class ANTSJacobianCommand(Command):
    descr = "ANTS Jacobian of warp"
    def __init__(self, comment, **kwargs):
        """
        Createas a command for ANTS's ANTSJacobian binary.
        """

        if 'out_prefix' not in kwargs:
            kwargs['out_prefix'] = kwargs['input'].rsplit('.nii.gz',1)[0]
        if 'log' in kwargs and kwargs['log']:
            kwargs['log_string'] = '1'
            out_suffix = 'logjacobian.nii.gz'
        else:
            kwargs['log_string'] = '0'
            out_suffix = 'jacobian.nii.gz'
        self.outfiles = [kwargs['out_prefix'] + out_suffix]
        self.cmd=os.path.join(ANTSPATH, 'ANTSJacobian') + \
                ' 3 %(input)s %(out_prefix)s %(log_string)s -'
        Command.__init__(self, comment, **kwargs)

class N4Command(Command):
    descr = "N4 bias field corr."
    def __init__(self, comment, **kwargs):
        """
        Creates a command for N4 bias field correction. Assumes 3D images.

        Parametere:
        -----------
        comment : a short string describing what your command does

        Keyword arguments:
        ------------------
        input, output: image filenames
        """
        self.cmd = os.path.join(ANTSPATH, 'N4BiasFieldCorrection') + \
                ' --image-dimension 3 --input-image %(input)s --output %(output)s'
        Command.__init__(self, comment, **kwargs)

