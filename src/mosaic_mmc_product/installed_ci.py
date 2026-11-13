"""Installed-wheel qualification entry point used by public CI.

This module intentionally runs outside a source checkout.  It proves module
origin, protocol conformance, and one complete disposable migration using only
the installed distribution plus its declared qualification dependencies.
"""
from __future__ import annotations

import argparse
import importlib
from importlib.metadata import distribution
from pathlib import Path

from mosaic_mmc import canonical
from mosaic_mmc.errors import require
from . import capabilities
from .conformance import run_conformance
from .disposable import run_disposable_migration


MODULES=(
    'mosaic_mmc','mosaic_mmc_t2','mosaic_mmc_t3','mosaic_mmc_t4',
    'mosaic_mmc_t5','mosaic_mmc_product','mosaic_mmc_workbench',
)


def installed_origins(forbid_root=None):
    forbidden=Path(forbid_root).resolve() if forbid_root else None
    rows=[]
    for name in MODULES:
        module=importlib.import_module(name)
        origin=Path(module.__file__).resolve()
        require(origin.is_file(),'MMC_INSTALLED_CI_ORIGIN',detail=name)
        if forbidden is not None:
            require(not origin.is_relative_to(forbidden),'MMC_INSTALLED_CI_SOURCE_IMPORT',detail=name)
        rows.append({'module':name,'origin_status':'FILE_OUTSIDE_FORBIDDEN_SOURCE'
                     if forbidden is not None else 'MODULE_FILE_VERIFIED'})
    return rows


def run(forbid_root=None):
    origins=installed_origins(forbid_root)
    dist=distribution('mosaic-migration-compiler')
    conformance=run_conformance()
    migration=run_disposable_migration()
    product=capabilities()
    require(conformance['status']=='PASS_PROTOCOL_CONFORMANCE','MMC_INSTALLED_CI_CONFORMANCE')
    require(migration['status']=='PASS_NATIVE_CONTROLLER_DISPOSABLE_MIGRATION_RETIREMENT_RECOVERY',
            'MMC_INSTALLED_CI_MIGRATION')
    require(product['version']==dist.version,'MMC_INSTALLED_CI_VERSION')
    body={'schema':'mmc.installed-wheel-ci.v1','status':'PASS_INSTALLED_WHEEL_CI',
          'distribution':'mosaic-migration-compiler','version':dist.version,
          'module_origins':origins,'protocol_case_count':conformance['case_count'],
          'migration_receipt_root':migration['receipt_root'],
          'effects':'DISPOSABLE_TEMPORARY_SQLITE_AND_CHILD_PROCESSES_ONLY',
          'authority_effect':'NONE'}
    return {**body,'root':__import__('hashlib').sha256(canonical(body)).hexdigest()}


def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--forbid-root')
    args=parser.parse_args(argv)
    print(canonical(run(args.forbid_root)).decode('utf-8'))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
