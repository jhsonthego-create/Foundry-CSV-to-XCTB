# Complete implementation guide: Radio Foundry CSV to Motorola CPS 2.0 XCTB

**Scope:** Motorola MOTOTRBO CPS 2.x `.xctb` file structure, Radio Foundry (RF) CSV exports, data-preserving schema-aware migration, encryption/compression repackaging, and independent validation. This is an **unofficial, observed** schema and workflow, not a Motorola XSD, supported Motorola interface, or a universal codeplug generator.

This guide is deliberately explicit about what has and hasn't been verified. A valid container/checksum is **necessary but insufficient** to prove CPS semantic correctness or radio programmability.

## 0. Requirements and limitations

- **Inputs:** unmodified Motorola `.xctb`, RF `.zip`, operator-approved import/corrections.
- **Tools:** Python 3.9+; `python -m pip install -r requirements.txt` (`cryptography`); included scripts; Motorola CPS 2.0 for final validation.
- **Supported XCTB writing:** `protect=d` default-protected XCTB. `scripts/xctb_roundtrip.py` was tested against the example on data-model `2.159.125`; it guards known data-models `2.151.206`, `2.153.50`, `2.159.125`. Other formats need separate verification. A password-protected `protect=u` archive can be **read** by the supplied read-only decoder when its password is provided, but the supplied packer deliberately does NOT write `protect=u`. Never silently convert a password-protected archive into default-protected output.
- **Other formats:** legacy `.ctb2` can be decoded read-only by the included decoder; `.ctb` (CPS1) is **not** covered.
- **No licensing modifications:** do not forge radio entitlements, device capabilities, firmware licenses, or activation records; no radio hardware feature is assumed to be supported merely because XML contains a field.
- **Source preservation:** never overwrite original XCTB or RF ZIP; preserve 100% of original Motorola records and configuration. Add RF records using unique new IDs.
- **No radio write:** final CPS validation and operator authorization come **after** repackaging.

## 1. Inventory both inputs, take hashes, inspect the Radio Foundry ZIP

Keep all files in a private working directory. On Linux/WSL:

```bash
sha256sum ORIGINAL_MOTOROLA.xctb RADIO_FOUNDRY_EXPORT.zip
unzip -l RADIO_FOUNDRY_EXPORT.zip
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
Get-FileHash .\ORIGINAL_MOTOROLA.xctb -Algorithm SHA256
Get-FileHash .\RADIO_FOUNDRY_EXPORT.zip -Algorithm SHA256
py -3 -m pip install -r requirements.txt
```

Expect four authoritative RF sources:

| Source | Destination | Dependency |
|---|---|---|
| `contacts.csv` | Motorola Contacts > Contacts, `PCRContacts` | First |
| `rx-group-lists.csv` | Motorola RX Groups Lists > Digital RX Group List, `DigitalRXGroupList` | After contacts |
| `channels.csv` | Motorola channel personalities, `ConventionalPersonality` | After contacts and RX groups |
| `zones.csv` | Motorola Zone/Channel Assignment > Zone, `Zone` and nested `ZoneItems` | After channels |

**Ignore:** `dtmf-contacts.csv`, `aprs.csv` for this particular workflow. Do **not** interpret them as channels or silently import them.

An RF export may be from a radio with different frequency bands, unsupported features, or a different number of channels/zones than the target Motorola model. Record every exception. Check the **actual Motorola radio's band** before excluding or correcting any values.

## 2. Decode source XCTB and produce the HTML reference

Recommended baseline:

```bash
mkdir -p WORK
python scripts/xctb_roundtrip.py verify ORIGINAL_MOTOROLA.xctb
python scripts/decode_xctb_ctb2_with_dbnode.py ORIGINAL_MOTOROLA.xctb --outdir WORK
python scripts/build_rm_contacts_zones_html_v3.py \
  WORK/ORIGINAL_MOTOROLA.DBNode.xml -o WORK/motorola-explorer.html
```

