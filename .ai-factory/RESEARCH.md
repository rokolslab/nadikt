# Research

Updated: 2026-08-03 10:08
Status: active

## Active Summary (input for /aif-plan)
<!-- aif:active-summary:start -->
Topic: ASR model delivery and coding-dictation benchmark direction for Nadikt MVP.

Goal: Preserve fully local/private runtime while allowing practical model delivery options for installation and prioritizing accurate Russian dictation with coding-related English terms.

Constraints:
- Runtime dictation, ASR, insertion, dictionary, and normalization must work without internet after installation.
- Internet during installation is allowed only as fallback if embedded installer, separate model pack, or removable media delivery is not practical.
- Runtime must accept only a local verified model package path with checksum/package validation; Hub model names or implicit network downloads remain forbidden.
- Separate model pack files next to the installer or copied from a flash drive are acceptable.
- Installer/model pack size is not currently a major constraint.
- Manual model pack selection/installation by the user is acceptable for MVP.
- ASR priority is Russian accuracy with coding anglicisms, library names, commands, identifiers, abbreviations, and technical terms.
- Full mixed Russian-English dictation can be postponed or marked experimental after the first usable MVP.

Decisions:
- Separate install-time delivery from runtime package validation.
- Support multiple delivery channels for the same local model package format: embedded installer, separate offline package, and online installer fallback.
- Reframe early MVP ASR target from generic `Russian` vs full `Russian + English` to `Russian with coding terms` as the practical priority.
- Do not choose final ASR model until real local package load/probe and quality/resource benchmark results exist.

Open questions:
- Which concrete model packages can be legally redistributed or downloaded by the installer.
- Whether GigaAM cache-style local package loading works with real `.ckpt` and tokenizer files under blocked-network conditions.
- Whether faster-whisper CTranslate2 local packages provide enough Russian/coding-term quality on CPU INT8.
- What minimal coding-dictation dataset best represents the user's real workflow.
- Which Windows packaging mechanism will support model pack import/download with checksum verification.

Success signals:
- Real local package probe loads, warms up, short-transcribes, and closes at least one candidate under externally blocked network.
- Missing/corrupted package fails before backend import/load and never attempts network access.
- First coding-dictation benchmark covers Russian phrases with code terms such as `pytest`, `docker compose`, `React component`, `FastAPI route`, `access token`, `pull request`, and common identifiers.
- Benchmark compares quality, RTF, latency, CPU, and peak RAM on the current i3 12th gen development machine before later Windows baseline validation.
- A decision matrix can recommend one MVP ASR path and one fallback path without weakening runtime privacy/offline guarantees.

Next step: Create a full AI Factory plan for `ASR model delivery and coding dictation benchmark`, including documentation updates, dataset expansion, real model package preparation outside Git, offline load gates, and first quality/resource benchmark.
<!-- aif:active-summary:end -->

## Sessions
<!-- aif:sessions:start -->
### 2026-08-03 10:08 - ASR delivery and coding dictation direction
What changed:
- User clarified installation/runtime constraints for model delivery and MVP ASR priorities.
- Internet during installation is allowed only as fallback; post-install runtime must remain fully local/offline.
- Separate model pack files and removable media delivery are acceptable.
- Installer/model pack size is not important at this stage.
- Manual model pack installation is acceptable.
- Accuracy for Russian with coding anglicisms is more important than lowest latency.
- Full mixed Russian-English dictation can wait until after the first usable MVP.

Key notes:
- Model delivery should be architecture-neutral: embedded installer, offline model pack, and internet fallback all produce the same local verified model package.
- Runtime policy remains strict: local path only, checksum required, no Hub model identifiers, no implicit network download.
- Benchmark should add or emphasize a `ru_coding_terms` category with realistic coding-task dictation phrases.
- Next engineering gate should prove real local package load/warm-up/short-transcribe/close under blocked network before broader UI work.

Links (paths):
- `.ai-factory/ROADMAP.md`
- `docs/requirements/Nadikt_TZ_v0.2.md`
- `docs/research/local_asr_offline_package_prototype.md`
- `docs/research/local_asr_performance_benchmark_plan.md`
<!-- aif:sessions:end -->
