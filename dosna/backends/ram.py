#!/usr/bin/env python
"""backend RAM keeps every data structure in memory"""

import logging

import numpy as np

import random
import string

from dosna.backends import Backend
from dosna.backends.base import (BackendConnection, BackendDataChunk,
                                 BackendDataset, DatasetNotFoundError,
                                 BackendGroup, GroupNotFoundError)

log = logging.getLogger(__name__)

class MemConnection(BackendConnection):
    """
    A Memory Connection represents a dictionary.
    """
    def __init__(self, *args, **kwargs):
        super(MemConnection, self).__init__(*args, **kwargs)
        self.root_group = MemGroup(self, "/", attrs=None)
        self.datasets = {}
        
    def create_group(self, path, attrs=None):
        if not path.isalnum():
            raise Exception("String ", path, "is not alphanumeric")
        if path != "/":
            return self.root_group.create_group(path, attrs)
        else:
            raise Exception("Group", path, "already exists")
        
    def get_group(self, path):
        return self.root_group.get_group(path)
    
    def has_group(self, path):
        return self.root_group.has_group(path)
        
    def del_group(self, path):
        self.root_group.del_group(path)
    
    def create_dataset(self, name, shape=None, dtype=np.float32, fillvalue=0,
                       data=None, chunk_size=None):

        if not ((shape is not None and dtype is not None) or data is not None):
            raise Exception('Provide `shape` and `dtype` or `data`')
        if self.has_dataset(name):
            raise Exception('Dataset `%s` already exists' % name)

        if data is not None:
            shape = data.shape
            dtype = data.dtype

        if chunk_size is None:
            chunk_size = shape

        chunk_grid = (np.ceil(np.asarray(shape, float) / chunk_size))\
            .astype(int)

        log.debug('Creating Dataset `%s`', name)
        self.datasets[name] = None  # Key `name` has to exist
        dataset = MemDataset(self, name, shape, dtype, fillvalue, chunk_grid,
                             chunk_size)
        self.datasets[name] = dataset
        return dataset

    def get_dataset(self, name):
        if not self.has_dataset(name):
            raise DatasetNotFoundError('Dataset `%s` does not exist' % name)
        return self.datasets[name]

    def has_dataset(self, name):
        return name in self.datasets

    def del_dataset(self, name):
        if not self.has_dataset(name):
            raise DatasetNotFoundError('Dataset `%s` does not exist' % name)
        log.debug('Removing Dataset `%s`', name)
        del self.datasets[name]
        
class MemLink(): # TODO implement this in
    def __init__(self, source, target, name):
        self.source = source
        self.target = target
        self.name = name
        
