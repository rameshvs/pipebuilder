from __future__ import division
from __future__ import print_function
import json
import ast
import os
import shutil
import tempfile
import mimetypes
import base64
import hashlib
import string
import collections

import cherrypy
import numpy as np

from . import registration


def get_single_line_numeric(filename):
    is_multiline = True
    try:
        with open(filename) as f:
            firstline = f.readline().strip()
            for i in xrange(2):
                try:
                    is_multiline = (f.next() != '')
                except StopIteration:
                    is_multiline = False
    except IOError:
        return None
    if not is_multiline:
        try:
            maybe_num = ast.literal_eval(firstline)
        except SyntaxError:
            return None
        if type(maybe_num) in (int, float):
            return maybe_num


def get_valid_modality_items(features_by_modality):
    valid_items = []
    for modality in features_by_modality:
        for feature in features_by_modality[modality]:
            valid_items.append({'modality': modality, 'feature': feature})
    return valid_items



class Tracker(object):
    """ Tracks dependencies between commands """

    def __init__(self, commands, datasets, subjects=None):
        """
        commands is a list of pipebuild.Command objects, and dataset is a
        list of pipebuild.Dataset
        """
        self.commands = commands
        self.datasets = datasets

        self.update_ids()


    def update_ids(self):
        """
        Updates command_classes, which maps command classes to small integers
        """
        self.command_classes = {}
        classes = set([cmd.__class__ for cmd in self.commands])
        self.command_descriptions = []
        for (i, cls) in enumerate(classes):
            self.command_classes[cls] = i
            self.command_descriptions.append(cls.descr)


    def compute_dependencies(self):
        """
        Computes a dependency graph for all commands created so far
        """
        N = len(self.commands)

        # Sparse array of filelists: list at (i, j) has all files that i
        # outputs that j depends on
        self.dependency_files = np.empty([N, N], dtype='object')

        for i in xrange(N):
            for j in xrange(N):
                self.dependency_files[i, j] = []

        for (i, early_command) in enumerate(self.commands):
            for (j, late_command) in enumerate(self.commands):
                # check if any of the early command's outputs are
                # inputs to the later command
                for outp in early_command.outfiles:
                    if outp in late_command.inputs:
                        self.dependency_files[i, j].append(outp)
                    # else:
                    #     if outp.endswith('.txt') and 'arp' in late_command.comment:
                    #         pass

        # directed (acyclic) graph representing what tasks depend on what
        self.dependency_graph = np.vectorize(len)(self.dependency_files)

    def make_command_metadata(self, command):
        out = {}
        out['version'] = 1
        out['comment'] = command.comment
        out['outfiles'] = sorted(command.outfiles)
        out['all_inputs'] = sorted(command.inputs)
        out['cmd'] = command.cmd
        out['original_inputs'] = []
        out['intermediate_inputs'] = []
        for inp in command.inputs:
            if self.test_is_original_file(inp):
                out['original_inputs'].append(inp)
            else:
                out['intermediate_inputs'].append(inp)
        return out

    def write_task_json_file(self, command, filename=None):
        """
        Writes a JSON file containing essential information about a task.
        Overwites the file.
        """
        raise NotImplementedError
        # if filename is None:
        #     filename = command.task_file
        # out = {}
        # out['version'] = 1
        # out['comment'] = command.comment
        # out['outfiles'] = sorted(command.outfiles)
        # out['all_inputs'] = sorted(command.inputs)
        # out['cmd'] = command.cmd
        # out['named_outfiles'] = {}
        # for (param_name, filename) in command.parameters.iteritems():
        #     if filename in out['outfiles']:
        #         out['named_outfiles'][param_name] = filename


        # out['original_inputs'] = []
        # out['intermediate_inputs'] = []
        # for inp in command.inputs:
        #     if self.test_is_original_file(inp):
        #         out['original_inputs'].append(inp)
        #     else:
        #         out['intermediate_inputs'].append(inp)


        # # hash the command line: since it's constructed in the same order
        # # programatically, we don't have to worry about changing the order
        # # of command line arguments.
        # # this will eventually be used to detect if outputs need to be recomputed.

        # with open(filename, 'w') as f:
        #     f.write(json.dumps(out))

    def write_pipeline_to_json(self, filename, metadata_path=''):
        """
        Writes a graph of this pipeline (nodes, links) to a JSON file
        """
        # TODO compress nodes based on input-output relationships:
        # nodes with the same inputs and the same outputs can be compressed!
        self.compute_dependencies()
        stages = self.compute_stages_bottomup()
        collapsed = self.collapse_by_stage(stages)

        N = len(self.commands)

        reverse_mapping = {} # maps node number to which supernode it's in
        # Set up supernodes (nodes grouped by almost-sameness)
        supernodes = []
        supernode_counter = 0
        for (i, stage) in enumerate(collapsed):
            for (j, subnodes) in enumerate(sorted(stage)):
                supr = {'stage': i,
                        'height': j,
                        'index': supernode_counter,
                        'class': self.command_classes[self.commands[subnodes[0]].__class__],
                        'id': 'supernode' + str(supernode_counter),
                        'subnodes': subnodes}
                supernodes.append(supr)
                for subnode in subnodes:
                    assert subnode not in reverse_mapping
                    reverse_mapping[subnode] = supernode_counter
                supernode_counter += 1

        # Set up individual nodes
        nodes = []
        klass_list = set()
        for command in self.commands:
            cmd_name = command.__class__.__name__
            klass_list.add(cmd_name)
        klass_list = list(klass_list)

        for (k, command) in enumerate(self.commands):
            outfiles = command.outfiles[:]
            named_outfiles = {}
            for (param_name, outfilename) in command.parameters.iteritems():
                if outfilename in outfiles:
                    named_outfiles[param_name] = outfilename
                    outfiles.remove(outfilename)
            klass = command.__class__.__name__
            cmdline_hash = base64.urlsafe_b64encode(hashlib.md5(command.cmd).digest())
            metadata_prefix = os.path.join(metadata_path, cmdline_hash)
            nodes.append({'name': command.comment,
                          'class': self.command_classes[command.__class__],
                          'id': 'subnode' + str(k),
                          'klass': klass_list.index(klass),
                          'command_line': command.cmd,
                          'metadata_prefix': metadata_prefix,
                          'index': k,
                          'outputs': command.outfiles,
                          'named_outfiles': named_outfiles,
                          'task_info': self.make_command_metadata(command),
                          'supernode': reverse_mapping[k]})

        edges = collections.Counter()
        for i in xrange(N):
            for j in xrange(i+1, N):
                weight = int(self.dependency_graph[i, j])
                edges[(reverse_mapping[i], reverse_mapping[j])] += weight
        links = []
        for ((supersource, supertarget), weight) in edges.iteritems():
            if weight > 0:
                links.append({
                    'weight': weight,
                    'supersource': supersource,
                    'supertarget': supertarget})

        klass_list = [k[:-len('Command')] for k in klass_list]

        s = json.dumps({'supernodes': supernodes, 'klasses': klass_list,
            'subnodes': nodes, 'links': links, 'reverse_mapping': reverse_mapping})
        with open(filename, 'w') as f:
            f.write(s)

    def gather_multi_subject_jsons(self, subject_list, this_subject,
            out_location=None):
        self.all_jsons = {}
        assert this_subject in subject_list
        for dataset in self.datasets:
            try:
                log_folder = dataset.get_log_folder(subj=this_subject)
                this_json_list = os.path.join(log_folder, 'pb_json_list.txt')
                read_last_line(this_json_list)
            except Exception:
                continue
        #assert this_subj_json is not None
        for subject in subject_list:
            json_list = this_json_list.replace(this_subject, subject)
            try:
                subj_json = read_last_line(json_list)
            except IOError:
                continue
            print(subj_json)
            with open(subj_json) as f:
                self.all_jsons[subject] = json.load(f)

        if out_location is not None:
            assert out_location.endswith('.json')
            with open(out_location, 'w') as f:
                json.dump(self.all_jsons, f)

    def compute_stages_bottomup(self):
        all_stages = []
        this_stage_nodes = []
        completed_nodes = set()

        # Find all nodes without children to initialize
        for (i, cmd) in enumerate(self.commands):
            if np.sum(self.dependency_graph[i,:]) == 0:
                this_stage_nodes.append(i)

        while True:
            prev_stage_nodes = []
            for node in this_stage_nodes:
                completed_nodes.add(node)
                parents = np.where(self.dependency_graph[:,node])[0]
                for parent in parents:
                    if parent not in completed_nodes:
                        # make sure all its parents have been accounted for
                        # before adding it
                        children = np.where(self.dependency_graph[parent,:])[0]
                        if set(children).issubset(completed_nodes):
                            prev_stage_nodes.append(int(parent))
            all_stages.append(this_stage_nodes)
            if prev_stage_nodes == []:
                break
            this_stage_nodes = prev_stage_nodes
        all_stages.reverse()
        return all_stages

    def make_nipype_pipeline_multimodal(self, features_by_modality):
        valid_inputs = get_valid_modality_items(features_by_modality)
        return self.make_nipype_pipeline(valid_inputs)


    def make_nipype_pipeline(self, base_dir):
        from nipype import config
        config.enable_provenance()
        import nipype.pipeline.engine as pe
        import re
        self.compute_dependencies()
        nodes = []
        pipeline = pe.Workflow('converted_to_nipype', base_dir)
        i=0
        for command in self.commands:
            (interface, input_map, output_map) = make_nipype_function_interface(command)
            comment = re.sub(r'\W','_', command.comment)
            #comment = command.comment.replace(' ','_')
            nodes.append((pe.Node(interface=interface, name=comment),
                          input_map, output_map))
            i+=1
        (input_nodes, mapping) = self.make_selectfiles(nodes)
        for i in xrange(len(self.commands)):
            (parent_node, parent_inputs, parent_outputs) = nodes[i]
            for (input_file, input_name) in parent_inputs.items():
                if input_file in mapping:
                    (fields, j) = mapping[input_file]
                    input_source = input_nodes[j]
                    nipype_input_name = make_nipype_name(fields)
                    pipeline.connect([(input_source, parent_node, [(nipype_input_name, input_name)])])
            for j in xrange(i, len(self.commands)):

                (child_node, child_inputs, _) = nodes[j]

                files = self.dependency_files[i,j]
                for file in files:
                    assert file in parent_outputs
                    assert file in child_inputs
                    pipeline.connect([(parent_node, child_node, [(parent_outputs[file], child_inputs[file])])])
        return pipeline


    def make_selectfiles(self, nodes):
        import nipype
        import nipype.pipeline.engine as pe
        valid_inputs_for_datasets = [[] for d in self.datasets]
        mapping = {}
        # Deduce valid inputs from the pipeline: list all things that were used
        for (i, (node, inputs, outputs)) in enumerate(nodes):
            for inp in inputs:
                found = False
                for (j, dataset) in enumerate(self.datasets):
                    fields = dataset.get_fields(inp)
                    if fields is not None:
                        assert not found
                        valid_inputs_for_datasets[j].append(fields)
                        mapping[inp] = (fields, j)
                        found = True
                    else:
                        continue

        input_nodes = []
        for (j, (dataset, valid_items)) in enumerate(zip(self.datasets, valid_inputs_for_datasets)):
            selectfiles_dict = dataset_to_selectfiles(dataset, valid_items)
            input_source = pe.Node(nipype.SelectFiles(selectfiles_dict), 'in_%d' % j)
            input_nodes.append(input_source)
        print(input_nodes)
        return (input_nodes, mapping)

    def compute_stages(self):
        """
        Breaks commands down into `stages' for visualization. Each stage only
        depends on events from previous stages.
        """
        all_stages = []
        this_stage_nodes = []
        next_stage_nodes = []

        # find all nodes without parents to start us off
        completed_nodes = set()
        for (i, cmd) in enumerate(self.commands):
            if np.sum(self.dependency_graph[:,i]) == 0:
                this_stage_nodes.append(i)

        # continue through each stage
        while True:
            next_stage_nodes = []
            for node in this_stage_nodes:
                completed_nodes.add(node)
                children = np.where(self.dependency_graph[node,:])[0]
                for child in children:
                    if child not in completed_nodes:
                        # make sure all its parents have been accounted for
                        # before adding it
                        parents = np.where(self.dependency_graph[:, child])[0]
                        if set(parents).issubset(completed_nodes):
                            next_stage_nodes.append(int(child))
            all_stages.append(this_stage_nodes)
            if next_stage_nodes == []:
                break
            this_stage_nodes = next_stage_nodes
        return all_stages

    def test_is_original_file(self, filename):
        for dataset in self.datasets:
            if dataset.is_original_file(filename):
                return True
        return False
    def collapse_by_stage(self, stages):
        """
        Returns a grouping by stage of nodes that are similar.

        Two nodes are defined to be 'similar' if their only differing inputs are
        original (i.e. non-pipeline-generated) files, AND they are the same type

        Returns a list similar to input, but with one further layer of nesting
        """
        # TODO also group by non-file stuff (e.g. nodes with the same inputs
        # but different parameters)
        out_stages = []
        for stage in stages:
            out_stage = []
            groups = collections.defaultdict(lambda : [])
            for idx in stage:
                command = self.commands[idx]
                inputs = []
                for inp in command.inputs:
                    if self.test_is_original_file(inp):
                        continue
                    elif command.__class__ == registration.ANTSWarpCommand and \
                            command.parameters['moving'] == inp:
                        # Special case: group warps
                        continue
                    else:
                        inputs.append(inp)
                key = (self.command_classes[command.__class__], frozenset(inputs))

                groups[key].append(idx)
            for (key, val) in groups.iteritems():
                # if the "shared inputs" are actually empty, then don't group the nodes
                if len(key[1]) == 0:
                    out_stage.extend([[idx] for idx in val])
                else:
                    out_stage.append(val)
            out_stages.append(out_stage)
        return out_stages

