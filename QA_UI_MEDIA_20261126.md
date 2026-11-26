# PULS UI and media — 2026-11-26

Base: real-media branch da8b04c. Compact source has 150 first-aid topics (70 critical, 57 urgent), not the historical full offline pack. The 3 archive parts are absent. Do not overwrite full assets with this compact edition.

UI: removed duplicate favorites shortcut and duplicated SOS prompt, collapsed recent and backup, added grouped medicine shelf without dosage recommendations. Existing checklists, settings, and emergency instructions retained. Photos are shown only from a local attribution manifest; no runtime external requests. Candidate list is separate and not claimed as installed media. First-aid images and videos need medical and rights review before publication.

Privacy branch is divergent, not merged; review before release. Build and emulator verification still required.

8.19.3: emulator installation and launch passed; browser chain test used a mismatched URL glob (index.html omitted). 8.19.4 uses hash predicates, adds critical-topic search with call access retained, a combined missing supplies list, keyboard focus indicators and actual library counts. New CI results pending. No clinical advice changed or new media approved.

8.19.5: action-first compact emergency layout, 8 immediate home shortcuts, step-bound clinically and rights-reviewed media, no automatic playback, direct media jump only when content exists. Candidate quarantine expanded by 15 files (30 total), including original photos and video. Quarantine is not packaged clinical media. No clinical text rewritten. New CI pending.

Original decorative action/equipment cues: 103 mapped to existing steps across 34 guides. These are symbols, not clinical illustrations or technique demonstrations. Added synthetic JPEG loading and no-autoplay regression checks; fixed strict selector after nested credits were introduced.

CI caught an isolated medicine-license fixture regression: the new topic database check ran even for medicine-only tests. Scoped it to actual first-aid records and added an exact-step/unknown-topic regression test.
