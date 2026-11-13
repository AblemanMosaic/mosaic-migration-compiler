# Capability Layer T3 acceptance and evidence scope

The original 100 cases and 84 requirements remain unchanged. 31 cases are due in T3.
The cumulative gate may report 79 scoped passes only after actual current T1/T2/T3 execution.
The remaining 21 later cases stay NOT_RUN. Test counts alone never close them.

Every T3 case below is interpreted under the signed-fixture, trusted-local-host and SQLite simulation
boundary. Authentication is actual cryptography; real observer truth, universal coverage, production
authority, physical durability and native orchestration are not established.

| Case | Exact executable evidence |
|---|---|
| AC-AUTHORITY-01 | `test_joint_approval`, `test_policy_substitution_refused` |
| AC-AUTHORITY-02 | `test_unrecognized_signature`, `test_unrecognized_signer` |
| AC-AUTHORITY-03 | `test_one_missing_cannot_mask`, `test_denial_blocks` |
| AC-AUTHORITY-04 | `test_expiry_exact_boundary`, `test_not_before` |
| AC-AUTHORITY-05 | `test_rehashed_pass_not_evidence`, `test_report_cannot_approve` |
| AC-AUTHORITY-06 | `test_unrecognized_method`, `test_obligations_bind_method_authority`, `test_record_cannot_rewrite_audience` |
| AC-AUTHORITY-07 | `test_duplicate_signer_not_threshold`, `test_duplicate_statement_no_extra_support` |
| AC-AUTHORITY-08 | `test_negative_observation_blocks`, `test_conflicting_applicable_observations_block`, `test_same_sequence_equivocation_retained` |
| AC-AUTHORITY-09 | `test_coverage_class_required`, `test_incomplete_roster_blocks`, `test_authentic_but_false_statement_not_truth` |
| AC-AUTHORITY-10 | `test_three_steps_progress`, `test_target_change_before_commit`, `test_record_cannot_rewrite_audience` |
| AC-AUTHORITY-11 | `test_replay_recomputes`, `test_journal_replay_never_calls_adapter` |
| AC-AUTHORITY-12 | `test_success_does_not_execute`, `test_commit_without_approval_refuses`, `test_readonly_abi_refuses_effects` |
| AC-EFFECT-01 | `test_prepare_does_not_mutate_target` |
| AC-EFFECT-02 | `test_report_cannot_approve`, `test_commit_without_approval_refuses` |
| AC-EFFECT-03 | `test_target_change_before_commit`, `test_atomic_target_rechecks_preconditions`, `test_expired_request` |
| AC-EFFECT-04 | `test_duplicate_commit_is_one_effect`, `test_idempotency_collision` |
| AC-EFFECT-05 | `test_lost_ack_reconciles_without_repeating`, `test_real_subprocess_commits_effect_then_dies` |
| AC-EFFECT-06 | `test_actual_multi_target_partial`, `test_partial_outcome_is_not_no_effect` |
| AC-EFFECT-07 | `test_restart_before_approval`, `test_restart_after_approval`, `test_restart_after_commit`, `test_crash_after_intent_before_effect`, `test_crash_after_effect_before_receipt` |
| AC-EFFECT-08 | `test_journal_replay_never_calls_adapter` |
| AC-EFFECT-09 | `test_target_reservation_across_migrations`, `test_two_cooperating_controllers_do_not_double_dispatch`, `test_concurrent_head` |
| AC-EFFECT-10 | `test_retry_budget` |
| AC-EFFECT-11 | `test_cancelled_approval_not_reusable`, `test_new_evidence_invalidates_approval`, `test_duplicate_commit_is_one_effect` |
| AC-EFFECT-12 | `test_request_mutation_is_detached`, `test_wrong_adapter`, `test_target_change_before_commit` |
| AC-EFFECT-13 | `test_other_cohort_unchanged_by_compensation`, `test_compensation_blocked_by_completed_successor`, `test_compensation_preserves_other_target_and_floors` |
| AC-EFFECT-14 | `test_unbound_adapter_refused`, `test_unmodeled_effect_descriptor_refused`, `test_real_subprocess_dies_before_sqlite_commit` |
| AC-LIFECYCLE-07 | `test_missing_is_not_false`, `test_stale_is_not_zero_activity`, `test_partial_is_not_complete`, `test_stale_newer_does_not_revive_old_positive` |
| AC-LIFECYCLE-08 | `test_age_equality`, `test_uncertain_clock_crosses_expiry`, `test_clock_uncertainty_policy` |
| AC-LIFECYCLE-09 | `test_other_cohort_unchanged_by_compensation` |
| AC-LIFECYCLE-10 | `test_adapter_rejects_security_rollback`, `test_adapter_rejects_revocation_erasure`, `test_external_checkpoint_detects_database_restore` |
| AC-LIFECYCLE-12 | `test_revision_invalidates_approval` |

## Specific exclusions

T3 coverage means recognized testimony over the modeled roster, not discovered completeness.
Targeted rollback requires a new signed request and preserves security state. The limited inverse
adapter supports declared restore-prior-state, not arbitrary distributed compensation. Partial target
outcomes remain RECOVERY_REQUIRED and locked. The sequential selected planner witness is executable;
atomic multi-transition phases refuse until a qualified adapter exists. No production retirement is
performed. The seven small workflows are not the complete T5 end-to-end qualification.

The 19 requirement links are mechanical code/test correspondence, not proof of complete semantics.
