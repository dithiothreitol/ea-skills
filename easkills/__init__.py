"""Deterministic tooling behind the EA skills pipeline.

The skills supply judgement; this package supplies proof. Every rule enforced here
is decided by vendored primary-source data (the ArchiMate 3.2 relationship matrix
and the Open Group exchange schemas), never by a language model.
"""

__all__ = ["oracle", "dsl", "genschema", "validate", "aoef", "cli"]
__version__ = "0.1.0"
