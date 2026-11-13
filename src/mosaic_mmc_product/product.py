"""Current product inventory without changing the versioned T1-T6 ABIs."""
from __future__ import annotations

from copy import deepcopy
import importlib.resources as resources

from mosaic_mmc import decode

VERSION = "0.1.0a9"
REVISION = "RELEASE-CONVERGENCE-r013"


def _pins() -> dict:
    return decode(resources.files("mosaic_mmc_product").joinpath("data", "integrations.json").read_bytes())


def capabilities() -> dict:
    return {
        "schema": "mmc.product-capabilities.v1",
        "distribution": "mosaic-migration-compiler",
        "version": VERSION,
        "revision": REVISION,
        "interfaces": {
            "current": "mmc-product",
            "operation_catalogue": "mmc-product protocol",
            "schema_export": "mmc-product schema all",
            "uniform_request": "mmc-product request REQUEST.json",
            "adapter_transport": "mmc-product transport",
            "target_qualification": "mmc-product verify-target-migration",
            "compatibility": ["mmc", "mmc-t2", "mmc-t3", "mmc-agent", "mmc-foundry"],
        },
        "agent_surface": "47_OPERATIONS_THROUGH_MMC_AGENT_V1_UNIFORM_REQUEST_RESPONSE",
        "uniform_effect_abi": "MMC_EFFECT_ADAPTER_PYTHON_V1_HOST_SELECTED",
        "adapter_transport": "mmc.adapter-transport.v1",
        "adapter_authentication": "PRIVATE_PIPE_HMAC_SHA256_MUTUAL_CHALLENGE",
        "offline_dependency_profile": "NATIVE_CPYTHON_312_HASH_LOCKED_QUALIFICATION_BUNDLES",
        "binary_abi": "NOT_DEFINED",
        "subsystems": [
            {"id": "MODEL_COMPILER", "package": "mosaic_mmc", "status": "IMPLEMENTED", "effects": "NONE"},
            {"id": "DOMAIN_PLANNER_RETIREMENT", "package": "mosaic_mmc_t2", "status": "IMPLEMENTED", "effects": "NONE"},
            {"id": "CONTROLLER_EVIDENCE_RECOVERY", "package": "mosaic_mmc_t3", "status": "IMPLEMENTED_WITH_EXPLICIT_ADAPTER_ABI", "effects": "HOST_SELECTED_LOCAL_ADAPTER"},
            {"id": "AGENT_WORKBENCH_SDK", "package": "mosaic_mmc_t4", "status": "IMPLEMENTED", "effects": "BOUNDED_HOST_SELECTED"},
            {"id": "FINITE_QUALIFICATION_FOUNDRY", "package": "mosaic_mmc_t5", "status": "IMPLEMENTED", "effects": "LOCAL_SIMULATION_ONLY"},
            {"id": "CURRENT_INTEGRATION_CONFORMANCE", "package": "mosaic_mmc_product", "status": "IMPLEMENTED_EXECUTED_PATHS", "effects": "READ_ONLY_AND_TEMPORARY_JOURNAL"},
            {"id": "DISPOSABLE_REAL_MIGRATION", "package": "mosaic_mmc_product", "status": "NATIVE_CONTROLLER_MIGRATION_RECOVERY_RETIREMENT_VERIFIED", "effects": "TEMPORARY_SQLITE_AND_CHILD_PROCESS"},
            {"id": "ENROLLED_SQLITE_TARGET", "package": "mosaic_mmc_product", "status": "IMPLEMENTED_WITH_AUTHENTICATED_PROCESS_TRANSPORT", "effects": "HOST_ENROLLED_SQLITE_TABLES"},
        ],
        "model_coverage": [
            "PERSISTED_DATA", "PRODUCERS", "CONSUMERS", "DEPENDENCY_ORDER",
            "COEXISTENCE", "COHORTS", "USE_CASES", "UNCERTAINTY", "EVIDENCE",
            "RETIREMENT_GATES", "TARGETED_ROLLBACK", "POINT_OF_EFFECT_RECHECK",
            "RECONCILIATION",
        ],
        "production_effect_adapter": "NOT_SHIPPED",
        "native_identity_binding": "UNBOUND",
        "public_release": "APACHE_2_0_SOURCE_AND_DKN_ENDORSED_ASSETS_AUTHORIZED_FOR_PUBLICATION",
        "independent_study": "NOT_PERFORMED",
        "authority_effect": "NONE",
    }


def integration_status() -> dict:
    pins = _pins()
    return {
        "schema": "mmc.integration-status.v1",
        "version": VERSION,
        "integrations": deepcopy(pins["integrations"]),
        "dependency_graph": deepcopy(pins["dependency_graph"]),
        "native_semantic_authority": "MMC_NATIVE",
        "effect_executor": "MMC_NATIVE_CONTROLLER",
        "ucm_role": "SHADOW_GOVERNANCE_AND_CONFORMANCE",
        "authority_effect": "NONE",
    }
