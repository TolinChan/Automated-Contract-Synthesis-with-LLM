# Hard Candidate Screening

Static, model-free screening of hard benchmark candidates.

| tier | id | score | screen_passed | selected | features | reject_reasons | selection_note |
|---|---:|---:|---|---|---|---|---|
| primary | `reconfiguration_reconfigure` | 15 | true | true | old, global_resource, resource_mutation, ensures=4, verify_duration_estimate=600 |  | selected_for_hard_expansion_v1 |
| primary | `stake_update_stake_pool` | 14 | true | true | global_resource, quantifier, resource_mutation, ensures=3, verify_duration_estimate=300 |  | selected_for_hard_expansion_v1 |
| primary | `stake_append` | 11 | true | true | old, quantifier, loop_or_vector, ensures=4 |  | selected_for_hard_expansion_v1 |
| primary | `stake_remove_validators` | 7 | true | true | global_resource, loop_or_vector, resource_mutation |  | selected_for_hard_expansion_v1 |
| primary | `stake_distribute_rewards` | 6 | true | true | old, ensures=4 |  | selected_for_hard_expansion_v1 |
| primary | `coin_mint_internal` | 13 | true | true | modifies, old, global_resource, quantifier, resource_mutation, ensures=2 |  | selected_for_hard_expansion_v1 |
| primary | `storage_gas_on_reconfig` | 7 | true | true | quantifier, resource_mutation, aborts_if=3 |  | selected_for_hard_expansion_v1 |
| primary | `stake_next_validator_consensus_infos` | 10 | true | true | quantifier, loop_or_vector, verify_duration_estimate=300 |  | selected_for_hard_expansion_v1 |
| primary | `fungible_asset_unchecked_withdraw` | 5 | true | true | modifies, global_resource |  | selected_for_hard_expansion_v1 |
| primary | `fungible_asset_unchecked_deposit` | 5 | true | true | modifies, global_resource |  | selected_for_hard_expansion_v1 |
| primary | `block_block_prologue_common` | 7 | true | true | resource_mutation, verify_duration_estimate=1000 |  | selected_for_hard_expansion_v1 |
| primary | `block_emit_new_block_event` | 4 | true | true | quantifier, resource_mutation |  | selected_for_hard_expansion_v1 |
| backup | `block_emit_genesis_block_event` | 7 | true | false | global_resource, loop_or_vector, resource_mutation |  | backup_passed_not_needed |
| backup | `aggregator_v2_string_concat` | 0 | false | false |  | extract_error:ValueError:function 'string_concat' not found | rejected |
| backup | `aggregator_v2_copy_snapshot` | 0 | false | false |  | extract_error:ValueError:function 'copy_snapshot' not found | rejected |
| backup | `genesis_create_initialize_validators` | 6 | true | false | loop_or_vector, verify_duration_estimate=120 |  | backup_passed_not_needed |
| backup | `object_grant_permission` | 3 | false | false | aborts_if=3 | fewer_than_two_static_feature_classes | rejected |
