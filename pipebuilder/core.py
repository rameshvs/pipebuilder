"""
This module provides a general set of tools for implementing medical imaging
pipelines.
"""
from __future__ import print_function

import os
import re
import time
import errno
import base64
import string
import hashlib
import datetime
import warnings
import subprocess

import parse

from . import util

THIS_DIR = os.path.dirname(os.path.realpath(__file__))

# Script to generate a file for submitting with SGE QSUB
QSUB_RUN =        os.path.join(THIS_DIR, '..', 'scripts', 'qsub-run')
# Requires SGE to run in batch mode
QSUB = 'qsub'

################################################################################
### Utility I/O stuff (handles all file naming conventions: adjust to taste) ###
################################################################################
class Dataset(object):
    """
    Class representing your data. Has a range of features from simple to
    elaborate; you can use as much as is useful to you.
    """
    all_datasets = [] # Static list of all dataset objects
    def __init__(self, base_dir, original_template, processing_template,
            log_template=None, default_extension='.nii.gz'):
        """
        All templates should be specified using curly-brace formatting, e.g.:
        /home/data/{subject}/{modality}{extension}

        base_dir: common root for all files (for convenience). The following
                  paths can either be absolute or relative with respect to
                  base_dir.
        original_template: template for original files (i.e., inputs to the
                           pipeline)
        processing_template: template for processing files (i.e., files that
                             are produced as intermediate values or outputs of
                             the pipeline). If this dataset won't produce any
                             intermediate files, this should be set to None.
        log_template: template for creating a log folder (where logs are
                      stored). Defaults to base_dir if not given.
        """

        f = string.Formatter()
        self.base_dir = base_dir
        self.default_extension = default_extension

        self.original_fields = util.ordered_unique(['extension'] + [name for (_, name, _, _) in f.parse(original_template)])
        if None in self.original_fields:
            raise ValueError
        self.original_template = os.path.join(base_dir, util.add_extension(original_template))

        if processing_template is None:
            self.processing_fields = self.processing_template = None
        else:
            self.processing_fields = util.ordered_unique(['extension'] + [name for (_, name, _, _) in f.parse(processing_template)])
            self.processing_template = os.path.join(base_dir, util.add_extension(processing_template))

        if log_template is None:
            self.log_template = base_dir
        else:
            self.log_template = os.path.join(base_dir, log_template)

        self.filenames_to_field_values = {}
        self.mandatory_files = set()
        self.invalid_files = set()

        # List of fields that are filled. for example,
        # if the full set of fields is ('subject', 'modality', 'feature'),
        # and you declare (modality='t1', feature='image') to be mandatory,
        # then filled_mandatory_fields is ['modality', 'feature']. This means
        # that for every possible combination of values for the remaining
        # fields, these values for the mandatory fields must be present.

        self.filled_mandatory_fields = ()
        # Add fields to doc strings: TODO this feels kind of hacky: is there a
        # better way to do this?
        if self.processing_template is None:
            field_list_string = '***NONE'
        else:
            field_list_string = ', '.join(self.processing_fields)
        self.get.__func__.__doc__ += '\nFields: ' + field_list_string
        self.get_original.__func__.__doc__ += '\nFields: ' + ', '.join(self.original_fields)

        Dataset.all_datasets.append(self)


    def loop_over_original(self, field_name, values):
        """
        """
        raise NotImplementedError
        self._loop_over(field_name, self.original_template, self.original_fields, values)
    def loop_over_processing(self, field_name, values):
        raise NotImplementedError
        self._loop_over(field_name, self.processing_template, self.processing_fields, values)

    def _loop_over(self, field_name, template, fields, value):
        raise NotImplementedError
    def get_fields(self, filename):
        """
        Given a filename *that was already produced by this dataset*,
        returns the corresponding fields that were used to produce it.

        e.g., if you called mydataset.get(foo='a', bar='b') to produce
        /path/to/a/b.txt,
        calling mydataset.get_fields('/path/to/a/b.txt') would return
        {'foo': 'a', 'bar': 'b'}. However, making the second call *without*
        having called the first would return None.
        """
        if filename in self.filenames_to_field_values:
            return self.filenames_to_field_values[filename]
        else:
            return None

    def is_original_file(self, filename):
        """
        Determines whether the filename could have been produced by the original
        template.
        """
        parsing = parse.parse(self.original_template, filename) is not None
        return parsing != None

    def get_folder(self, **partial_format):
        """
        Given a partial formatting (i.e., a dictionary with values for some of
        the template fields), tries completing the formatting to return the
        folder where the result would be.
        """
        if self.processing_template is None:
            raise ValueError("Can't call get_folder without specifying a template")
        self._fill_partial_format(partial_format, self.processing_fields)
        retval = os.path.dirname(self.processing_template.format(**partial_format))
        return retval

    def _fill_partial_format(self, partial_format, fields, value='%'):
        """
        Given a partial format (dictionary), fills in all the missing keys from
        fields using the provided value.
        """
        # TODO consider replacing it with itself (e.g. {foo} -> {foo})
        # would need to change how mandatory stuff is handled for that too
        for field in fields:
            partial_format.setdefault(field, value)
        return partial_format

    def get_log_folder(self, **partial_format):
        "Returns the log folder for a given formatting"
        return self.log_template.format(**partial_format)

    def get_original(self, **format):
        "Returns an original file using the template and the provided fields"
        format.setdefault('extension', self.default_extension)
        filename = self.original_template.format(**format)
        if not os.path.exists(filename):
            if self.is_mandatory(format):
                raise IOError("Missing mandatory file: " + filename)
            else:
                self.invalidate(filename)

        assert filename not in self.filenames_to_field_values \
                or self.filenames_to_field_values[filename] == format
        self.filenames_to_field_values[filename] = format
        return filename

    def get(self, **format):
        """
        Returns an intermediate/output file using the template and provided
        fields
        """
        if self.processing_template is None:
            raise ValueError("Can't get a file if you didn't specify a template")
        format.setdefault('extension', self.default_extension)
        filename = self.processing_template.format(**format)
        return filename

    def parse(self):
        ""
        raise NotImplementedError

    def is_mandatory(self, format):
        """
        Determines whether the file specified by the given format is
        mandatory or not
        """
        format = format.copy()
        for field in self.original_fields:
            if field not in self.filled_mandatory_fields:
                format[field] = '%'
        return self.original_template.format(**format) in self.mandatory_files

    def add_mandatory_input(self, **partial_format):
        """
        Specifies that any input matching the partial format is mandatory, and
        that the code should crash immediately if the mandatory file is not
        found.

        For example, if the fields are {subject}, {modality}, and {feature},
        then specifying a partial format of feature=img means that for every
        subject and for every modality, the feature "img" must be present or
        the system will crash at the time of pipeline creation.
        """
        if self.filled_mandatory_fields == ():
            self.filled_mandatory_fields = set(partial_format.keys())
        else:
            assert set(partial_format.keys()) == self.filled_mandatory_fields
        self._fill_partial_format(partial_format, self.original_fields)
        self.mandatory_files.add(self.original_template.format(**partial_format))

    def is_invalid(self, filename):
        """ Checks if a filename is invalid: future commands using it won't run. """
        return filename in self.invalid_files

    def invalidate(self, filename):
        """ Invalidates a filename: future commands using it won't run. """
        self.invalid_files.add(filename)

    def invalidate_command_outputs(self, command):
        """
        Invalidates all of a Command's outputs (filenames) so that future
        commands that depend on them won't run.
        """
        for out_fname in command.outfiles:
            self.invalidate(out_fname)

    def has_all_valid_inputs(self, command):
        """ Checks if any inputs to command have been invalidated """
        for inp in command.inputs:
            if has_valid_path(inp) and self.is_invalid(inp):
                return False
        return True

