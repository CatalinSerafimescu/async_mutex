# libc++ TSAN false positives — and the instrumented-libc++ fix

The `linux-clang-libc++-tsan` CI lane used to intermittently report
`ThreadSanitizer: data race ... in operator delete` on three tests. This is a
**known false positive caused by an uninstrumented libc++**, not a data race in
`async_mutex`. It is **fixed** in CI by loading a TSAN-instrumented libc++ at test
time (see *Fix* below). This document records the root cause and the fix so a future
recurrence — or a change to that CI step — is understood.

## Root cause

The lane compiles our code (and gtest) with `-fsanitize=thread`, but links the
**stock `libc++-22` shared library from apt.llvm.org, which is _not_ TSAN-instrumented**.
TSAN therefore cannot observe the synchronization that happens *inside* `libc++.so`
— in particular the release/acquire edges of `std::future`/`std::promise`
shared-state teardown and `std::mutex` internals. When a cross-thread teardown
frees a `use_future` `std::promise<void>` shared state on a worker thread, TSAN
sees the intercepted `operator delete` but not the libc++-internal edge that
ordered it, and reports a phantom race against an unrelated, earlier access at the
same (recycled) heap address. This is a documented limitation of TSAN with an
uninstrumented standard library; LLVM's own guidance is to build an instrumented
libc++ for TSAN.

Corroborating evidence:

- **The "conflicting" accesses are unrelated objects.** The write is asio freeing
  the `use_future` promise state on the worker thread; the "previous read" stack is
  **gtest's own framework `std::mutex::lock()`** inside `testing::Test::Run()`
  (`gtest.cc:2664`) — both frames resolve inside the uninstrumented `libc++.so.1`.
  The race addresses are low `0x7220000000XX` (TSAN's heap) and differ per test
  (`…218`, `…018`).
- **libc++-only.** The identical commit passes `linux-clang-tsan` (libstdc++), whose
  `<future>` is header-inline and therefore fully instrumented. A genuine race in
  the header would fire under both standard libraries.
- **Independent of the mutex code.** It first surfaced on a docs-only commit while
  the prior commit passed; the header is byte-identical across them. The gtest
  bodies pass (`[ PASSED ]`) — only TSAN's nonzero exit fails ctest.
- **Not reproducible on an instrumented libc++.** Reproduce-then-disprove: the apt
  libc++ trips reliably in CI, an instrumented libc++ gives **0 races**.

This is the same artifact the origin project (fixpp) diagnosed and fixed in its
`tier3-libcxx.yml`; the affected tests and toolchain were ported from there.

## Affected tests

`CATSERAF_ASYNC_MUTEX_TEST_SEAM` tests that run a second `io_context` on a
background `std::thread` and coordinate via `asio::co_spawn(..., asio::use_future)`:

- `sync_async_mutex_aba_interleave` (`AsyncMutexAbaInterleave.PopPreCasAbaCorruptionDetected`)
- `sync_async_mutex_terminal_cas_recursive_unlock` (`...F6FifoExhaustedTerminalCasFailGrantsWaiter`)
- `sync_async_mutex_chain_walk_cas_loss` (`...ResidualWalkCancelWinsGrantCasLoss`)

## Fix

`.github/workflows/ci-linux-libcxx.yml`, TSan leg only:

1. **Fetch a TSAN-instrumented libc++** — built from `llvmorg-22.1.2` with
   `-DLLVM_USE_SANITIZER=Thread` (ABI-identical to stock, so no relink), pulled
   from the public, **digest-pinned** image
   `ghcr.io/catalinserafimescu/fixpp-libcxx-tsan@sha256:65106764…` and `docker cp`'d
   out. It is pinned by digest, not the mutable `:22.1.2` tag, because the `.so` is
   loaded into the test process — a re-pushed tag could fabricate or suppress TSAN
   results.
2. **Load it ahead of the apt libc++** by prepending its directory to
   `LD_LIBRARY_PATH` in the TSan `Test` step, so the `libc++.so.1` soname resolves
   to the instrumented copy at runtime.

Beyond killing the flake, this closes a real blind spot: without it, the lane
cannot see genuine races synchronized through `libc++.so` internals.

## Re-triage

If the TSan leg reports a race:

- If the two conflicting accesses resolve inside `libc++.so.1` (e.g. `std::mutex::lock`
  / `std::promise::~promise` / `operator delete` in `use_future` teardown) and the
  instrumented-libc++ step was skipped or the image failed to load, it is this
  artifact — check that `Fetch instrumented libc++ (TSan)` ran and
  `LD_LIBRARY_PATH` points at it.
- Treat it as a **real** race only if the conflicting accesses name the same
  `async_mutex` / `waiter_record` object, or if the `linux-clang-tsan` (libstdc++)
  lane also fails.
