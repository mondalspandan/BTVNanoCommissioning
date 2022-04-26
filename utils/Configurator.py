import os
import sys
import json
import importlib.util

#from parameters.allhistograms import histogram_settings

class Configurator():
    def __init__(self, cfg, plot=False, create_dataset=False):
        # Load config file and attributes
        self.plot    = plot
        self.create_dataset = create_dataset
        self.load_config(cfg)
        self.load_attributes()

        if not self.create_dataset:
            # Load dataset
            self.load_dataset()

            # Check if output file exists, and in case add a `_v01` label
            self.overwrite_check()

            # Truncate file list if self.limit is not None
            self.truncate_filelist()

            # Define output file path
            self.define_output()

            # Load histogram settings
            #self.load_histogram_settings()

            # Load workflow
            self.load_workflow()

    def load_config(self, path):
        spec = importlib.util.spec_from_file_location("cfg", path)
        cfg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cfg)
        self.cfg = cfg.cfg

    def load_attributes(self):
        for key, item in self.cfg.items():
            setattr(self, key, item)
        for key in ['only']:
            try: getattr(self, key)
            except: setattr(self, key, '')
        self.plots = os.path.abspath(self.plots)

    def load_dataset(self):
        with open(self.input) as f:
            self.fileset = json.load(f)

    def overwrite_check(self):
        if self.plot:
            print(f"The output will be saved to {self.plots}")
            return
        elif self.create_dataset:
            print(f"The output will be saved to {self.json}")
            return
        else:
            path = self.output
            version = 1
            while os.path.exists(path):
                tag = str(version).rjust(2, '0')
                path = self.output.replace('.coffea', f'_v{tag}.coffea')
                version += 1
            if path != self.output:
                print(f"The output will be saved to {path}")
            self.output = path

    def truncate_filelist(self):
        try: self.run_options['limit']
        except: self.run_options['limit'] = None
        if self.run_options['limit']:
            for dataset, filelist in self.fileset.items():
                if isinstance(filelist, dict):
                    self.fileset[dataset]["files"] = self.fileset[dataset]["files"][:self.run_options['limit']]
                elif isinstance(filelist, list):
                    self.fileset[dataset] = self.fileset[dataset][:self.run_options['limit']]
                else:
                    raise NotImplemented

    def define_output(self):
        try: self.output
        except: self.output = f'hists_{self.workflow}_{(self.input).rstrip(".json")}.coffea'

    def load_histogram_settings(self):
        if isinstance(self.cfg['variables'], list):
            self.cfg['variables'] = {var_name : None for var_name in self.cfg['variables']}
        for var_name in self.cfg['variables'].keys():
            if self.cfg['variables'][var_name] == None:
                self.cfg['variables'][var_name] = histogram_settings['variables'][var_name]
            elif not isinstance(self.cfg['variables'][var_name], dict):
                sys.exit("Format non valid for histogram settings")
            elif set(self.cfg['variables'][var_name].keys()) != {'binning', 'xlim', 'xlabel'}:
                sys.exit("Missing keys in histogram settings. Required keys: {'binning', 'xlim', 'xlabel'}")
            elif set(self.cfg['variables'][var_name]['binning'].keys()) != {'n_or_arr', 'lo', 'hi'}:
                sys.exit("Missing keys in histogram binning. Required keys: {'n_or_arr', 'lo', 'hi'}")

    def load_workflow(self):
        if self.workflow == "fatjet_tagger":
            from workflows.fatjet_tagger import NanoProcessor
            self.processor_instance = NanoProcessor(cfg=self.cfg)
        elif self.workflow == "fatjet_tagger_ggHcc":
            from workflows.fatjet_tagger_ggHcc import NanoProcessor
            self.processor_instance = NanoProcessor(cfg=self.cfg)
        else:
            raise NotImplemented
