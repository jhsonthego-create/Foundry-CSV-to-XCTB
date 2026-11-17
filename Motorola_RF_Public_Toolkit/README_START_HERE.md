# Motorola CPS 2.0 + Radio Foundry CSV → XCTB toolkit

**Standalone reference, 2026-11-17. Unofficial research/interop tooling; not affiliated with Motorola Solutions or Radio Foundry.**

This package explains how to preserve a Motorola MOTOTRBO CPS 2.0 codeplug, import Radio Foundry CSV records, rebuild a new `.xctb`, and verify its structure. The public package contains **no actual user codeplug, key, CSV export, or decrypted operational XML**.

## What goes into a NEW ChatGPT conversation

Upload these **private inputs** into the new conversation (not into a public shared conversation unless sanitized):

1. `ORIGINAL_MOTOROLA.xctb` — the unmodified archive exported from Motorola CPS 2.0.
2. `RADIO_FOUNDRY_EXPORT.zip` — original Radio Foundry export. Requires `channels.csv`, `zones.csv`, `contacts.csv`, `rx-group-lists.csv` (other CSVs may be present).
3. `Motorola_RF_Public_Toolkit.zip` — **this** toolkit.
4. Optional, only after reviewing/redacting secrets: an **already merged working XCTB**, QA reports, and the original+merged pair. These are useful regression examples but are *not needed* to start.

Paste `START_NEW_CHAT_PROMPT.txt` as the opening prompt in the new conversation.

**The toolkit does not include an automatic general-purpose RF→Motorola merger.** It includes a tested decoder, an independently tested XCTB repacker, a CSV dependency/rename preflight planner, an HTML viewer generator, a structural auditor, an observed field map, and a precise **merge implementation specification**. The new ChatGPT instance must implement/check the DBNode merge for the *actual* radio schema and test it. Do not assume cloning records from an unrelated Motorola model will work.

## Files

| File | Purpose |
|---|---|
| `START_NEW_CHAT_PROMPT.txt` | Ready-to-paste detailed prompt for a separate **private conversion** conversation |
| `START_PUBLIC_TUTORIAL_CHAT_PROMPT.txt` | Separate prompt for a **new publicly shareable tutorial** conversation; no real radio inputs |
| `docs/COMPLETE_CONVERSION_GUIDE.md` | Step-by-step conversion, schema, reference rules, repack, validation, troubleshooting |
| `docs/PUBLIC_SHARING_AND_SAFETY.md` | How to publish without leaking private codeplug information |
| `docs/REFERENCE_CASE_EXPECTED_RESULTS.md` | Verified **counts and test expectations** from the successful example, no raw radio data |
| `scripts/decode_xctb_ctb2_with_dbnode.py` | Verified read-only unpacker for XCTB/CTB2 (supports protected XCTB with provided password) |
| `scripts/build_rm_contacts_zones_html_v3.py` | Offline searchable HTML channel/zone/contact reference builder |
| `scripts/xctb_roundtrip.py` | Verified extract/verify/repack for **default-protected XCTB**; preserves wrapper and checksums |
| `scripts/rf_preflight.py` | RF CSV parsing, validation, collisions, frequency exceptions, renaming, zone/roam dependency plan |
| `scripts/audit_xctb_merge.py` | Compare original vs resulting XCTB; verify old records and new UUID references |
| `requirements.txt` | Python dependency |

## Quick start

```bash
python -m pip install -r requirements.txt
python scripts/xctb_roundtrip.py verify ORIGINAL_MOTOROLA.xctb
python scripts/decode_xctb_ctb2_with_dbnode.py ORIGINAL_MOTOROLA.xctb --outdir WORK
python scripts/build_rm_contacts_zones_html_v3.py WORK/ORIGINAL_MOTOROLA.DBNode.xml -o WORK/motorola-view.html
python scripts/rf_preflight.py --rf RADIO_FOUNDRY_EXPORT.zip \
  --motorola-xctb ORIGINAL_MOTOROLA.xctb --out WORK/import-plan.json \
  --min-mhz 136 --max-mhz 174
```

**The `rf_preflight.py` command above does not modify or merge anything.** Change the frequency range to the actual radio's band. If a channel is intentionally excluded or frequencies corrected, pass explicit `--omit-channel` and `--fix-tx` options; do not silently discard or modify channels.

After the DBNode merge has been implemented and produced `WORK/edited.DBNode.xml`:

```bash
python scripts/xctb_roundtrip.py repack ORIGINAL_MOTOROLA.xctb \
  --dbnode WORK/edited.DBNode.xml --out WORK/MERGED_CANDIDATE.xctb
python scripts/xctb_roundtrip.py verify WORK/MERGED_CANDIDATE.xctb
python scripts/audit_xctb_merge.py ORIGINAL_MOTOROLA.xctb \
  WORK/MERGED_CANDIDATE.xctb --out WORK/merge-audit.json
```

**Then open the new XCTB in Motorola CPS 2.0 and run its configuration validation. Do not write the radio before the CPS checks pass and a reliable original backup exists.**

## What has actually been tested

- Successfully decoded and verified the original reference Motorola XCTB (data-model `2.159.125`).
- Successfully decoded and verified the independently built merged reference XCTB.
- Completed extract → repackage → independently decode verification with unchanged source DBNode.
- The RF preflight produced the same counts and zone-based roam member totals as the reference conversion.
- The audit verified 704 unchanged preexisting nested records out of 705 total including the intentionally expanded top parent record; zero broken selected references.
- **No claim is made that these scripts alone have performed Motorola CPS semantic compilation, on-radio writing, or independent validation of another model.**

## File and public-sharing rules

- Keep real `.xctb`, decrypted XML, DBNode XML, private import plans, and generated HTML **private by default**.
- Don't upload Motorola DLLs, CPS binaries, licenses, passwords, cryptographic keys, or actual radio IDs in the public toolkit.
- To make a public ChatGPT link, create a **new conversation** with the **public toolkit only** and use its Share menu. There is no API action in this package that creates or shares a ChatGPT conversation.
- If publishing a Drive/GitHub/Gist repository, upload this public package only; the input files are supplied privately by each user.

Read `docs/COMPLETE_CONVERSION_GUIDE.md` before modifying a codeplug.
