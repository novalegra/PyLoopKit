# PyLoopKit
A set of Python tools for building closed-loop insulin delivery apps (Python port of LoopKit)

<a href="/example_files/example_prediction_figure.png"><img src="/example_files/example_prediction_figure.png?raw=true" alt="Sample Prediction Figure from PyLoopKit"></a>

[Link to Tidepool Loop repository version used for algorithm](https://github.com/tidepool-org/Loop/tree/8c1dfdba38fbf6588b07cee995a8b28fcf80ef69)

[Link of Tidepool LoopKit repository version used for algorithm](https://github.com/tidepool-org/LoopKit/tree/57a9f2ba65ae3765ef7baafe66b883e654e08391)

# To use this project
## Please review [the documentation](docs/pyloopkit_documentation.md) for usage instructions, input data requirements, and other important details.

### To recreate the Virtual Environment
1. This environment was developed with Anaconda. You'll need to install [Miniconda](https://conda.io/miniconda.html) or [Anaconda](https://anaconda-installer.readthedocs.io/en/latest/) for your platform.
2. In a terminal, navigate to the directory where the environment.yml 
is located (likely the PyLoopKit folder).
3. Run `conda env create`; this will download all of the package dependencies
and install them in a virtual environment named py-loop. PLEASE NOTE: this
may take up to 30 minutes to complete.

### To use the Virtual Environment
In Bash run `source activate py-loop`, or in the Anaconda Prompt
run `conda activate py-loop` to start the environment.

Run `deactivate` to stop the environment.