def to_filename(thing):
    return thing

###############################################################################
### Commands (perform tasks, sort of like interfaces in nipype but simpler) ###
###############################################################################
class Command(object):
    """
    Represents a command/task that has to be run.  When creating one, make sure
    to call Command.__init__ with comment and output!

    If your command produces any outputs not given by the output keyword
    argument, you should set outfiles within your command.
    """
    descr = ''
    all_commands = [] # Static list of all command objects

    @classmethod
    def clear(cls):
        cls.all_commands = []

    @classmethod
    def reset(cls):
        cls.all_commands = []

    @classmethod
    def generate_code_from_datasets(cls, datasets, log_folder, short_id='',
            tracker=None, clobber_existing_outputs=False, sge=False, wait_time=0):
        timestamp = datetime.datetime.now().strftime('%y%m%d-%H%M%S-%f')
        out_script = os.path.join(log_folder, 'pb_%s.%s.sh' % (short_id, timestamp))
        if tracker is not None:
            # TODO clean up multiple places where pb_metadata path is constructed
            json_filename = out_script[:-3] + '.json'
            (cmd_file_path, file_prefix) = os.path.split(out_script[:-3])
            metadata_path = os.path.join(cmd_file_path, 'pb_metadata')
            tracker.write_pipeline_to_json(json_filename, metadata_path)
            json_list = os.path.join(log_folder, 'pb_json_list.txt')
            with open(json_list, 'a') as f:
                f.write(json_filename + '\n')
            pass
        cls.generate_code(out_script, log_folder, datasets, clobber_existing_outputs)
        print(out_script)
        if sge:
            out_qsub = out_script + '.qsub'
            os.environ['SGE_LOG_PATH'] = log_folder
            os.environ['SGE_LOG_DIR'] = log_folder
            with open(out_qsub,'w') as out_qsub_file:
                subprocess.call([QSUB_RUN, '-c', out_script], stdout=out_qsub_file)

            time.sleep(wait_time) # sleep so that timestamps don't clash & SGE isn't overloaded
            print(out_qsub)
            subprocess.call([QSUB, '-q', 'main.q', out_qsub])
        return out_script


    @classmethod
    def generate_code(cls, command_file, log_folder, datasets,
                      tracker=None, clobber_existing_outputs=False,
                      json_file=None):
        """
        Writes code to perform all created commands. Commands are run in the
        order they were created; there are no dependency-based reorderings.

        command_file : a file to write the commands to
        datasets : a list of dataset objects to cross-check commands against
        tracker : a tracking.Tracker that tracks this dataset/these commands
        clobber_existing_outputs : whether or not to rerun commands whose
        outputs already exist
        """
        assert command_file.endswith('.sh'), "Command files must end with .sh for now"
        # TODO incorporate dependencies
        # if tracker is not None:
        #     task_json_prefix = command_file.rsplit('.', 1)[0]
        #     task_json_folder = task_json_prefix + '_taskfiles'
        #     os.mkdir(task_json_folder)
        with open(command_file, 'w') as f:
            f.write('#!/usr/bin/env bash\n')
            f.write('set -e\n\n')
            for command in cls.all_commands: # loop in order listed

                # if tracker is not None:
                #     import hashlib
                #     import base64
                #     filename = base64.urlsafe_b64encode(hashlib.md5(command.cmd).digest())
                #     command.task_file = os.path.join(task_json_folder, filename + '.json')
                #     tracker.write_task_json_file(command)
                # else:
                #     command.task_file = '/dev/null'
                command.task_file = '/dev/null'

                # TODO more consistent naming
                if command.skip:
                    f.write('# *** Skipping (due to user instructions) ' + command.comment + '\n'*2)

                elif clobber_existing_outputs or command.clobber or not command.check_outputs():
                    if len(datasets) > 0 and not command.has_all_valid_inputs(datasets):
                        f.write('# *** Skipping (due to missing input) ' + command.comment + '\n'*2)
                        command.invalidate_outputs(datasets)
                    else:
                        cmdline_hash = base64.urlsafe_b64encode(hashlib.md5(command.cmd).digest())
                        f.write('# ' + command.comment + '\n')
                        st = ''
                        if tracker is not None:
                            (cmd_file_path, file_prefix) = os.path.split(command_file[:-3])
                            wrap_files_path = os.path.join(cmd_file_path, 'pb_metadata', cmdline_hash)
                            try:
                                os.makedirs(wrap_files_path)
                            except OSError as exc: # Python >2.5
                                if exc.errno == errno.EEXIST and os.path.isdir(wrap_files_path):
                                    pass
                                else: raise
                            wrap_files_prefix = os.path.join(wrap_files_path, file_prefix)
                            wrap = os.path.join(THIS_DIR, '..', 'scripts', 'wrap_simple.py ')
                            st += wrap + wrap_files_prefix + ' \\\n\\\n'
                        f.write(st + command.cmd + '\n'*4)
                else:
                    f.write('# *** Skipping (due to already-present output) ' + command.comment + '\n'*2)
        os.chmod(command_file, 0775)

    def __init__(self, comment, **kwargs):
        self.clobber = 'clobber' in kwargs and kwargs['clobber']
        self.skip = 'skip' in kwargs and kwargs['skip']
        self.task_file = ''
        if not hasattr(self, 'outfiles'):
            if 'output' not in kwargs:
                self.outfiles = []
                warnings.warn("output/outfiles not specified for command; can't track output:\n"+comment,
                        RuntimeWarning)
            else:
                self.outfiles = [kwargs['output']]

        self.parameters = kwargs
        self.comment = comment

        good_kwargs = dict( ((k, to_filename(v)) for (k, v) in kwargs.iteritems()) )
        self.cmd_template = self.cmd
        self.cmd = self.cmd % good_kwargs

        self.command_id = len(Command.all_commands)
        Command.all_commands.append(self) # order is very important here


        # Tracking of input/output relationships between commands.
        inputs = []
        self.inputs = []
        # TODO smarter checking of inputs/outputs here
        for (k, v) in self.parameters.items():
            if k == 'cmdName':
                continue
            if type(v) is str:
                # split on non-escaped spaces (since escaped spaces could be
                # filenames)
                inputs.extend(re.split(r'(?<!\\)\s+', v))
            elif type(v) is list or type(v) is tuple:
                inputs.extend(v)
        for v in inputs:
            if (type(v) is str and has_valid_path(v)) or \
                    hasattr(v, 'filename'):
                self.inputs.append(v)

        self.inputs = set(map(to_filename, self.inputs)).difference(map(to_filename, self.outfiles))

    def check_outputs(self):
        """
        Checks if outputs are already there (True if they are). Warning: not
        thread-safe
        """
        new_outfiles = []
        for f in self.outfiles:
            new_outfiles.append(to_filename(f))

        return len(self.outfiles) > 0 and \
                all([os.path.exists(f) for f in new_outfiles])

    def has_all_valid_inputs(self, datasets):
        for input in self.inputs:
            if not has_valid_path(input):
                continue # it's not a file, so no need to check
            #found_invalidation = False
            for dataset in datasets:
                if dataset.is_invalid(input):
                    return False
        return True

    def invalidate_outputs(self, datasets):
        for output in self.outfiles:
            for dataset in datasets:
                # TODO fix this: find the right dataset and only invalidate once
                dataset.invalidate(output)

def has_valid_path(filename):
    #return os.path.isdir(os.path.dirname(filename))
    # what if options start with slashes?
    return os.path.isabs(filename)