The HTML is a **local/offline visual reference**, not the authoritative merge source. Use it to inspect preexisting channel aliases, zone membership, analog bandwidth, independent RX/TX PL/DPL, digital color code, slots, contacts, scan/roam items, etc. The actual merge must inspect the XML and DBNode fields; HTML views can omit fields.

**Generated XML/HTML is potentially secret-bearing: do not place it in a public repository or shared conversation.**

### 2A. XCTB decoding mechanics — verified observed wrapper

An observed default-protected XCTB has:

1. Motorola copyright/text prefix, followed by a **four-byte little-endian** JSON header length.
2. Outer JSON including `type=xctb`, `protect=d`, `stamp` (Base64 16-byte AES IV), `rmVersion`, and `dataModelVersion.Version`.
3. Remainder: AES-256-CBC ciphertext, PKCS#7-padded.
4. Key derivation for observed default protection:

   ```text
   seed = UTF8("627842")
   h = SHA256(seed)
   mixed = h[0:16] XOR h[16:32]
   iv = Base64Decode(header.stamp)
   aes_key = SHA256(iv XOR mixed)
   ```

5. AES-CBC decrypt; remove and validate PKCS#7 padding; GZIP decompress.
6. Decompressed plaintext: **4-byte little-endian inner-header byte length**, inner JSON header, then `MatrixRadio` XML.
7. Inner header includes `checksum`, the **Base64(SHA256(exact MatrixRadio XML bytes))**. Verify before modifying. Preserve other metadata such as `keyViewPassword` without exposing it.
8. Inside the XML, navigate `MatrixRadio / WorkingCodeplug / Configuration / DBNodeCmpBytes`. That text is **Base64(raw DEFLATE bytes)**. Inflate with `zlib.decompress(blob, -15)`; parse the resulting `DBNode` XML.

Do not confuse the **outer MatrixRadio XML** with the **inner DBNode XML**. Channel records, zones, contacts, scan and roaming relationships in this workflow predominantly live in the inner DBNode. Updating only display-level fields in the outer XML will not import those records.

**Write path is the reverse:** modify DBNode records, serialize DBNode XML → raw DEFLATE → Base64 replace `DBNodeCmpBytes` → recompute outer XML checksum in inner JSON → length-prefix inner JSON+XML → GZIP → pad → AES-256-CBC encrypt with a **fresh random IV** → replace `stamp` in outer JSON → prepend original text and header length → write a new `.xctb`.

The supplied packer performs the wrapper/repack step for default-protected archives and self-tests the decrypted result. It does **not** implement the RF-to-Motorola XML merge, which must be adapted and verified for the target codeplug schema.

## 3. Understand the actual Motorola DBNode schema before coding

The observed `DBNode` XML contains a primary record and nested `RefSet` groups with many `<DBNode xsi:type="Record" ... UUID="..."><DBNode xsi:type="DBField" Name="..." Value="..."/> ...</DBNode>` child nodes. Nested `DBRefField` values often point to another node's **UUID**.

Important: an XML `Name` attribute like `Name="0"` or `Name="161"` is **not** a globally unique record identifier. The `UUID` identifies the record. Generate a fresh UUID for **every new `xsi:type=Record`**, including nested group members and zone/channel assignment rows. Do not alter UUIDs of existing Motorola records.

This observed field map is from one CPS2/4550 codeplug (other codeplug models/versions must be inspected and tested):

