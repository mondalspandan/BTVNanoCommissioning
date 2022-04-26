
# BTVNanoCommissioning
Repository for Commissioning studies in the BTV POG based on (custom) nanoAOD samples

## Requirements
### Setup 
```
# only first time 
git clone git@github.com:cms-btv-pog/BTVNanoCommissioning.git 

# activate enviroment once you have coffea framework 
conda activate coffea
```
### Coffea installation with Miniconda
For installing Miniconda, see also https://hackmd.io/GkiNxag0TUmHnnCiqdND1Q#Local-or-remote
```
wget https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
# Run and follow instructions on screen
bash Miniconda3-latest-Linux-x86_64.sh
```
NOTE: always make sure that conda, python, and pip point to local Miniconda installation (`which conda` etc.).

You can either use the default environment`base` or create a new one:
```
# create new environment with python 3.7, e.g. environment of name `coffea`
conda create --name coffea python3.7
# activate environment `coffea`
conda activate coffea
```
Install coffea, xrootd, and more:
```
pip install git+https://github.com/CoffeaTeam/coffea.git #latest published release with `pip install coffea`
conda install -c conda-forge xrootd
conda install -c conda-forge ca-certificates
conda install -c conda-forge ca-policy-lcg
conda install -c conda-forge dask-jobqueue
conda install -c anaconda bokeh 
conda install -c conda-forge 'fsspec>=0.3.3'
conda install dask
```
### Other installation options for coffea
See https://coffeateam.github.io/coffea/installation.html
### Running jupyter remotely
See also https://hackmd.io/GkiNxag0TUmHnnCiqdND1Q#Remote-jupyter

1. On your local machine, edit `.ssh/config`:
```
Host lxplus*
  HostName lxplus7.cern.ch
  User <your-user-name>
  ForwardX11 yes
  ForwardAgent yes
  ForwardX11Trusted yes
Host *_f
  LocalForward localhost:8800 localhost:8800
  ExitOnForwardFailure yes
```
2. Connect to remote with `ssh lxplus_f`
3. Start a jupyter notebook:
```
jupyter notebook --ip=127.0.0.1 --port 8800 --no-browser
```
4. URL for notebook will be printed, copy and open in local browser



## Structure
Example worfkflow for ttbar is included. 

Each workflow can be a separate "processor" file, creating the mapping from NanoAOD to
the histograms we need. Workflow processors can be passed to the `runner.py` script 
along with the fileset these should run over. Multiple executors can be chosen 
(for now iterative - one by one, uproot/futures - multiprocessing and dask-slurm). 

To run the example, run:
```
python runner.py --workflow ttcom
```

Example plots can be found in ` make_some_plots.ipynb` though we might want to make
that more automatic in the end.

To test a small set of files to see whether the workflows run smoothly, run:
```
python runner.py --workflow ${workflow} --json metadata/test.json 
```

### b-SFs 

<details><summary>details</summary>
<p>

- Dileptonic ttbar phase space : check performance for btag SFs, muon channel

```
python runner.py --workflow ttdilep_sf --json metadata/94X_doublemu_PFNano.json
```

- Semileptonic ttbar phase space : check performance for btag SFs, muon channel

```
python runner.py --workflow ttsemilep_sf --json metadata/94X_singlemu_PFNano.json
```

</p>
</details>

### c-SFs
<details><summary>details</summary>
<p>

- Dileptonic ttbar phase space : check performance for charm SFs, bjets enriched SFs, muon channel

```
python runner.py --workflow ctag_ttdilep_sf --json metadata/94X_doublemu_PFNano.json
```


- Semileptonic ttbar phase space : check performance for charm SFs, bjets enriched SFs, muon channel

```
python runner.py --workflow ctag_ttsemilep_sf --json metadata/94X_singlemu_PFNano.json
```

- W+c phase space : check performance for charm SFs, cjets enriched SFs, muon  channel

```
python runner.py --workflow ctag_ttdilep_sf --json metadata/94X_singlemu_PFNano.json
```

- DY phase space : check performance for charm SFs, light jets enriched SFs, muon channel

```
python runner.py --workflow ctag_ttdilep_sf --json ctag_DY_mu_PFNano.json
```

</p>
</details>


### Fatjet taggers

More information in this [readme page](docs/README_fatjet_tagger.md).

### Validation - check different campaigns

<details><summary>details</summary>
<p>

Only basic jet selections(PUID, ID, pT, $\eta$) applied. Put the json files with different campaigns

```
python runner.py --workflow valid --json {}
```

</p>
</details>



## Scale-out (Sites)

Scale out can be notoriously tricky between different sites. Coffea's integration of `slurm` and `dask`
makes this quite a bit easier and for some sites the ``native'' implementation is sufficient, e.g Condor@DESY.
However, some sites have certain restrictions for various reasons, in particular Condor @CERN and @FNAL.

### Condor@FNAL (CMSLPC)
Follow setup instructions at https://github.com/CoffeaTeam/lpcjobqueue. After starting 
the singularity container run with 
```bash
python runner.py --wf ttcom --executor dask/lpc
```

### Condor@CERN (lxplus)
Only one port is available per node, so its possible one has to try different nodes until hitting
one with `8786` being open. Other than that, no additional configurations should be necessary.

```bash
python runner.py --wf ttcom --executor dask/lxplus
```

### Coffea-casa (Nebraska AF)
Coffea-casa is a JupyterHub based analysis-facility hosted at Nebraska. For more information and setup instuctions see
https://coffea-casa.readthedocs.io/en/latest/cc_user.html

After setting up and checking out this repository (either via the online terminal or git widget utility run with
```bash
python runner.py --wf ttcom --executor dask/casa
```
Authentication is handled automatically via login auth token instead of a proxy. File paths need to replace xrootd redirector with "xcache", `runner.py` does this automatically.


### Condor@DESY 
```bash
python runner.py --wf ttcom --executor dask/condor
```

### Maxwell@DESY 
```bash
python runner.py --wf ttcom --executor parsl/slurm
```


## Make the json files

Use the `fetch.py` in `filefetcher`, the `$input_DAS_list` is the info extract from DAS, and output json files in `metadata/`

```
python fetch.py --input ${input_DAS_list} --output ${output_json_name} --site ${site}
```

## Plotting code

- data/MC comparison code

```python
python plotdataMC.py --lumi ${lumi} --phase ctag_ttdilep_sf --output ctag_ttdilep_sf (--discr zmass --log True/False --data data_runD)
# lumi in /pb
# phase = workflow 
# output coffea file output = hist_$output$.coffea 
# discr = input variables, the defaults are the discriminators, can add multiple variables with space
# log = logorithm on y-axis
# data = data name
```

- data/data, MC/MC comparison

```python
python comparison.py --phase ctag_ttdilep_sf --output ctag_ttdilep_sf -ref 2017_runB --compared 2017_runC 2017_runD (--discr zmass --log True/False --sepflav True/False)
# phase = workflow 
# output coffea file output = hist_$output$.coffea 
# ref = reference data/MC sample
# comapred = 
# discr = input variables, the defaults are the discriminators, can add multiple variables with space
# log = logorithm on y-axis
# sepflav = separate the jets into different flavor
```
