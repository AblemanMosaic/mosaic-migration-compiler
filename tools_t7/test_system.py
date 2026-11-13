"""Canonical MMC test topology and profile-aware lane planning."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

from mosaic_mmc import canonical
from mosaic_mmc.errors import require
from tools.common import source_snapshot

CONTRACT_PATH = ROOT / "profiles/TEST-SYSTEM.json"
REGISTRY_PATH = ROOT / "provenance/turn7/TEST-REGISTRY.json"
PATH_ENVIRONMENT = {
    "MMC_QUALIFICATION_DEPENDENCY_BUNDLE",
    "MMC_QUALIFICATION_CMBA_A4_WHEEL",
    "MMC_QUALIFICATION_CMBA_A7_WHEEL",
    "MMC_QUALIFICATION_DKN_RC5_WHEEL",
    "MMC_UCM_R038_SOURCE",
}


def rooted(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def flattened(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flattened(item)
        else:
            yield item


def contract() -> dict:
    value = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    require(value.get("schema") == "mosaic.mmc.test-system.v0.1", "MMC_TEST_SYSTEM_SCHEMA")
    groups = value.get("groups")
    require(isinstance(groups, list) and [row.get("id") for row in groups] ==
            ["t1", "t2", "t3", "t4", "t5", "t6", "t7"], "MMC_TEST_SYSTEM_GROUPS")
    require([row.get("name") for row in groups[:6]] ==
            [f"CAPABILITY_LAYER_{index}" for index in range(1, 7)] and
            groups[6].get("name") == "RELEASE_CONVERGENCE", "MMC_TEST_SYSTEM_NAMES")
    artifact_checks=value.get("artifact_checks")
    require(artifact_checks==[{
        "id": "installed-wheel-ci",
        "purpose": "PROVE_INSTALLED_MODULE_ORIGIN_PROTOCOL_CONFORMANCE_AND_DISPOSABLE_MIGRATION_OUTSIDE_SOURCE",
        "entry_point": "mmc-installed-ci",
        "platforms": ["LINUX_X86_64", "WINDOWS_X86_64"],
        "effect_class": "DISPOSABLE_TEMPORARY_SQLITE_AND_CHILD_PROCESSES_ONLY",
        "release_qualifying": False,
    }],"MMC_TEST_SYSTEM_ARTIFACT_CHECKS")
    profile = value["discovery_profile"]
    lanes = value.get("lanes")
    require(isinstance(lanes, list) and len({row.get("id") for row in lanes}) == len(lanes),
            "MMC_TEST_SYSTEM_LANES")
    for lane in lanes:
        require(lane.get("execution_profile", profile["id"])
                in {profile["id"], "PUBLIC_CI_QUALIFICATION_EXTRA_FROM_PYPI"},
                "MMC_TEST_SYSTEM_EXECUTION_PROFILE", str(lane.get("id")))
    return value


def groups() -> dict[str, str]:
    return {row["id"]: row["directory"] for row in contract()["groups"]}


def validate_discovery_profile(environment: dict[str, str] | None = None) -> dict:
    environment = os.environ if environment is None else environment
    profile = contract()["discovery_profile"]
    missing = []
    invalid_paths = []
    for name in profile["required_environment"]:
        value = environment.get(name)
        if not isinstance(value, str) or not value:
            missing.append(name)
        elif name in PATH_ENVIRONMENT and not Path(value).exists():
            invalid_paths.append(name)
    require(not missing, "MMC_TEST_DISCOVERY_PROFILE_MISSING", detail=",".join(sorted(missing)))
    require(not invalid_paths, "MMC_TEST_DISCOVERY_PROFILE_PATH", detail=",".join(sorted(invalid_paths)))
    return {
        "schema": "mosaic.mmc.test-discovery-profile.v0.1",
        "profile_id": profile["id"],
        "required_environment": profile["required_environment"],
        "status": "PASS_EXACT_DISCOVERY_PROFILE_PRESENT",
        "authority_effect": "NONE",
    }


def discover() -> dict[str, list[str]]:
    validate_discovery_profile()
    discovered = {}
    for name, directory in groups().items():
        suite = unittest.defaultTestLoader.discover(str(ROOT / directory), top_level_dir=str(ROOT))
        ids = sorted(case.id() for case in flattened(suite))
        require(ids and len(ids) == len(set(ids)) and not any("_FailedTest" in value for value in ids),
                "MMC_TEST_SYSTEM_DISCOVERY", name)
        discovered[name] = ids
    return discovered


def plan(lane_id: str, expected_source: str) -> dict:
    snapshot = source_snapshot(ROOT)
    require(snapshot["root"] == expected_source, "MMC_TEST_SYSTEM_SOURCE_PIN")
    topology = contract()
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    lane = next((row for row in topology["lanes"] if row["id"] == lane_id), None)
    require(lane is not None, "MMC_TEST_SYSTEM_LANE", lane_id)
    selections = {}
    for group, prefixes in lane["selectors"].items():
        require(group in registry["groups"] and isinstance(prefixes, list) and prefixes,
                "MMC_TEST_SYSTEM_SELECTOR", group)
        admitted = registry["groups"][group]
        selected = list(admitted) if prefixes == ["*"] else [
            test_id for test_id in admitted if any(test_id.startswith(prefix) for prefix in prefixes)
        ]
        require(selected, "MMC_TEST_SYSTEM_EMPTY_SELECTOR", group)
        selections[group] = selected
    body = {
        "schema": "mosaic.mmc.test-plan.v0.1",
        "lane": lane_id,
        "purpose": lane["purpose"],
        "cost_class": lane["cost_class"],
        "effect_class": lane["effect_class"],
        "execution_profile": lane.get("execution_profile", topology["discovery_profile"]["id"]),
        "admitted_nonpasses": lane.get("admitted_nonpasses", {}),
        "source_root": expected_source,
        "discovery_profile": topology["discovery_profile"]["id"],
        "selections": selections,
        "counts": {name: len(ids) for name, ids in selections.items()},
        "total": sum(len(ids) for ids in selections.values()),
        "release_qualifying": lane_id == "full",
        "authority_effect": "NONE",
    }
    return {**body, "plan_root": rooted(body)}


def resolve_source_pin(lane_id: str, expected_source: str | None, self_pin: bool) -> tuple[str, str]:
    require(bool(expected_source) != self_pin, "MMC_TEST_SYSTEM_SOURCE_PIN_MODE")
    if self_pin:
        require(lane_id != "full", "MMC_TEST_SYSTEM_FULL_REQUIRES_EXTERNAL_SOURCE_PIN")
        return source_snapshot(ROOT)["root"], "SELF_OBSERVED_DIAGNOSTIC"
    return str(expected_source), "EXTERNAL_EXPECTED_SOURCE"
