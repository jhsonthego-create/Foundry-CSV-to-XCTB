# Observed reference case — expected structural results

This document publishes **counts and logic only**. No actual Motorola radio archive, frequencies, subscriber IDs, keys, or confidential codeplug XML are included.

## Inputs

- Original Motorola: MOTOTRBO CPS 2.0 XCTB, default-protected, data model `2.159.125`.
- Radio Foundry ZIP contains `channels.csv`, `zones.csv`, `contacts.csv`, `rx-group-lists.csv`, plus ignored `dtmf-contacts.csv`, `aprs.csv`.
- RF source count: 104 channels, 8 zones, 12 digital contacts, 1 RX group.
- The operator approved one out-of-band channel omission, two specific frequency corrections, high power, and `-RF` suffix/truncation.

## Expected summary

| Section | Original | Added | Final |
|---|---:|---:|---:|
| Channel personalities | 166 | 103 | 269 |
| Zones | 11 | 8 | 19 |
| Contacts | 90 | 12 | 102 |
| Digital RX Groups | 1 | 1 | 2 |
| Roam lists | 3 | 3 | 6 |
| Scan lists | 7 | 0 | 7 |

- 92 RF zone-channel assignments were created.
- 24 roaming channel memberships, in 3 per-zone roam lists: 11, 1, 12.
- 18 new display names required renaming (16 channels, 1 contact, 1 zone); 16-character limits applied where needed.
- 16 RF channel personalities were unassigned to an RF zone but were still imported.
- Verified duplicate UUIDs: 0.
- Verified selected broken references: 0.
- 704 out of 705 original UUID-bearing records byte-equivalent in parsed XML; **the one intentionally changed record is the enclosing parent** that holds all appended sets.
- Packer AES/GZIP/sha/DBNode roundtrip: PASS.
- Actual CPS semantic compile and radio write: outside these independent scripts; must be checked by operator.

## Do not generalize these decisions

Never automatically omit an out-of-band channel, correct any frequency, assume a band limit, or add an SMA license based on this historic case. All such values are operator- and model-specific. This toolkit is about **configuration interoperability, not acquiring or transferring Motorola feature entitlements**.
