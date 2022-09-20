import importlib.resources
import gzip
import pickle
import contextlib
import cloudpickle

import numpy as np
import awkward as ak
from coffea.lookup_tools.lookup_base import lookup_base
from coffea.lookup_tools import extractor

from coffea.analysis_tools import Weights

from coffea.lumi_tools import LumiMask
from coffea.btag_tools import BTagScaleFactor
from coffea.jetmet_tools import JECStack, CorrectedJetsFactory
from coffea.lookup_tools import extractor

# FIXME make jsons campaing configurable
lumiMasks = {}
_lumi_path = "BTVNanoCommissioning.data.lumiMasks"
with importlib.resources.path(
    _lumi_path, "Cert_271036-284044_13TeV_23Sep2016ReReco_Collisions16_JSON.txt"
) as filename:
    lumiMasks["2016"] = LumiMask(filename)
with importlib.resources.path(
    _lumi_path, "Cert_294927-306462_13TeV_EOY2017ReReco_Collisions17_JSON_v1.txt"
) as filename:
    lumiMasks["2017"] = LumiMask(filename)
with importlib.resources.path(
    _lumi_path,
    "Cert_314472-325175_13TeV_17SeptEarlyReReco2018ABC_PromptEraD_Collisions18_JSON.txt",
) as filename:
    lumiMasks["2018"] = LumiMask(filename)
with importlib.resources.path(
    _lumi_path,
    "Cert_271036-284044_13TeV_Legacy2016_Collisions16_JSON.txt",
) as filename:
    lumiMasks["UL16"] = LumiMask(filename)
with importlib.resources.path(
    _lumi_path,
    "Cert_294927-306462_13TeV_UL2017_Collisions17_GoldenJSON.txt",
) as filename:
    lumiMasks["UL17"] = LumiMask(filename)
with importlib.resources.path(
    _lumi_path,
    "Cert_314472-325175_13TeV_Legacy2018_Collisions18_JSON.txt",
) as filename:
    lumiMasks["UL18"] = LumiMask(filename)
## MET filters
met_filters = {
    "UL16": {
        "data": [
            "goodVertices",
            "globalSuperTightHaloUL16Filter",
            "HBHENoiseFilter",
            "HBHENoiseIsoFilter",
            "EcalDeadCellTriggerPrimitiveFilter",
            "BadPFMuonFilter",
            "BadPFMuonDzFilter",
            "eeBadScFilter",
        ],
        "mc": [
            "goodVertices",
            "globalSuperTightHalo2016Filter",
            "HBHENoiseFilter",
            "HBHENoiseIsoFilter",
            "EcalDeadCellTriggerPrimitiveFilter",
            "BadPFMuonFilter",
            "BadPFMuonDzFilter",
            "eeBadScFilter",
        ],
    },
    "UL17": {
        "data": [
            "goodVertices",
            "globalSuperTightHalo2016Filter",
            "HBHENoiseFilter",
            "HBHENoiseIsoFilter",
            "EcalDeadCellTriggerPrimitiveFilter",
            "BadPFMuonFilter",
            "BadPFMuonDzFilter",
            "hfNoisyHitsFilter",
            "eeBadScFilter",
            "ecalBadCalibFilter",
        ],
        "mc": [
            "goodVertices",
            "globalSuperTightHalo2016Filter",
            "HBHENoiseFilter",
            "HBHENoiseIsoFilter",
            "EcalDeadCellTriggerPrimitiveFilter",
            "BadPFMuonFilter",
            "BadPFMuonDzFilter",
            "hfNoisyHitsFilter",
            "eeBadScFilter",
            "ecalBadCalibFilter",
        ],
    },
    "UL18": {
        "data": [
            "goodVertices",
            "globalSuperTightHalo2016Filter",
            "HBHENoiseFilter",
            "HBHENoiseIsoFilter",
            "EcalDeadCellTriggerPrimitiveFilter",
            "BadPFMuonFilter",
            "BadPFMuonDzFilter",
            "hfNoisyHitsFilter",
            "eeBadScFilter",
            "ecalBadCalibFilter",
        ],
        "mc": [
            "goodVertices",
            "globalSuperTightHalo2016Filter",
            "HBHENoiseFilter",
            "HBHENoiseIsoFilter",
            "EcalDeadCellTriggerPrimitiveFilter",
            "BadPFMuonFilter",
            "BadPFMuonDzFilter",
            "hfNoisyHitsFilter",
            "eeBadScFilter",
            "ecalBadCalibFilter",
        ],
    },
}

##JEC
def load_jetfactory(campaign, path):
    _jet_path = f"BTVNanoCommissioning.data.JME.{campaign}"
    with importlib.resources.path(_jet_path, path) as filename:
        with gzip.open(filename) as fin:
            jmestuff = cloudpickle.load(fin)

    jet_factory = jmestuff["jet_factory"]
    return jet_factory

