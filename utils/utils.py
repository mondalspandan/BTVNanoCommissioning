import collections
import numpy as np
import awkward as ak
from helpers.fatjet_tagger_parameters import lumi, xsecs

def rescale(accumulator, xsecs=xsecs, lumi=lumi, data="BTagMu"):
#def rescale(accumulator, xsecs=xsecs, data="BTagMu"):
    """Scale by lumi"""
    #lumi = 1000*lumi    # Convert lumi to pb^-1
    from coffea import hist
    scale = {}
    sumxsecs = ak.sum(xsecs.values())
    #N_data = accumulator['nbtagmu_event_level'][data]
    #print("N_data =", N_data)
    for dataset, N_mc in collections.OrderedDict(sorted(accumulator['sumw'].items())).items():
        if dataset in xsecs:
            print(" ", dataset, "\t", N_mc, "events\t", xsecs[dataset], "pb")
            #scale[dataset] = (xsecs[dataset]/sumxsecs)*(N_data/N_mc)
            scale[dataset] = (xsecs[dataset]*lumi)/N_mc
        else:
            print(" ", "X ", dataset)
            scale[dataset] = 0#lumi / N_mc
    print(scale)

    datasets_mc = [item for item in list(xsecs.keys()) if not 'GluGlu' in item]
    for h in accumulator.values():
        if isinstance(h, hist.Hist):
            h.scale(scale,       axis="dataset")
            N_data = ak.sum(h[data].values().values())
            N_mc = ak.sum(h[datasets_mc].sum('dataset', 'flavor').values().values())
            #scaletodata = dict(zip(scale.keys(), len(scale)*[1./N_data]))
            scaletodata = dict(zip(scale.keys(), len(scale)*[N_data/N_mc]))
            h.scale(scaletodata, axis="dataset")
    return accumulator

def get_nsv(sj, sv, R=0.4):

    sv_dr = sj.delta_r(sv)
    nsv = ak.count(sv_dr[sv_dr < R], axis=1)

    return nsv

def get_sv_in_jet(jet, sv, R=0.8):

    sv_dr = jet.delta_r(sv)
    sv_in_jet = ak.fill_none(sv_dr < R, [])

    return sv_in_jet

"""
def xSecReader(fname):
   # Probably unsafe
    with open(fname) as file:
        lines = file.readlines()
    lines = [l.strip("\n") for l in lines if not l.startswith("#")]
    lines = [l.split("#")[0] for l in lines if len(l) > 5]

    _dict = {}
    for line in lines:
        key = line.split()[0]
        valuex = line.split()[1:]
        if len(valuex) > 1:
            value = "".join(valuex)
        else:
            value = valuex[0]
        _dict[key] = float(eval(value))
    return _dict

"""