| Meaning | Observed DBNode field(s) |
|---|---|
| Contact name | `PCRContacts` → `ContactName` |
| DMR contact ID/type | `PCRContacts/DigitalCalls` member → `DU_CALLLSTID`, `DU_CALLTYPE` (`GRPCALL`, etc.) |
| RX group name | `DigitalRXGroupList` → `RXTG_RXTGLISTALIAS` |
| RX group contact membership | `DigitalRXGroupListItems` → `RXTG_DGUCLCOMP` pointing to `PCRContacts` UUID |
| Channel personality name | `ConventionalPersonality` → `CP_CNVPERSALIAS` |
| Analog/digital personality | `CP_PERSTYPE`: `ANLGCONV` / `DGTLCONV6PT25` observed |
| RX/TX MHz | `CP_RXFREQ`, `CP_TXFREQ` |
| TX power | `CP_TXPWR` = `HIGHPWR` |
| Time-out timer | `CP_TOT` (seconds in observed records) |
| Channel width | `CP_CHNLBWDTH` (`STR_12PT5KHZ`, other values depend on target model) |
| TX analog squelch/tone mode | `CP_TXSQCHTY` and associated RX/TX TPL/DPL fields |
| TPL | `CP_TXTTPLFREQ`, `CP_RXTPLFREQ` plus other tone selectors/index fields |
| DPL | `CP_TXTDPLCD`, `CP_RXDPLCD`, `CP_TXDPLINV`, `CP_RXDPLINV`, plus selector/index fields |
| DMR color code | `CP_COLORCODE` |
| DMR slot | `CP_SLTASSGMNT` (`SLOT1`, `SLOT2`) |
| TX contact | `CP_UKPPERS` → `PCRContacts` UUID |
| RX group | `CP_TGLISTIT` → `DigitalRXGroupList` UUID (observed target) |
| IP Site Connect indication | `CP_MLTSTPSNLTIND=True` and `CP_USELD=ON` observed for imported RF roaming channels; **verify exact semantics in actual CPS and target model** |
| Channel Scan/Roam List link | `CP_SCNROAMLISTIT` → `RoamList` UUID (or `NONE`) with appropriate `ReferSetName` |
| Zone name | `Zone` → `ZP_ZONEALIAS` |
| Zone member | `Zone/ZoneItems` → `ZP_PERSIT` → `ConventionalPersonality` UUID |
| Roam-list name | `RoamList` → `SSP_SCANLISTALIAS` |
| Roam-list zone member | `RoamList/RoamListItems`: `SSP_CNVPERCOMP_Zone` → `Zone` UUID and `SSP_CNVPERCOMP` → **ZoneItem UUID**, not channel personality UUID |

**Critical:** don't change one tone field in isolation. Motorola has several related analogue tone/type/index fields. Compare analog CSQ, TPL and DPL source *templates* from the actual original Motorola codeplug, and clone/reconfigure a schema-compatible channel. The same applies to digital power, slot, RX group, IP Site Connect, and model-specific options. Do not assume a feature flag field is itself sufficient to enable the feature.

## 4. Run RF preflight; build maps before writing

Example preflight for a radio whose **actual supported band is 136–174 MHz** (change for other hardware):

```bash
python scripts/rf_preflight.py \
  --rf RADIO_FOUNDRY_EXPORT.zip \
  --motorola-xctb ORIGINAL_MOTOROLA.xctb \
  --min-mhz 136 --max-mhz 174 \
  --out WORK/import-plan.json
```

Only after the operator explicitly authorizes exceptional changes, add the flags below, replacing the **placeholder values** with the person's actual file data:

```text
--omit-channel 'AUTHORIZED_CHANNEL_TO_EXCLUDE'
--fix-tx 'AUTHORIZED_CHANNEL_NAME=CORRECT_MHZ'
```

The demonstrated historical conversion had one approved out-of-band exclusion and two authorized TX-frequency corrections. **These exceptions must NOT be applied blindly to other files.** The preflight refuses unresolved source references, duplicate source names, out-of-band frequencies, multiple-zone conflicting roam-list assignments, unsupported analog tone syntax, and malformed CSV headers. It does **not** modify any codeplug.

The plan contains: original name → normalized name, any `-RF` suffix/truncation, corrected frequency after explicit approval, RF contact→RX group→channel relationships, channel→zone associations, and zone-named roam lists.

### Collision/rename algorithm

Perform a *complete name-planning pass* before importing any record:

