find_package(GTest CONFIG REQUIRED)

set(SYNC_FIXTURES_DIR "${CMAKE_CURRENT_SOURCE_DIR}/fixtures")
set(SYNC_GREP_GATE_SCRIPT
  "${CMAKE_SOURCE_DIR}/tools/check_no_std_mutex_in_awaitable_headers.sh")

function(async_mutex_apply_test_warnings target)
  if(NOT ASYNC_MUTEX_WERROR)
    return()
  endif()

  # Opt-in only (ASYNC_MUTEX_WERROR default OFF; not enabled by any preset). The
  # origin never applied -Werror to its sync tests, and this vendored suite is not
  # warning-clean under it (gtest's EXPECT_THROW discards the [[nodiscard]] result
  # of slot_allocator::allocate → -Wunused-result; unused static helpers → with
  # -Wall). Kept as -Werror-only (no -Wall/-Wextra) for anyone who opts in.
  if(MSVC)
    target_compile_options(${target} PRIVATE /WX)
  else()
    target_compile_options(${target} PRIVATE -Werror)
  endif()
endfunction()

function(add_sync_test name)
  add_executable(${name} ${ARGN})
  target_link_libraries(${name} PRIVATE
    catseraf::async_mutex
    GTest::gtest
    GTest::gtest_main
  )
  target_include_directories(${name} PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}"
    "${SYNC_FIXTURES_DIR}"
  )
  async_mutex_apply_test_warnings(${name})
  add_test(NAME ${name} COMMAND ${name})
  set_tests_properties(${name} PROPERTIES
    ENVIRONMENT "SYNC_FIXTURES_DIR=${SYNC_FIXTURES_DIR};SYNC_GREP_GATE_SCRIPT=${SYNC_GREP_GATE_SCRIPT}"
  )
endfunction()

add_sync_test(sync_uncontended_latency test_uncontended_latency.cpp)
add_sync_test(sync_contended_latency test_contended_latency.cpp)
add_sync_test(sync_fifo_fairness test_fifo_fairness.cpp)
add_sync_test(sync_fifo_across_cycles test_fifo_across_cycles.cpp)
add_sync_test(sync_contention_stress test_contention_stress.cpp)
add_sync_test(sync_async_mutex_mt_hammer test_async_mutex_mt_hammer.cpp)
set_tests_properties(sync_async_mutex_mt_hammer PROPERTIES TIMEOUT 120)
if(ASYNC_MUTEX_ENABLE_COVERAGE)
  target_compile_definitions(sync_async_mutex_mt_hammer PRIVATE
    CATSERAF_ASYNC_MUTEX_MT_HAMMER_COVERAGE_BURST
  )
  set_tests_properties(sync_async_mutex_mt_hammer PROPERTIES TIMEOUT 300)
endif()
add_sync_test(sync_executor_compat test_executor_compat.cpp)
add_sync_test(sync_dispatch_vs_post test_dispatch_vs_post.cpp)
add_sync_test(sync_cross_strand_acquire test_cross_strand_acquire.cpp)
add_sync_test(sync_guard_destructive_move test_guard_destructive_move.cpp)
add_sync_test(sync_unlock_reaper_splice test_unlock_reaper_splice.cpp)
add_sync_test(sync_result_write_race test_result_write_race.cpp)

add_sync_test(sync_cancellation_mid_wait test_cancellation_mid_wait.cpp)
add_sync_test(sync_race_cancel_pre_drain test_race_cancel_pre_drain.cpp)
add_sync_test(sync_race_multi_cancel test_race_multi_cancel.cpp)
add_sync_test(sync_race_cancel_during_resume test_race_cancel_during_resume.cpp)
add_sync_test(sync_residual_cancel_graceful test_residual_cancel_graceful.cpp)

add_sync_test(sync_tsan_clean test_tsan_clean.cpp)
add_sync_test(sync_asan_clean test_asan_clean.cpp)
add_sync_test(sync_halo_firing test_halo_firing.cpp)
add_sync_test(sync_pmr_fallback test_pmr_fallback.cpp)
add_sync_test(sync_slot_allocator_storage test_slot_allocator_storage.cpp)

add_sync_test(sync_destructor_release_death test_destructor_release_death.cpp)
add_sync_test(sync_drain_destroy_inflight_mt test_drain_destroy_inflight_mt.cpp)
add_sync_test(sync_cancel_and_drain test_cancel_and_drain.cpp)
add_sync_test(sync_cancel_and_drain_concurrent test_cancel_and_drain_concurrent.cpp)
add_sync_test(sync_drain_latch_holder_lifecycle test_drain_latch_holder_lifecycle.cpp)
add_sync_test(sync_in_flight_acquirer_coverage test_in_flight_acquirer_coverage.cpp)
add_sync_test(sync_drain_awaitable_cancellation test_drain_awaitable_cancellation.cpp)

