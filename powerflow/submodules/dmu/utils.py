# Copyright (c) 2022 Manuel Pitz, RWTH Aachen University
#
# Licensed under the Apache License, Version 2.0, <LICENSE-APACHE or
# http://apache.org/licenses/LICENSE-2.0> or the MIT license <LICENSE-MIT or
# http://opensource.org/licenses/MIT>, at your option. This file may not be
# copied, modified, or distributed except according to those terms.

import copy

def varargsToList(*args):
    ''' Converts a list of arguments to a list.'''
    if isinstance(args, tuple):
        if len(args) == 1:
            if isinstance(args[0], list):
                return copy.deepcopy(args[0])
            elif isinstance(args[0], tuple):
                return copy.deepcopy(list(args[0]))
            else:
                return copy.deepcopy([args[0]])
        elif len(args) > 1:
            return copy.deepcopy(list(args))
    return []

def handleListArguments(name,*args):
    ''' handles cases of lists and values as arguements '''

    if isinstance(name,list):
        return str(name[0]), copy.deepcopy(name[1:])
        # name is a list
    # if we pass only a list, instead of a single name and than comma sperated args, extract the first element as the name

    return str(name), varargsToList(*args)