def read_last_line(filename):
    """
    (Naively) reads the whole file in and returns the last line.
    """
    # TODO make this smarter
    with open(filename) as f:
        line = f.read().rsplit('\n', 2)[-2]
    return line

class SubjServer(object):

    def __init__(self, dataset, subject_list, content_path, aggregate_json=None):
        self.dataset = dataset
        self.content_path = content_path
        self.activeJSON = None
        self.subject_list = subject_list
        self.precomputed_output_info = None
        self.aggregate_json = aggregate_json
        if aggregate_json is not None:
            self.good_subjects = sorted(aggregate_json.keys())

            assert set(self.good_subjects).issubset(self.subject_list)
            self.combine_output_info()

    @cherrypy.expose
    def getOutputInfo(self, index):
        index = int(index)
        cherrypy.response.headers['Content-Type'] = 'application/json'
        if (self.is_aggregate):
            json_dict = {'aggregate': True, 'data': self.aggregated_output_spec[index]}
        else:
            json_dict = self._computeOutputInfo(index, self.activeJSON)
        return json.dumps(json_dict)

    def _computeOutputInfo(self, index, json_dict):
        node = json_dict['subnodes'][index]
        if 'metadata_prefix' in node:
            metadata_prefix = node['metadata_prefix']
            # TODO FIXME for some reason they weren't saved properly so do it here
            # digest = base64.urlsafe_b64encode(hashlib.md5(node['command_line']).digest())
            node_path = metadata_prefix
            # only works because the filenames have timestamps
            try:
                files = sorted(os.listdir(node_path))
                if len(files) == 0:
                    print("Warning: no output found for '" + node['name'] + "'")
                    json_file = None
                else:
                    json_file = os.path.join(node_path, [f for f in files if f.endswith('.json')][-1])
            except OSError:
                json_file = None
        else:
            json_file = None
        for extra in ['stdout', 'stderr']:
            if extra not in node:
                    try:
                        with open(json_file) as f:
                            node[extra] = json.load(f)[extra]
                    # TODO ioerror and json load error only, no key error
                    except:
                        node[extra] = ''
        out = [
                {'name': 'Command line', 'value': node['task_info']['cmd'], 'type': 'string'},
                {'name': 'stdout', 'value': node['stdout'], 'type': 'string'},
                {'name': 'stderr', 'value': node['stderr'], 'type': 'string'},
                ]

        for (param_name, filename) in node['named_outfiles'].items():
            current = {'name': param_name, 'value': filename, 'type': 'file'}
            (mtype, encoding) = mimetypes.guess_type(filename)
            # TODO add more med imaging formats here
            if filename.endswith('.nii.gz'):
                mtype = 'application/x-nifti'
            current['mimetype'] = mtype
            current['mimeencoding'] = encoding

            if filename.endswith('.txt'):
                maybe_num = get_single_line_numeric(filename)
                if maybe_num is not None:
                    current['numeric'] = maybe_num
            out.append(current)

        return out

    def precompute_output_info(self):
        self.precomputed_output_info = {}
        for subj in self.good_subjects:
            json = self.aggregate_json[subj]
            indices = len(json['subnodes'])
            outputs = []
            for index in xrange(indices):
                outputs.append(self._computeOutputInfo(index, json))
            self.precomputed_output_info[subj] = outputs

    def combine_output_info(self):
        if self.precomputed_output_info is None:
            self.precompute_output_info()

        outs = zip(*(self.precomputed_output_info[subj] for subj in self.good_subjects))
        self.aggregated_output_spec = []
        for (i, subj_nodes) in enumerate(outs):
            aggregate_node = []
            self.aggregated_output_spec.append(aggregate_node)
            max_count = max((len(subj_node) for subj_node in subj_nodes))
            for j in xrange(max_count):
                keys = set()
                for subj_node in subj_nodes:
                    keys.update(subj_node[j].keys())
                out_val = {}
                completion_fraction = None
                for key in keys:
                    all_values = []
                    for (subj, subj_node) in zip(self.good_subjects, subj_nodes):
                        if key in subj_node[j]:
                            all_values.append((subj, subj_node[j][key]))
                    (subjects, values) = zip(*all_values)
                    # TODO make out_val[key] a rich structure that stores #subjects, etc
                    first = values[0]
                    if values.count(first) == len(values):
                        out_val[key] = first

                    else:

                        completion_fraction = len(subjects)/len(self.good_subjects)
                        out_dict = {'aggregate': True, 'value': values, 'subjects': subjects}
                        # if type(first) in (float, int):
                        #     out_dict['type'] = 'number'
                        # elif type(first) is str and os.path.exists(first):
                        #     out_dict['type'] = 'filename'
                        # elif type(first) is str:
                        #     out_dict['type'] = 'string'
                        out_val[key] = out_dict

                if completion_fraction is not None:
                    out_val['completion_fraction'] = completion_fraction

                if 'numeric' in out_val:
                    #numbers = np.array(out_val['numeric']['value'])
                    numbers = np.log10(np.array(out_val['numeric']['value']))
                    n_bins = int(round(numbers.size / 10))
                    if n_bins < 10:
                        n_bins = 10
                    (counts, bins) = np.histogram(numbers, bins=n_bins)
                    out_val['histogram'] = [{'x': "%0.2f" % x, 'y': y} for (x,y) in zip(bins, counts)]
                    # Compute outliers
                    (q1, median, q3) = np.percentile(numbers, [25, 50, 75])
                    iqr = q3 - q1
                    lower = median - 1.5*iqr
                    upper = median + 1.5*iqr
                    (low_indices,) = np.where(numbers < lower)
                    (hi_indices,) = np.where(numbers > upper)
                    low_subjs = [subjects[i] for i in low_indices]
                    hi_subjs = [subjects[i] for i in hi_indices]
                    out_val['outliersubj'] = {'low': low_subjs, 'high': hi_subjs}

                aggregate_node.append(out_val)

    # @cherrypy.expose
    # def index(self, **kwargs):
    #     head = '<html><head><link type="text/css" rel="stylesheet" href="viz/style.css?v=<?=time();?>"><title>Subject List</title></head>'

    #     body = '<body><h1>Subjects (click to see pipeline visualization)</h1><ul>'
    #     if self.aggregate_json is not None:
    #         body += '<li><a href="viewer?subj=aggregate">Overview</a></li>'
    #     for subj in self.subject_list:
    #         body += '<li><a href="viewer?subj={subj}">{subj}</a></li>'.format(subj=subj)
    #     body += '</ul></body>'
    #     return head + body

    @cherrypy.expose
    def index(self):
        self.active_subj = 'aggregate'
        self.is_aggregate = True
        # self.is_aggregate = (subj == 'aggregate')
        # self.active_subj = subj
        raise cherrypy.HTTPRedirect("static/index.html")


    @cherrypy.expose
    def changeSubject(self, subj):
        self.is_aggregate = (subj == 'aggregate')
        self.active_subj = subj
        raise cherrypy.HTTPRedirect("static/index.html")

    @cherrypy.expose
    def test(self, subj):
        with open(os.path.join(self.content_path, 'viz', 'index.html')) as f:
            out = f.readlines()
        return out


    #@cherrypy.expose
    #def getActiveSubjJSON(self):
    @cherrypy.expose
    def getGraphJSON(self):
        # TODO intelligently go through the JSONs to find all the actions performed
        if self.is_aggregate:
            active_subj = self.subject_list[0]
        else:
            active_subj = self.active_subj
        json_list_file = os.path.join(self.dataset.get_log_folder(subj=active_subj),
                     'pb_json_list.txt')
        json_fname = read_last_line(json_list_file)
        with open(json_fname) as f:
            self.activeJSON = json.load(f)
        cherrypy.response.headers['Content-Type'] = 'application/json'
        return json.dumps(self.activeJSON)


    @cherrypy.expose
    def getSubjects(self):
        cherrypy.response.headers['Content-Type'] = 'application/json'
        #return json.dumps([{'d': s} for s in self.good_subjects])
        return json.dumps(self.good_subjects)

    @cherrypy.expose
    def nodeStatuses(self, timeout):
        import time
        assert self.activeJSON is not None
        # TODO actually retrieve statuses here based on metadata
        # TODO sleep here
        time.sleep(int(timeout))
        statuses = []
        for node in self.activeJSON['subnodes']:
            if os.path.exists(node['outputs'][0]):
                statuses.append(1)
            else:
                statuses.append(-1)
        #statuses = [os.path.exists(node['outfiles'][0]) for node in self.activeJSON['nodes']]
        #statuses = np.random.randint(-1, 2, len(self.activeJSON['nodes']))
        cherrypy.response.headers['Content-Type'] = 'application/json'
        #return json.dumps(statuses.aslist())
        return json.dumps(statuses)

    @cherrypy.expose
    def queryFile(self, filename):
        filename = os.path.normpath(filename)
        if not filename.startswith(self.dataset.base_dir):
            print("Warning: invalid file access attempted: you asked for")
            print(filename)
            print("but I can only serve files from " + self.dataset.base_dir)
            return ''
        elif not os.path.exists(filename):
            print("Warning: file doesn't exist:")
            print(filename)
            return ''
        else:
            (mtype, encoding) = mimetypes.guess_type(filename)
        cherrypy.response.headers['Content-Type'] = 'application/json'
        return [mtype, encoding]

    @cherrypy.expose
    def retrieveFile(self, filename):
        """
        Meant for reading of arbitrary files from disk.
        """
        # TODO make this secure: currently allows reading of arbitrary
        # files once you've authenticated with the password. integrate w/dataset?
        #filename = os.path.normpath('/' + '/'.join(args))
        filename = os.path.normpath(filename)
        if not filename.startswith(self.dataset.base_dir):
            print("Warning: invalid file access attempted: you asked for")
            print(filename)
            print("but I can only serve files from " + self.dataset.base_dir)
            return ''
        elif not os.path.exists(filename):
            print("Warning: file doesn't exist:")
            print(filename)
            return ''
        else:
            # mime type enables us to read the file after loading
            (mtype, encoding) = mimetypes.guess_type(filename)
            cherrypy.response.headers["Access-Control-Allow-Origin"] = '*'
            cherrypy.response.headers["Content-Type"] = mtype
            if encoding is not None:
                cherrypy.response.headers["Content-Encoding"] = encoding
            return open(filename, 'r')

