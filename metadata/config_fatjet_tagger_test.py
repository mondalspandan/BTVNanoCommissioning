cfg =  {
    # Dataset parameters
    "dataset"  : "datasets/DAS/datasets_btag2016ULPreVFP.txt",
    "json"     : "datasets/RunIISummer20UL16-PreVFP.json",
    "storage_prefix" : "/pnfs/psi.ch/cms/trivcat/store/user/mmarcheg/BTVNanoCommissioning",
    "campaign" : "UL",
    "year"     : "2016",

    # PU files https://cms-nanoaod-integration.web.cern.ch/commonJSONSFs/LUMI_puWeights_Run2_UL/
    'puFile'  : '/cvmfs/cms.cern.ch/rsync/cms-nanoAOD/jsonpog-integration/POG/LUM/2016preVFP_UL/puWeights.json.gz',
    'puJSON'   : 'Collisions16_UltraLegacy_goldenJSON',
    'nTrueFile' : '',

    # JEC
    "JECfolder": "tmp/",

    # Input and output files
    "workflow" : "fatjet_tagger",
    "input"    : "filefetcher/samplesQCDMuEn_JetHT_RunIISummer20UL16-PreVFP.json",
    "output"   : "histograms/RunIISummer20UL16-PreVFP_limit2.coffea",
    "plots"    : "plots/test",

    # Executor parameters
    "run_options" : {
        "executor"     : "futures",
        "workers"      : 12,
        "scaleout"     : 10,
        "chunk"        : 50000,
        "max"          : None,
        "skipbadfiles" : None,
        "voms"         : None,
        "limit"        : 2,
        "mem_per_worker" : None,
        "partition"    : 'standard',
        "exclusive"    : True,
        "walltime"     : "12:00:00",
    },

    # Processor parameters
    "checkOverlap" : False,
    "hist2d"       : False,
    "mupt"         : 5,
}