1. Inventory the existing Motorola names separately for contacts, RX groups, personalities, zones, scan lists, roam lists.
2. Match names case-insensitively, but preserve their user-facing case in the final codeplug.
3. If a new RF name matches an existing **Motorola** name of the same category, keep the existing Motorola item, rename the RF item with `-RF` suffix. Example: `ALPHA FIRE` → `ALPHA FIRE-RF`.
4. If the suffixed name exceeds the radio's field limit (16 characters for channel aliases in the reference case), truncate **the base name as needed**, never the `-RF` suffix. Example `S2G40 MAGNOLIA` → `S2G40 MAGNOLI-RF`.
5. Ensure renamed imported items are unique among one another and existing items. If suffixing/truncation creates a second collision, **stop and request a deterministic distinct name**.
6. Maintain maps for `original RF name → renamed RF name → newly assigned Motorola UUID`. Downstream relationships must resolve by UUID, never by stale display name.
7. Preserve the source RF export untouched; any normalized corrections should exist only in import plan/output.

**Reference propagation:** contact rename → contact membership in RX groups **and** `CP_UKPPERS` channel TX contact. Channel rename → zone members, scan lists, roam lists. Zone rename → roam-list name and zone-item references. Roam-list rename → `CP_SCNROAMLISTIT`. Do not make edits in arbitrary order without updating all dependent links.

## 5. Field conversion rules

### 5A. Contacts

`contacts.csv` has `Number,Name,ID,Call Type,Timeslot` in the reference export.

- Ignore `Number` and `Timeslot` (as requested).
- Add a new `PCRContacts` record for each RF contact (even if its display name matches Motorola—suffix it rather than merging away RF provenance).
- Set contact name, numeric ID and Group/Private/All Call appropriately using an actual matching Motorola source record template. Use model-supported call types only.
- Recreate its child `DigitalCalls` record with a new UUID. Preserve required metadata and default fields from a matching template, updating `DU_CALLLSTID` and `DU_CALLTYPE`.
- Build the `RF-contact-name → new PCRContacts.UUID` map. Do not point new channel TX contacts at an old Motorola record just because the names match.

### 5B. RX group lists

`rx-group-lists.csv` supplies `Name` and pipe-separated `Contacts`; ignore `Number`.

- Add the RF `DigitalRXGroupList` record, preserving any existing list unchanged.
- Create `DigitalRXGroupListItems` child records with new UUIDs, one per RF contact in source order; set `RXTG_DGUCLCOMP` to the **new RF contact UUID**.
- Use group alias from the renamed group map. Create the RX groups before assigning them to DMR channels.

### 5C. Channel personalities

Ignore these RF channel columns as explicitly requested: `Number`, `APRS`, `DMR ID`, `All Skip`, `Zone Skip`, `Tone Burst`, `No Beep`, `No Eco`, `Talker Alias TS1`, `Talker Alias TS2`, `Use Location`, `Latitude`, `Longitude`, `SFR`, `SFR A`, `SFR B`, and RF `Squelch`.

- Import all other meaningful supported settings: `Name`, `Mode`, `RX Frequency (MHz)`, `TX Frequency (MHz)`, `Timeout (s)`, `Bandwidth (kHz)`, `RX Tone`, `TX Tone`, `Color Code`, `Timeslot`, `TX Contact`, `RX Group List`, `RX Only`, `VOX`, `DMO`, `Roaming`.
- **Force `CP_TXPWR=HIGHPWR` on every new channel** regardless of the RF power column.
- RF `FM` → Motorola analog. Empty/off tone → CSQ; e.g. `100.0` → TPL/CTCSS 100.0 Hz; `D131N` → DPL code 131 normal polarity; `D466I` → DPL code 466 inverted polarity. RX and TX tones may be different; set each independently. Set all related CPS fields consistently.
- RF `DMR` → Motorola digital. Preserve RX/TX frequencies, CC 0–15, timeslot 1/2, TX contact and optional RX group by UUID. Match Motorola CPS options for digital admission/slot behavior based on model.
- RF `RX Only=Yes` should become the appropriate Motorola receive-only control where supported (this is **not** a reason to import an out-of-band channel).
- RF `VOX=Yes` should map to a compatible channel control if present; if unsupported in the observed model, report it rather than quietly dropping it.
- RF `DMO=Yes`: this is not permission to activate Motorola's **Extended Range Direct Mode**. For XPR 45x0/65x0/SLx, do not turn on that feature. For capable models, require RX MHz == TX MHz and confirm the feature is authorized and present.
- If a new channel is absent from all RF zones, **still create its channel personality**. Do not invent zone placement.
- No arbitrary scan-list creation: the demonstrated RF ZIP had no scan-list definition file.

