"""SAS Lineage: column-level provenance extraction from a SAS estate."""

from importlib.metadata import PackageNotFoundError, version

# Single source of truth: the installed package version (cz bumps pyproject),
# so provenance.json's parser_version always matches the released build.
try:
    __version__ = version("wraith-sas-lineage")
except PackageNotFoundError:
    __version__ = "0.0.0.dev0"
