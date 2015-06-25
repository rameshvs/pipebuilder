# PipeBuilder
PipeBuilder is a tool for constructing pipelines. While the focus of PipeBuilder
is pipelines to analyze medical images, it can be used for any purpose.

This documentation is a work in progress.

## Getting started
To get started, clone the repository and add it to your PYTHONPATH:

    cd /your/path/here
    git clone https://github.com/rameshvs/pipebuilder

    export PYTHONPATH=/your/path/here/pipebuilder:$PYTHONPATH

Next, change the relevant locations in `site.cfg` to point to the appropriate
binaries.

Now you're ready to start making pipelines! For some simple example pipelines,
see the `examples` folder, or my
[stroke analysis pipeline](https://github.com/rameshvs/stroke_analysis).