### 5D. Zones

`zones.csv` has `Name,Channels`, with pipe-delimited channel names in assignment order.

1. Create each new Motorola `Zone` with the mapped (possibly `-RF` suffixed) alias.
2. Create a new `ZoneItems` nested record **per zone-channel assignment**, with its own UUID.
3. `ZP_PERSIT` must reference the **new imported `ConventionalPersonality.UUID`**.
4. Preserve order from the RF `Channels` list; do not make alphabetical reordering unless requested.
5. A channel can appear in more than one zone; use separate ZoneItem UUIDs for each occurrence.
6. Update channel display-name mappings before zone assembly (never use old names after renaming).

### 5E. Roam lists: compute them from `channels.csv:Roaming`

This is the **corrected and approved workflow** (roam-list CSVs were not provided):

1. First finish all imported contacts, RX groups, channel personalities, zones and **ZoneItems**.
2. For each new RF zone, inspect every channel listed in that zone.
3. If no member channel has `Roaming=Yes`, **do not create a roam list** for that zone.
4. If ≥1 channel has `Roaming=Yes`, set the imported **DMR** channel to IP Site Connect (using model-verified settings).
5. Create a new Motorola **RoamList** using the **resolved zone name** (respect collision/length rules).
6. For every `Roaming=Yes` channel in that zone, add a new `RoamListItems` child record pointing to **both**: `SSP_CNVPERCOMP_Zone = Zone.UUID` and `SSP_CNVPERCOMP = that channel's ZoneItems.UUID`.
7. Go back to each imported roaming channel personality and set `CP_SCNROAMLISTIT` to the **new RoamList.UUID**, `ReferSetName=RoamList`, updating any associated IP Site Connect fields.
8. Leave imported non-roaming channels outside that roam list. Leave all original Motorola roam lists untouched.
9. If an imported channel is roaming in **multiple zones** requiring different list UUIDs, one channel's Scan/Roam reference cannot express both: **stop and report it**, rather than silently choosing one or cloning without authorization.
10. If RF `Roaming=Yes` is on an analog/unsupported channel or lacks a zone, report the incompatibility; do not fabricate configuration.

**This is a relational round-robin operation:** channels → zone memberships → roam lists containing zone items → channels' Scan/Roam list field. The list points to **ZoneItem UUID**, not just the channel personality UUID. Missing this detail creates superficially valid XML with broken or semantically incorrect roaming.

## 6. Mutating DBNode XML correctly

**Do this in a new working copy of the parsed XML, never in the source file.**

Recommended programmer workflow:

