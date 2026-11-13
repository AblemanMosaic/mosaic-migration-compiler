# Capability Layer T2 acceptance reconciliation

All original 100 case identities/oracles and the 84 requirements remain frozen. Due in Capability Layer T2: 19.
T1 29 cases are replayed; after scoped T2 qualification the remaining 52 retain NOT_RUN.
Passes below establish declared-model behavior, not observation authentication or live enforcement.

| Case | Evidence test | Claim ceiling |
|---|---|---|
| AC-PROFILE-01 | `tests_t2.test_profiles.ProfileAcceptance.test_ac_profile_01` | Supplied-model predicate; authority/effects remain external |
| AC-PROFILE-02 | `tests_t2.test_profiles.ProfileAcceptance.test_ac_profile_02` | Supplied-model predicate; authority/effects remain external |
| AC-PROFILE-03 | `tests_t2.test_profiles.ProfileAcceptance.test_ac_profile_03` | Supplied-model predicate; authority/effects remain external |
| AC-PROFILE-04 | `tests_t2.test_profiles.ProfileAcceptance.test_ac_profile_04` | Supplied-model predicate; authority/effects remain external |
| AC-PROFILE-05 | `tests_t2.test_profiles.ProfileAcceptance.test_ac_profile_05` | Supplied-model predicate; authority/effects remain external |
| AC-PROFILE-06 | `tests_t2.test_profiles.ProfileAcceptance.test_ac_profile_06` | Supplied-model predicate; authority/effects remain external |
| AC-PROFILE-07 | `tests_t2.test_profiles.ProfileAcceptance.test_ac_profile_07` | Supplied-model predicate; authority/effects remain external |
| AC-PROFILE-08 | `tests_t2.test_profiles.ProfileAcceptance.test_ac_profile_08` | Supplied-model predicate; authority/effects remain external |
| AC-PROFILE-09 | `tests_t2.test_planner.PlannerAcceptance.test_ac_profile_09` | Supplied-model predicate; authority/effects remain external |
| AC-PROFILE-10 | `tests_t2.test_planner.PlannerAcceptance.test_ac_profile_10` | Supplied-model predicate; authority/effects remain external |
| AC-PROFILE-11 | `tests_t2.test_planner.PlannerAcceptance.test_ac_profile_11` | Supplied-model predicate; authority/effects remain external |
| AC-PROFILE-12 | `tests_t2.test_profiles.ProfileAcceptance.test_ac_profile_12` | Supplied-model predicate; authority/effects remain external |
| AC-LIFECYCLE-01 | `tests_t2.test_lifecycle.LifecycleAcceptance.test_ac_lifecycle_01` | Supplied-model predicate; authority/effects remain external |
| AC-LIFECYCLE-02 | `tests_t2.test_lifecycle.LifecycleAcceptance.test_ac_lifecycle_02` | Supplied-model predicate; authority/effects remain external |
| AC-LIFECYCLE-03 | `tests_t2.test_lifecycle.LifecycleAcceptance.test_ac_lifecycle_03` | Supplied-model predicate; authority/effects remain external |
| AC-LIFECYCLE-04 | `tests_t2.test_lifecycle.LifecycleAcceptance.test_ac_lifecycle_04` | Supplied-model predicate; authority/effects remain external |
| AC-LIFECYCLE-05 | `tests_t2.test_lifecycle.LifecycleAcceptance.test_ac_lifecycle_05` | Supplied-model predicate; authority/effects remain external |
| AC-LIFECYCLE-06 | `tests_t2.test_lifecycle.LifecycleAcceptance.test_ac_lifecycle_06` | Supplied-model predicate; authority/effects remain external |
| AC-LIFECYCLE-11 | `tests_t2.test_lifecycle.LifecycleAcceptance.test_ac_lifecycle_11` | Supplied-model predicate; authority/effects remain external |

## Requirement mapping limits

W03: exact finite issuer/token, inventory, permission and worker predicates are realized. Real
custody, cryptographic token verification, domain-complete transformation languages and observations
are not. W04: one deterministic finite witness, with at most 16 transitions / 8192 visited states;
not an optimizer or proof outside the supplied model. W05: explicit proposed edges, exact routes
and scoped supplied-state retirement conditions. Runtime freshness/approval/recovery evidence
remains T3. T2 tests of numeric age/floor checks do not close those T3 cases.

Full live end-to-end gates AC-E2E-* are due T5 and are NOT_RUN. T2 executable examples compose
actual kernel/profile functions but do not constitute live end-to-end migration evidence.