# TODO more secure password checking (salting? reading from file? etc)
def checkpasshash(realm, user, password):
    # right now it's just pipeline/pipeline: change this!
    return user == 'pipeline' and hashlib.sha1(password).hexdigest() == '992b5d666718483c9676361ebc685d122089e3eb'

def run_server(subject_list, dataset, aggregate_json=None):

    cwd = os.path.dirname(os.path.realpath(__file__))
    content_dir = tempfile.mkdtemp(prefix=dataset.base_dir + '/')

    content_dir_name = os.path.basename(content_dir)

    shutil.copytree(os.path.join(cwd, '..', 'viz'), os.path.join(content_dir, 'viz'))

    old_cwd = os.getcwd()
    os.chdir(dataset.base_dir)

    #IP = "127.0.0.1" # Local access only
    IP = "0.0.0.0"
    PORT = 56473
    global_config = {'server.socket_port': PORT,
                    'server.socket_host': IP,
                    }
    cherrypy.config.update(global_config)
    appconfig = {
            '/viewer': {
                'tools.auth_basic.on': True,
                 'tools.auth_basic.realm': 'viz',
                 'tools.auth_basic.checkpassword': checkpasshash,
            },
            #'/content': {
            '/static': {
                'tools.staticdir.on' : True,
                'tools.staticdir.dir' : os.path.join(content_dir, 'viz'),
                'tools.staticdir.debug': True,
            }
    }
    cherrypy.quickstart(SubjServer(dataset, subject_list, content_dir_name, aggregate_json), config=appconfig)

    os.chdir(old_cwd)
    shutil.rmtree(content_dir)