1. Parse source DBNode XML using a namespace-aware parser that preserves field names and schema structure.
2. Inventory available analog, digital, roaming-enabled and other appropriate Motorola personalities. Choose **model- and feature-compatible** templates; clone a template record to preserve hundreds of unrelated required/default fields.
3. For each cloned `xsi:type=Record`, create a new collision-resistant UUID (e.g. `uuid.uuid4()`) for the cloned parent **and every descendant Record**. Update references within the clone if they originally pointed to other cloned descendants. Update the `LastModifiedDate` consistently; do not reuse historical source UUIDs.
4. Populate exact new field values from RF plan; only set fields whose meaning/format has been established from source records and CPS; don't convert unknown values by guessing.
5. Append new records to the correct `RefSet` preserving correct parent attributes, `RelationshipType`/`IsTopSet` helper nodes, and nested item layout.
6. Verify every new `DBRefField` targeting a UUID corresponds to the right new or preserved object. Do not reuse an old UUID under an imported name.
7. Make a complete post-write graph audit before serializing.
8. Serialize to e.g. `WORK/edited.DBNode.xml` as UTF-8. Confirm XML parses and contains all original Motorola records unchanged (except its enclosing top-level RefSet parent that necessarily includes new children).

**Do not assume** that cloning one digital personality works for all feature states; particularly preserve the difference between ordinary digital and IP Site Connect-enabled personality fields. Use actual source reference templates and verify acceptance in CPS.

## 7. Repackage a new XCTB

Once `WORK/edited.DBNode.xml` is complete and audited:

```bash
python scripts/xctb_roundtrip.py repack ORIGINAL_MOTOROLA.xctb \
  --dbnode WORK/edited.DBNode.xml --out WORK/MERGED_CANDIDATE.xctb
python scripts/xctb_roundtrip.py verify WORK/MERGED_CANDIDATE.xctb
```

What the repacker checks:

- Source is `protect=d` and data-model known to the utility.
- AES decrypt, valid PKCS7, GZIP, embedded XML SHA-256.
- One populated `DBNodeCmpBytes` and valid raw DEFLATE stream.
- New DBNode XML parses.
- DBNode raw DEFLATE re-encodes correctly.
- Unrelated original MatrixRadio XML bytes remain intact except replacement of encoded DBNode value.
- New XML digest and inner-header length are correct.
- Fresh random AES IV, new encrypted payload, and preserved copyright/text wrapper.
- The generated XCTB decrypts back to byte-for-byte identical modified MatrixRadio XML before it is written.

There is also an alternative for a fully edited outer XML (e.g. legitimate changes outside DBNode):

```bash
python scripts/xctb_roundtrip.py repack ORIGINAL_MOTOROLA.xctb \
  --xml WORK/edited.decrypted.xml --out WORK/MERGED_CANDIDATE.xctb
```

**Do not edit original XCTB in place; do not modify `protect=u` password archives with this packer.**

## 8. Independent structural QA and CPS handoff

```bash
python scripts/audit_xctb_merge.py ORIGINAL_MOTOROLA.xctb \
  WORK/MERGED_CANDIDATE.xctb --out WORK/merge-audit.json
python scripts/decode_xctb_ctb2_with_dbnode.py \
  WORK/MERGED_CANDIDATE.xctb --outdir WORK/check
python scripts/build_rm_contacts_zones_html_v3.py \
  WORK/check/MERGED_CANDIDATE.DBNode.xml -o WORK/check/merged-explorer.html
```

Also write a **row-by-row QA CSV** matching every imported RF channel to final Motorola personality UUID and fields, with at least: source/final name, mode, RX/TX MHz, high power, TOT, bandwidth, RX/TX PL/DPL/CSQ, color code, timeslot, TX contact, RX group, zone names, ZoneItem IDs, roaming source boolean, IP Site Connect status, roam list name and UUID, any correction/omission. Perform similar QA for contacts, RX group member order, and list membership.

The included structural auditor verifies:

- Valid source/candidate encryption, wrapper checksums, XML and DBNode inflate.
- Original record UUIDs remain present and original leaf/nested records remain unchanged.
- Newly created UUIDs are unique and selected references resolve.
- Expected top-level record delta for contacts, RX groups, channels, zones, roaming and scan lists.

It intentionally permits the main enclosing top-level `DBNode` record to grow, because adding records changes its child tree. This is **not** permission to change its unrelated fields or existing nested records.