add_sync_test(sync_drain_strand_local_reap test_drain_strand_local_reap.cpp)
add_sync_test(sync_drain_immediate_destroy test_drain_immediate_destroy_after_reap.cpp)
add_sync_test(sync_drain_reentrant_during_active test_drain_reentrant_during_active.cpp)
add_sync_test(sync_drain_onstrand_cancel test_drain_onstrand_cancel_during_reap.cpp)
add_sync_test(sync_drain_predrain_holder test_drain_predrain_holder.cpp)
add_sync_test(sync_async_mutex_layout_golden test_async_mutex_layout_golden.cpp)

add_sync_test(sync_arm64_weak_memory test_arm64_weak_memory.cpp)
set_tests_properties(sync_arm64_weak_memory PROPERTIES TIMEOUT 120)
add_sync_test(sync_consumer_contract_compile test_consumer_contract_compile.cpp)

add_sync_test(sync_async_mutex_aba_interleave test_async_mutex_aba_interleave.cpp)
target_compile_definitions(sync_async_mutex_aba_interleave PRIVATE CATSERAF_ASYNC_MUTEX_TEST_SEAM)

add_sync_test(sync_async_mutex_terminal_cas_recursive_unlock test_async_mutex_terminal_cas_recursive_unlock.cpp)
target_compile_definitions(sync_async_mutex_terminal_cas_recursive_unlock PRIVATE CATSERAF_ASYNC_MUTEX_TEST_SEAM)

add_sync_test(sync_async_mutex_chain_walk_cas_loss test_async_mutex_chain_walk_cas_loss.cpp)
target_compile_definitions(sync_async_mutex_chain_walk_cas_loss PRIVATE CATSERAF_ASYNC_MUTEX_TEST_SEAM)

add_sync_test(sync_async_mutex_acquire_livelock test_async_mutex_acquire_livelock.cpp)
target_compile_definitions(sync_async_mutex_acquire_livelock PRIVATE CATSERAF_ASYNC_MUTEX_TEST_SEAM)

add_sync_test(sync_pool_exhaustion_reuse test_pool_exhaustion_reuse.cpp)
target_compile_definitions(sync_pool_exhaustion_reuse PRIVATE CATSERAF_ASYNC_MUTEX_TEST_SEAM)

add_sync_test(sync_am_p3_impossible_state_traps test_am_p3_impossible_state_traps.cpp)
target_compile_definitions(sync_am_p3_impossible_state_traps PRIVATE CATSERAF_ASYNC_MUTEX_TEST_SEAM)

add_sync_test(sync_async_mutex_mt_hammer_seam test_async_mutex_mt_hammer.cpp)
target_compile_definitions(sync_async_mutex_mt_hammer_seam PRIVATE CATSERAF_ASYNC_MUTEX_TEST_SEAM)
set_tests_properties(sync_async_mutex_mt_hammer_seam PROPERTIES TIMEOUT 300)

if(NOT WIN32)
  # CXX=${CMAKE_CXX_COMPILER}: the gate must preprocess with the project's build
  # compiler, not PATH `clang++` (AppleClang on macOS rejects -std=c++23). Passed
  # via the test environment; the script honors $CXX and std::system() inherits it.
  add_sync_test(sync_no_std_mutex_ci_gate test_no_std_mutex_ci_gate.cpp)
  set_tests_properties(sync_no_std_mutex_ci_gate PROPERTIES
    ENVIRONMENT
      "CXX=${CMAKE_CXX_COMPILER};SYNC_GREP_GATE_SCRIPT=${SYNC_GREP_GATE_SCRIPT};SYNC_FIXTURES_DIR=${SYNC_FIXTURES_DIR};SYNC_GATE_INC=${CMAKE_SOURCE_DIR}/include;SYNC_ASIO_INC=$<TARGET_PROPERTY:asio::asio,INTERFACE_INCLUDE_DIRECTORIES>"
  )

  add_test(NAME check_no_std_mutex_corpus
    COMMAND bash "${SYNC_GREP_GATE_SCRIPT}"
      -I "${CMAKE_SOURCE_DIR}/include"
      -I "$<TARGET_PROPERTY:asio::asio,INTERFACE_INCLUDE_DIRECTORIES>"
      --require-awaitable-marker
      --
      "${CMAKE_SOURCE_DIR}/include/catseraf/sync/async_mutex.hpp"
  )
  set_tests_properties(check_no_std_mutex_corpus PROPERTIES
    ENVIRONMENT "CXX=${CMAKE_CXX_COMPILER}")
endif()
