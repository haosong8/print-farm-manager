# Environment Setup

1. Make sure that Anaconda or miniConda is installed. Link here: https://www.anaconda.com/download
    - Make sure Python is installed. Link here: https://www.python.org/downloads/
        - This will also install `pip` when using custom install make sure to add Python to PATH for all Users
2. Two Options:
    - Option 1: Create a conda environment from the .yml files provided in `/environment` folder:
        - If you are running windows, use the Conda Prompt, on Mac or Linux you can just use the Terminal.
        - Use the command: `conda env create -f environment.yml`
        - This should create an environment named `bid_solver_server`. 
        - Environment may take a while to resolve
    - Option 2: Using `conda` and `pip`
        1. Create a conda environment using the command `conda create --name <bid_solver_server>`
        2. Run `pip install -r requirements.txt`
        
3. Activate the conda environment:
    - Windows command: `activate bid_solver_server` 
    - MacOS / Linux command: `conda activate bid_solver_server`

For more references on conda environments, refer to [Conda Managing Environments](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html) or the [Conda Cheat Sheet](https://docs.conda.io/projects/conda/en/4.6.0/_downloads/52a95608c49671267e40c689e0bc00ca/conda-cheatsheet.pdf)