**MANDATORY CPS validation:** Open the merged `.xctb` in the appropriate Motorola CPS 2.0 version, inspect new digital/analog controls and zone/roam assignments, run validation and compile checks, save a new archive if CPS normalizes fields, and only then consider an authorized radio write. If CPS refuses to open, check schema/defaults, model/firmware constraints, version mismatch and references. A successful checksum is **not proof** of CPS acceptance. If you change licenses/features or radio firmware implicitly during conversion, stop.

## 9. Debugging and failure modes

| Symptom | Likely issue / action |
|---|---|
| Source XCTB says `protect=u` | Requires owner-supplied archive password for reading; supplied packer won't write `u` |
| Unknown data-model version | Do not force `TESTED_MODELS`; inspect format against a known working archive first |
| AES padding failure | Wrong archive protection/password, corruption, or unsupported format |
| XML checksum mismatch | Archive modified/corrupted; do not continue to patch data |
| DBNode inflate failure | Wrong Base64/raw-vs-zlib wrapper, truncated stream, unsupported layout |
| Duplicate UUID | Cloned parent or nested child reused an existing ID |
| CPS opens but channel/zone missing | Wrong `RefSet`, helper nodes, `CP_PERSTYPE` or zone's `ZP_PERSIT` UUID |
| Contact list appears but DMR channel TX call wrong | Incorrect `CP_UKPPERS` UUID mapping or wrong contact call type |
| RX Group empty | `RXTG_DGUCLCOMP` references old/different contact or member records malformed |
| Roam list empty or wrong | `SSP_CNVPERCOMP` points at personality UUID rather than `ZoneItem.UUID`; wrong zone pointer |
| Roaming checked but not working | Model/IPSC capability, `CP_MLTSTPSNLTIND` and related settings not correct, wrong list, RF/site system mismatch |
| CPS rejects Extended Range Direct Mode | Channel RX != TX or radio/model doesn't support the feature; don't enable it |
| Naming collision persists | Rename map incomplete; use UUID references and check 16-character truncation collisions |
| Out-of-band receive-only channel | Explicitly omit or ask the operator; don't assume RX-only bypasses model band limits |
| CPS rejects valid XCTB | Container validity != semantic validity; inspect CPS log/error and compare real source schema |

## 10. Record of the successfully constructed reference case

The historic reference conversion used a Motorola CPS2 data-model `2.159.125` source and RF ZIP with 104 channels, 8 zones, 12 contacts, 1 RX group. Operator explicitly authorized:

- Ignore `dtmf-contacts.csv`, `aprs.csv`.
- Omit one specifically identified out-of-band channel.
- Correct two specifically authorized TX-frequency entries (not a general rule).
- Force new high power and preserve original codeplug.
- Suffix collisions `-RF`, truncate base names as needed.
- Create roam lists by zone using RF channel `Roaming=Yes` flags, with ZoneItem → RoamList → channel backreferences.

Final structural result: **+103 channels, +8 zones, +12 contacts, +1 RX group, +3 roam lists**, with **24** roaming members distributed across **11 / 1 / 12** three lists. Original **166 channels, 11 zones, 90 contacts, 1 RX group, 3 roam lists and 7 scan lists** remained. All old **704** nested UUID records were preserved unchanged; the parent root expands, appropriately. All structural checks passed. This is a **worked regression example**, not a template for copying real individuals' frequencies/IDs/license records.

## 11. Deliverables another ChatGPT instance must produce

Deliver as distinct files:

- `candidate_merged.xctb`
- `merge-audit.json` and `merge-report.json` (input hashes, exact exceptions, counts, tests, errors, CPS validation status)
- `name-uuid-map.csv` (source/target name, category, reason, new UUID, parent and downstream references)
- `QA-channels.csv` (all imported channel field comparisons)
- `merged-explorer.html` (for private local viewing)
- Optional `edited.DBNode.xml` and `decrypted.xml`, **private only**

**Do not call the archive radio-ready until it has passed an actual CPS version/model validation and authorized radio checks.**
