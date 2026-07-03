# Known flake — libc++ TSAN heap-reuse false positive on the seam ABA tests

This document records a **known, intermittent ThreadSanitizer false positive** that
affects three tests **only under the libc++ TSAN lane** (`linux-clang-libc++-tsan`).
It is persisted here so that a future failure of this exact shape is recognized as a
toolchain artifact — **not** a data race in `async_mutex` — and is not "fixed" by
rewriting the tests' synchronization. No code, test, or CI change was made in
response to it (deliberate — see *Decision* below).

## Affected tests

All three are `CATSERAF_ASYNC_MUTEX_TEST_SEAM` tests that deliberately provoke
ABA / CAS-loss interleavings by running a second `io_context` on a background
`std::thread` and coordinating via `asio::co_spawn(..., asio::use_future)`:

- `sync_async_mutex_aba_interleave` (`AsyncMutexAbaInterleave.PopPreCasAbaCorruptionDetected`)
- `sync_async_mutex_terminal_cas_recursive_unlock` (`...F6FifoExhaustedTerminalCasFailGrantsWaiter`)
- `sync_async_mutex_chain_walk_cas_loss` (`...ResidualWalkCancelWinsGrantCasLoss`)

## Symptom

Under `linux-clang-libc++-tsan`, occasionally:

```
WARNING: ThreadSanitizer: data race
  Write of size 8 at 0x7220000000XX by thread T3:
    #0 operator delete(void*, unsigned long)
    ...
    #4 std::promise<void>::~promise()
    #11 asio::detail::promise_executor<...>::~promise_executor()   use_future.hpp:108
    #13 asio::detail::co_spawn_state<...>::~co_spawn_state()       co_spawn.hpp:76
    ...  (asio use_future teardown on the worker thread)
  Previous atomic read of size 1 at 0x7220000000XX by main thread:
    #0 pthread_mutex_lock
    #1 std::__1::mutex::lock()
    #2 testing::internal::HandleSehExceptionsInMethodIfSupported<testing::Test,...>  gtest.cc:2664
    #4 testing::Test::Run()
    ...  #12 main
SUMMARY: ThreadSanitizer: data race ... in operator delete(void*, unsigned long)
```

The gtest test body itself **passes** — `[ OK ]` / `[ PASSED ]` are printed. What
fails the lane is TSAN's warning plus its nonzero exit code, which `ctest` surfaces
as a failed test.

## Why it is a false positive (not an `async_mutex` race)

1. **The two "conflicting" accesses are unrelated objects at a recycled address.**
   The write is asio freeing the `use_future` `std::promise<void>` shared state
   (`__assoc_sub_state`) on the worker thread during `co_spawn` teardown. The
   "previous read" stack is **gtest's own framework `std::mutex`**
   (`std::mutex::lock()` inside `testing::Test::Run()` — `gtest.cc:2664`), not the
   test's data and not `future::get()`. The gtest mutex was freed earlier and the
   promise state was later allocated at the same heap address; TSAN's stale shadow
   across that alloc-reuse boundary flags a race between two objects that never
   coexisted. Note the address is a low `0x7220000000XX` value from TSAN's own heap
   region, and it **differs per test** (`…218`, `…018`), consistent with allocator
   reuse rather than a fixed shared datum.

2. **libc++-only.** The identical commit passes `linux-clang-tsan` (libstdc++) —
   e.g. commit `ab43884` failed `linux-clang-libc++-tsan` but its `linux-clang-tsan`
   run was green. A genuine race in the header would fire under both standard
   libraries.

3. **Flaky, and independent of the mutex code.** It first surfaced on a
   **docs-only** commit (`ab43884`, a README edit) while the immediately preceding
   commit (`830ee2e`) passed the same lane. The `async_mutex.hpp` header is
   byte-identical across those commits.

4. **Not locally reproducible.** ~540 runs of the three tests under the local
   `linux-clang-libc++-tsan` build (serial, and concurrently under memory/scheduler
   pressure) produced zero warnings.

## Decision

**Do nothing in the code / tests / CI.** These tests retain full ThreadSanitizer
coverage via the `linux-clang-tsan` (libstdc++) lane, which is reliably green, plus
ASAN/UBSAN and the non-sanitized lanes. Options considered and declined:

- *Exclude the three tests from the libc++-TSAN lane* — loses libc++-flavored TSAN
  on exactly these teardown paths for a false positive.
- *TSAN suppressions file* (e.g. `race:asio::detail::promise_executor::~promise_executor`)
  — can mask a genuine future regression in that path and cannot be validated
  locally (the artifact won't reproduce).
- *`ctest --repeat until-pass:2`* — blanket-masks flakiness beyond this artifact.

If the libc++-TSAN lane trips on one of these three tests with the stack signature
above (asio `use_future` teardown vs. a gtest-framework `std::mutex::lock`),
re-run the lane; it is this artifact. Only investigate as a real race if the
conflicting accesses name the same `async_mutex` / `waiter_record` object, or if the
`linux-clang-tsan` (libstdc++) lane also fails.
