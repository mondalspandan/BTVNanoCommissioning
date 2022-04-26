# Fatjet taggers 

The workflow is similar than for other taggers. However, several configuration parameters are simplified in a config file. More information below.

## How to run
To run the example, run:
```
python runner.py --cfg config/test.py
```

All the parameters relevant to the input and output files are saved in a config file as a Python dictionary and passed as an argument to `runner.py`.

Example plots can be found in ` make_some_plots.ipynb` though we might want to make
that more automatic in the end.

## Apply corrections 

### Pileup reweighting

Before the inclusion of the [jsonpog](https://gitlab.cern.ch/cms-nanoAOD/jsonpog-integration/-/tree/master), this reweighting was done manually by running the instructions in this section. __For UL campaigns, this step is not needed__.

To apply pileup reweighting in your MC samples, one needs to create first the pileup profile of the MC sample. This can be done with the script `createNTrueForPU.py`. This will take some of the files from your dataset and create a coffea file with that profile. To run it:
```
python createNTrueForPU.py --samples datasets/datasets_btag2017.json --year 2017 
```
The output will be stored in the `correction_files` folder with the name like: `nTrueInt_datasets_btag2017_2017.coffea`. In addition, you need to properly set the `self.puFile` and `self.nTrueFile` in your workflow file.

### Jet energy corrections
You need to download the tar files needed for the JECs from [this twiki](https://twiki.cern.ch/twiki/bin/viewauth/CMS/JECdataMC), in the `correction_files/JEC` folder and properly set these names in the dictionaries `parameters.jecTarFiles` and in `parameters.JECversions`.

## Scale Factors

### Installation

There are known conflicts when using a `coffea` conda environment and [combine](https://cms-analysis.github.io/HiggsAnalysis-CombinedLimit/). Try to keep two different environments. One to create the histograms in ``coffea`` and another to run `combine`. 

To install combine, follow the instructions from their [documentation](https://cms-analysis.github.io/HiggsAnalysis-CombinedLimit/#for-end-users-that-dont-need-to-commit-or-do-any-development). If you dont have `root` by default in your machine, you might need to install the version inside CMSSW. Otherwise you can use the standalone version.

In addition, you need to download the [rhalphalib](https://github.com/nsmith-/rhalphalib) package
```
pip install --user https://github.com/nsmith-/rhalphalib/archive/master.zip
```

### Create datacards for combine

First we need to translate the coffea histograms into numpy arrays. For this in the coffea environment one can run the script: [coffeaToPickle.py](coffeaToPickle.py), which creates a pickle file with the inputs needed. As example:
```
python coffeaToPickle.py -i histograms/hists_fattag_pileupJEC_2017_WPcuts_v01.coffea7 --year 2017
```
For the rest, migrate to the environment with combine. The script [scaleFactorComputation.py](scaleFactorComputation.py) can create the datacard needed in combine and also run the `FitDiagnostics` step in combine. As example:
```
python scaleFactorComputation.py --year 2017 --tpf histograms/hists_fattag_pileupJEC_2017_WPcuts_v01.pkl --selection msd100tau06DDB
```

Alternatively, the wrapped-up script [runSF.py](runSF.py) performs the fits for a given data taking year, in all pT bins and for DDB and DDC taggers, with multiple calls of [scaleFactorComputation.py](scaleFactorComputation.py). As example:
```
python runSF.py --year 2018 --tpf histograms/hists_fattag_pileupJEC_2018UL_WPcuts_sv1mass_pt500.pkl --outputDir /work/mmarcheg/BTVNanoCommissioning/fitdir/2018ULpt500 --pt 500
```

### Create pre/post-fit plots
After extracting the SF for all the pT bins and for all the taggers, the pre/post-fit plots in the pass and fail regions can be created by running the script [make_SFplots.py](make_SFplots.py):
```
python make_SFplots.py -i /work/mmarcheg/BTVNanoCommissioning/fitdir/2017EOYpt450 --year 2017
```