def load_jmefactory(campaign, path):
    _jet_path = f"BTVNanoCommissioning.data.JME.{campaign}"
    with importlib.resources.path(_jet_path, path) as filename:
        with gzip.open(filename) as fin:
            jmestuff = cloudpickle.load(fin)

        #jet_factory = jmestuff["jet_factory"]
    return jmestuff



def add_jec_variables(jets, event_rho):
    jets["pt_raw"] = (1 - jets.rawFactor) * jets.pt
    jets["mass_raw"] = (1 - jets.rawFactor) * jets.mass
    if hasattr(jets, "genJetIdxG"):
        jets["pt_gen"] = ak.values_astype(
            ak.fill_none(jets.matched_gen.pt, 0), np.float32
        )
    jets["event_rho"] = ak.broadcast_arrays(event_rho, jets.pt)[0]
    return jets


def load_metfactory(campaign, path):
    _jet_path = f"BTVNanoCommissioning.data.JME.{campaign}"
    with importlib.resources.path(_jet_path, path) as filename:
        with gzip.open(filename) as fin:
            jmestuff = cloudpickle.load(fin)

    met_factory = jmestuff["met_factory"]
    return met_factory



## PU weight
def load_pu(campaign, path):
    _pu_path = f"BTVNanoCommissioning.data.PU.{campaign}"
    with importlib.resources.path(_pu_path, path) as filename:

        if str(filename).endswith(".pkl.gz"):
            with gzip.open(filename) as fin:
                compiled = cloudpickle.load(fin)
        elif str(filename).endswith(".histo.root"):
            ext = extractor()
            ext.add_weight_sets([f"* * {filename}"])
            ext.finalize()
            compiled = ext.make_evaluator()

    return compiled


## BTag SFs
def load_BTV(campaign, path, tagger):
    _btag_path = f"BTVNanoCommissioning.data.BTV.{campaign}"
    if tagger == "DeepCSVB" or tagger == "DeepJetB":
        with importlib.resources.path(_btag_path, path[tagger]) as filename:
            deepsf = BTagScaleFactor(
                filename,
                BTagScaleFactor.RESHAPE,
                methods="iterativefit,iterativefit,iterativefit",
            )
    elif tagger == "DeepCSVC" or tagger == "DeepJetC":
        deepsf = "BTVNanoCommissioning/data/BTV/" + campaign + "/" + path[tagger]
    return deepsf


### Lepton SFs

# with contextlib.ExitStack() as stack:
#     # this would work even in zipballs but since extractor keys on file extension and
#     # importlib make a random tempfile, it won't work. coffea needs to enable specifying the type manually
#     # for now we run this whole module as $ python -m boostedhiggs.build_jec boostedhiggs/data/jec_compiled.pkl.gz
#     # so the compiled value can be loaded using the importlib tool in corrections.py
#     _ele_path = "BTVNanoCommissioning.data.LSF.Rereco17_94X"
#     real_paths = [stack.enter_context(importlib.resources.path(_ele_path, f)) for f in ele_sf_mapping.values()]
#     ext.add_weight_sets([f"{path} {file}" for path, file in zip(ele_sf_mapping.keys(), real_paths)])
#     ext.finalize()
# evaluator = ext.make_evaluator()
### Lepton SFs
def eleSFs(ele, campaign, path):
    _ele_path = f"BTVNanoCommissioning.data.LSF.{campaign}"
    ext = extractor()
    with contextlib.ExitStack() as stack:
        real_paths = [
            stack.enter_context(importlib.resources.path(_ele_path, f))
            for f in path.values()
        ]
        ext.add_weight_sets(
            [f"{path} {file}" for path, file in zip(path.keys(), real_paths)]
        )

    ext.finalize()
    evaluator = ext.make_evaluator()
    ele_eta = ak.fill_none(ele.eta, 0.0)
    ele_pt = ak.fill_none(ele.pt, 0.0)
    weight = 1.0
    for paths in path.keys():
        if "ele_Trig" in paths:
            weight = weight * evaluator[paths[: paths.find(" ")]](ele_pt)
        elif "ele" in paths:
            weight = weight * evaluator[paths[: paths.find(" ")]](ele_eta, ele_pt)
    return weight



def muSFs(mu, campaign, path):
    _ele_path = f"BTVNanoCommissioning.data.LSF.{campaign}"
    ext = extractor()
    with contextlib.ExitStack() as stack:
        real_paths = [
            stack.enter_context(importlib.resources.path(_ele_path, f))
            for f in path.values()
        ]
        ext.add_weight_sets(
            [f"{path} {file}" for path, file in zip(path.keys(), real_paths)]
        )

    ext.finalize()
    evaluator = ext.make_evaluator()
    mu_eta = ak.fill_none(mu.eta, 0.0)
    mu_pt = ak.fill_none(mu.pt, 0.0)
    weight = 1.0
    for paths in path.keys():
        if "mu" in paths:
            weight = weight * evaluator[paths[: paths.find(" ")]](mu_eta, mu_pt)
    return weight

