#!/usr/bin/env python
""" Tool to translate HDF5 files to DosNa"""

import logging

import numpy as np

import os
import h5py
import json
import dosna as dn
import hdf5todict as hd
from hdf5todict import LazyHdfDict
from dosna.backends import Backend
from dosna.backends.base import (BackendConnection, BackendDataChunk,
                                 BackendDataset, DatasetNotFoundError)

class Dosnatohdf5():
    """
    Includes methods to transform HDF5 to DosNa Objects
    """

    def __init__(self, connection=None):
        self._connection = connection
        self.max_num_bytes = 5
        
    def dosna_to_dict(self):
        root_group = self._connection.root_group
        def _recurse(links, dosnadict):
            for key, value in links.items():
                dosnadict[key] = {}
                if hasattr(value.target, "shape"):
                    dataset = value.target
                    dosnadict[key] = dataset
                else:
                    links = value.target.links
                    dosnadict[key] = _recurse(links, dosnadict[key])
            return dosnadict
        return _recurse(root_group.links, {})
    
    def dosnadict_to_hdf5(self, dosnadict, h5file):
        
        def _recurse(dosnadict, hdfobject):
            for key, value in dosnadict.items():
                if isinstance(value, dict):
                    if not key in list(hdfobject.keys()):
                        hdfgroup = hdfobject.create_group(key)
                        _recurse(value, hdfgroup)
                    else:
                        raise Exception("Group", key, "already created")
                else:
                    if not key in list(hdfobject.keys()):
                        dataset = hdfobject.create_dataset(
                            key,
                            shape=value.shape,
                            chunks=value.chunk_size,
                            dtype=value.dtype
                        )
                    else:
                        raise Exception("Dataset", key, "already created")
                        """
                        if dataset.chunks is not None:
                            for s in dataset.iter_chunks():
                                dataset[s] = value[s]
                        """
        with h5py.File(h5file, "w") as hdf:
            _recurse(dosnadict, hdf)
            return hdf
        
    def dosnadict_to_jsondict(self, dosnadict, jsonfile):
        
        def _recurse(dosnadict, jsondict):
            for key, value in dosnadict.items():
                if isinstance(value, dict):
                    jsondict[key] = {}
                    jsondict[key] = _recurse(value, jsondict[key])
                else:
                    jsondict[key] = {}
                    jsondict[key]["name"] = key # TODO path = key.split("/")
                    jsondict[key]["shape"] = value.shape
                    jsondict[key]["dtype"] = value.dtype.__name__
                    jsondict[key]["fillvalue"] = value.fillvalue
                    jsondict[key]["chunk_size"] = value.chunk_size
                    jsondict[key]["chunk_grid"] = value.chunk_grid.tolist()
                    jsondict[key]["is_dataset"] = True
                    #jsondict[key]["absolute_path"] = value.name # TODO absolute path
            return jsondict
        
        jsondict =  _recurse(dosnadict, {})
        
        with open(jsonfile, 'w') as f:
            f.write(json.dumps(jsondict))
        
        return jsondict

    def json_to_hdf5(self, jsonfile, h5file):
        
        with open(jsonfile, 'r') as f:
            jsondict = json.loads(f.read())
        
        def _recurse(jsondict, hdf5dict, group):
            for key, value in jsondict.items():
                if isinstance(value, dict):
                    if "is_dataset" in value:
                        dataset = group.get(key)
                    else:
                        subgroup = group.get(key)
                        _recurse(value, hdf5dict, subgroup)
        with h5py.File(h5file, "r") as hdf:
            _recurse(jsondict, {}, hdf)
            return hdf