Radio Foundry DM32UV Zip Export to M XCTB - DMR/analog channels - M CPS does not support P25, hence this also does not.

## Trademarks & Disclaimer
MOTOROLA, MOTO, MOTOROLA SOLUTIONS, and MOTOTRBO are trademarks or registered trademarks of Motorola Trademark Holdings, LLC. All other trademarks are the property of their respective owners.

This project is an independent work and is not affiliated with, endorsed by, or sponsored by Motorola Solutions, Inc.

This project is an independent work and is not affiliated with, endorsed by, or sponsored by Radio Foundry.

#Begin

 Motorola CPS 2.0 + Radio Foundry CSV → XCTB toolkit

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

