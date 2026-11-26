# PULS UI and media — 2026-11-26

Base: real-media branch da8b04c. Compact source has 150 first-aid topics (70 critical, 57 urgent), not the historical full offline pack. The 3 archive parts are absent. Do not overwrite full assets with this compact edition.

UI: removed duplicate favorites shortcut and duplicated SOS prompt, collapsed recent and backup, added grouped medicine shelf without dosage recommendations. Existing checklists, settings, and emergency instructions retained. Photos are shown only from a local attribution manifest; no runtime external requests. Candidate list is separate and not claimed as installed media. First-aid images and videos need medical and rights review before publication.

Privacy branch is divergent, not merged; review before release. Build and emulator verification still required.

8.19.3: emulator installation and launch passed; browser chain test used a mismatched URL glob (index.html omitted). 8.19.4 uses hash predicates, adds critical-topic search with call access retained, a combined missing supplies list, keyboard focus indicators and actual library counts. New CI results pending. No clinical advice changed or new media approved.
