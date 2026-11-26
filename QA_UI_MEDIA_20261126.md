# PULS UI and media — 2026-11-26

Base: real-media branch da8b04c. Compact source has 150 first-aid topics (70 critical, 57 urgent), not the historical full offline pack. The 3 archive parts are absent. Do not overwrite full assets with this compact edition.

UI: removed duplicate favorites shortcut and duplicated SOS prompt, collapsed recent and backup, added grouped medicine shelf without dosage recommendations. Existing checklists, settings, and emergency instructions retained. Photos are shown only from a local attribution manifest; no runtime external requests. Candidate list is separate and not claimed as installed media. First-aid images and videos need medical and rights review before publication.

Privacy branch is divergent, not merged; review before release. Build and emulator verification still required.

8.19.3: emulator installation and launch passed; browser chain test used a mismatched URL glob (index.html omitted). 8.19.4 uses hash predicates, adds critical-topic search with call access retained, a combined missing supplies list, keyboard focus indicators and actual library counts. New CI results pending. No clinical advice changed or new media approved.

8.19.5: action-first compact emergency layout, 8 immediate home shortcuts, step-bound clinically and rights-reviewed media, no automatic playback, direct media jump only when content exists. Candidate quarantine expanded by 15 files (30 total), including original photos and video. Quarantine is not packaged clinical media. No clinical text rewritten. New CI pending.

Original decorative action/equipment cues: 103 mapped to existing steps across 34 guides. These are symbols, not clinical illustrations or technique demonstrations. Added synthetic JPEG loading and no-autoplay regression checks; fixed strict selector after nested credits were introduced.

CI caught an isolated medicine-license fixture regression: the new topic database check ran even for medicine-only tests. Scoped it to actual first-aid records and added an exact-step/unknown-topic regression test.

8.19.6: 39 curated phrase groups (182 Russian/English search phrases) prioritize relevant existing guides, preserve adult/child variants, no automatic diagnosis/navigation. Added emergency call on home search with critical or zero results; no-results SOS offers clear search and full catalog. No medical instructions rewritten.

Follow-up: explicit phrase order now wins over incidental body-text matches, general burns and pregnancy bleeding do not imply unrelated conditions. SOS search also displays up to four matching noncritical guides separately and always exposes full catalog search. Browser test blocks and records external requests. No new clinical instructions or media approvals.

8.19.7: native foreground-only emergency screen awake via origin-restricted WebMessageListener (setting defaults on; unsupported WebView gracefully falls back), cached search normalization, larger reviewed-media manifest capacity, primary photo at each step with extra media collapsed, local coverage counts for photos/videos/medicines/kits. New CI pending. 8.19.6 passed Android install and browser regression.

8.19.8: 12 new bilingual guide drafts tied to NHS or NHS trust patient sources; 40 reference medicine cards with class, explicit index-only source and no dosing. 162 guides, 501 steps, 240 medicines. 12 new symbolic cue mappings. Independent clinical review remains pending; no new approved media. Source scope must not be represented as medical approval.

8.19.9: all 73 critical guides have hand-mapped symbolic action cues; 246 nonempty icons in 87 guides. No change in clinical instructions. QA medicine and kit photos visibly labeled pending review if approvals missing. This is not photographic or clinical coverage.
