"""
=================================
Schema (:mod:`data_tools.schema`)
=================================

Schema is a module which composes a set of classes and objects
to abstractly construct a filesystem-like API

File API
========

.. autosummary::
   :toctree: generated/

   File             -- Atomic unit of data
   CanonicalPath    -- Represent a location in an abstract filesystem
   FileType         -- Discretize different file types


Data Handling
=============

.. autosummary::
   :toctree: generated/

   Result           -- Algebraic datatype that can either represent a successful result of some operation, or a failure.
   UnwrappedError   -- Error arising from unwrapping a ``Result`` which contains a failure


DataSource API
==============

.. autosummary::
   :toctree: generated/

   DataSource      -- Abstract interface for storing and acquiring data
   FileLoader      -- A useful callable mapping to a stored File in an abstract filesystem
   Event           -- A named time range

"""


from ._event import (
    Event
)

from ._result import (
    UnwrappedError,
    Result
)

from ._file import (
    FileType,
    File,
    CanonicalPath
)

from ._file_loader import (
    FileLoader
)

from ._data_source import (
    DataSource
)

__all__ = [
    "DataSource",
    "File",
    "FileType",
    "FileLoader",
    "CanonicalPath",
    "Result",
    "UnwrappedError",
    "Event"
]