class MemGroup(BackendGroup):
    
    def __init__(self, parent, name, attrs, *args, **kwargs):
        super(MemGroup, self).__init__(parent, name, attrs)
        self.parent = parent
        self.links = {}
        self.attrs = attrs
        self.datasets = {}
        self.connection = self.get_connection() # TODO is this necessary?
        self.absolute_path = self.get_absolute_path() # TODO too much recursion?
        #self.path_split = TODO
        
    def get_connection(self):
        """
        Recursively access the parent groups until the parent group is the
        root group which is "/", then get the parent name of the root group
        which is the name of the connection.
        
        :return name of the DosNa connection
        """
        def find_connection(group):
            if group.name == "/":
                return group.parent.name
            else:
                return find_connection(group.parent)
            
        return find_connection(self)
    
    def get_absolute_path(self):
        """
        Recursively access the parent groups until the parent name is the root group "/"
        and append the name of the parent groups to obtain the full path from the root group.
        
        :return absolute path name from the root group
        """
        
        def find_path(group):
            full_path = []
            if group.name == "/":
                return full_path
            else:
                full_path.append(group.name)
                full_path += find_path(group.parent)
            return full_path
        
        full_path_list = find_path(self)
        full_path_list.reverse()
        full_path = "/" + '/'.join(full_path_list)
        return full_path
    
    def keys(self):
        """
        Get the names of directly attached group memebers. 
        """
        return list(self.links.keys())
    
    def values(self):
        """
        Get the objects contained in the group (Group and Dataset instances).
        """
        objects = []
        for value in self.links.values():
            objects.append(value.target)
        return objects
    
    def items(self):
        """
        Get (name, value) pairs for objects directly attached to this group.
        """
        items = {}
        for value in self.links.values():
            items[value.name] = value.target
        return items
    
    def create_group(self, path, attrs=None):
        """
        Creates a new empty group.
        Validates the path is alphanumeric.
        If path is not in the links attached to the group, it will create a new group and link.
        The link will the current group as source and the new group as target. The name of the link
        is the name of the group.
        :param string that provides an absolute path or a relative path to the new group
        :return new group
        """
        if not path.isalnum():
            raise Exception("String ", path, "is not alphanumeric")
        elif path in self.links:
            raise Exception("Group", path, "already exists")
        else:
            group = MemGroup(self, path, attrs)
            link = MemLink(self, group, path)
            self.links[path] = link
            return group
            
        
    def get_group(self, path):
        """
        Splits the path string for each slash found.
        For each element in the resulting array, it checks recursively whether the first element
        of the array is in the dictionary of links. If it is, it pops the the first element and
        performs the same process with the next element of the array and the next group links.
        
        :param string that provides an absolute path or a relative path to the new group
        :return DosNa group
        """
        def _recurse(arr, links):
            if arr[0] in links:
                link_target = links.get(arr[0]).target
                if len(arr) > 1:
                    arr.pop(0)
                    return _recurse(arr, link_target.links)
                else:
                    return link_target
        
        path_elements = path.split("/") # TODO change this
        group = _recurse(path_elements, self.links)
        
        if group is None:
            raise GroupNotFoundError("Group ", path, "does not exist")
        return group
    
    def has_group(self, path): # TODO: get group
        """
        Splits the path string for each slash found.
        For each element in the resulting array, it checks recursively whether the first element
        of the array is in the dictionary of links. If it is, it pops the the first element and
        performs the same process with the next element of the array and the next group links.
        """
        if self.get_group(path):
            True
        else:
            raise GroupNotFoundError("Group", path, "does not exist")
        
    
    def del_group(self, path):
        """
        Recursively access links to find group, and then deletes it. 
        """
        if not self.has_group(path):
            raise GroupNotFoundError("Group", path, "does not exist")

        def _recurse(arr, links):
            if arr[0] in links:
                link_target = links.get(arr[0]).target
                log.debug("Removing Group", path)
                if len(arr) > 1:
                    arr.pop(0)
                    return _recurse(arr, link_target.links)
                else:
                    del links[arr[0]]
        
        arr = path.split("/")
        _recurse(arr, self.links)
        
    def get_groups(self): # TODO docstring
        """
        Recursively visit all objects in this group and subgroups
        :return all objects names of the groups and subgroups of this group
        """
        def _recurse(links):
            groups = []
            for key, value in links.items():
                subgroup = value.target
                if hasattr(subgroup, "links"):
                    #groups.append(key)
                    groups.append(subgroup.absolute_path)
                    groups += _recurse(subgroup.links)
            return groups
        
        return _recurse(self.links)
    
    def get_objects(self): # TODO visit datasets not absolute path
        """
        Recursively visit all objects in this group and subgroups
        :return all objects names of the groups, subgroups and datasets of this group
        """
        
        def _recurse(links):
            objects = []
            for key, value in links.items():
                objects.append(key)
                if hasattr(value.target, "links"):
                    objects += _recurse(value.target.links)
            return objects
        
        return _recurse(self.links)
        

    def create_dataset(
        self,
        name,
        shape=None,
        dtype=np.float32,
        fillvalue=0,
        data=None,
        chunk_size=None,
    ):

        if not ((shape is not None and dtype is not None) or data is not None):
            raise Exception("Provide `shape` and `dtype` or `data`")
        if self.has_dataset(name):
            raise Exception("Dataset `%s` already exists" % name)

        if data is not None:
            shape = data.shape
            dtype = data.dtype

        if chunk_size is None:
            chunk_size = shape

        chunk_grid = (np.ceil(np.asarray(shape, float) / chunk_size)).astype(int)

        log.debug("Creating Dataset `%s`", name)
        self.datasets[name] = None  # Key `name` has to exist
        dataset = MemDataset(
            self, name, shape, dtype, fillvalue, chunk_grid, chunk_size,
        )
        self.datasets[name] = dataset
        
        link = MemLink(self, dataset, name)
        self.links[name] = link
        return dataset
    
    def get_dataset(self, name):
        if not self.has_dataset(name):
            raise DatasetNotFoundError("Dataset `%s` does not exist")
        return self.datasets[name]

    def has_dataset(self, name):
        return name in self.datasets

    def del_dataset(self, name):
        if not self.has_dataset(name):
            raise DatasetNotFoundError("Dataset `%s` does not exist")
        log.debug("Removing Dataset `%s`", name)
        del self.datasets[name]
    
    def get_metadata(self):
        return self.metadata
    
    def has_metadata(self):
        if metadata:
            return self.metadata
    
    def del_metadata(self):
        return self.metadata
        
    
class MemDataset(BackendDataset):

    def __init__(self, pool, name, shape, dtype, fillvalue, chunk_grid,
                 chunk_size):
        super(MemDataset, self).__init__(pool, name, shape, dtype, fillvalue,
                                         chunk_grid, chunk_size)
        self.data_chunks = {}
        self._populate_chunks()

    def _populate_chunks(self):
        for idx in np.ndindex(*self.chunk_grid):
            self.create_chunk(idx)

    def create_chunk(self, idx, data=None, slices=None):
        if self.has_chunk(idx):
            raise Exception('DataChunk `{}{}` already exists'.format(self.name,
                                                                     idx))

        self.data_chunks[idx] = None

        chunk = MemDataChunk(self, idx, 'Chunk {}'.format(idx),
                             self.chunk_size, self.dtype, self.fillvalue)
        if data is not None:
            slices = slices or slice(None)
            chunk.set_data(data, slices=slices)

        self.data_chunks[idx] = chunk
        return chunk

    def get_chunk(self, idx):
        if self.has_chunk(idx):
            return self.data_chunks[idx]
        return self.create_chunk(idx)

    def has_chunk(self, idx):
        return idx in self.data_chunks

    def del_chunk(self, idx):
        if self.has_chunk(idx):
            del self.data_chunks[idx]
            return True
        return False


class MemDataChunk(BackendDataChunk):

    def __init__(self, dataset, idx, name, shape, dtype, fillvalue):
        super(MemDataChunk, self).__init__(dataset, idx, name, shape,
                                           dtype, fillvalue)
        self.data = np.full(shape, fillvalue, dtype)

    def get_data(self, slices=None):
        return self.data[slices]

    def set_data(self, values, slices=None):
        self.data[slices] = values


_backend = Backend('ram', MemConnection, MemDataset, MemDataChunk)
