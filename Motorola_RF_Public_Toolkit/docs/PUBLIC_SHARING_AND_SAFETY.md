# Publishing the conversion workflow without exposing a real radio codeplug

## Important distinction: two separate conversations

**Conversation A — private conversion job.** Upload your real Motorola XCTB and Radio Foundry ZIP together with the public toolkit. Perform the merge and validate it. Do **not** create a shared link to this conversation if it includes any real codeplug, decrypted XML, private HTML, or uploaded keys.

**Conversation B — public tutorial.** Start a completely new conversation. Upload **only** `Motorola_RF_Public_Toolkit.zip` and paste a short tutorial prompt below. Do not attach the reference case's real radio archives or actual RF export. When it produces the standalone guide, review its messages and uploaded files, then use that conversation's **Share** menu to create a new link. This is separate from Conversation A or any earlier history.

### Ready-to-paste public tutorial prompt

> This is a PUBLIC tutorial conversation. Use only the attached `Motorola_RF_Public_Toolkit.zip`, which contains a standalone read-only decoder, XCTB repacker, RF CSV preflight tool, HTML builder, structural auditor and detailed merge specification. Explain how other users can upload their own ORIGINAL Motorola CPS 2.0 XCTB and Radio Foundry CSV ZIP in a PRIVATE chat, inspect the source schema, construct a correct dependency-aware DBNode merge, repackage the XCTB, and validate it in Motorola CPS. Do not use or request real subscriber data, passwords, encryption keys, personal files or archives in this PUBLIC chat. State clearly that the toolkit does not include a universal fully automated merger and that Motorola CPS still must validate the result. Give download links only to the public toolkit files available in this chat.

### How to create the new ChatGPT share link

1. Start a **new ChatGPT conversation** (not a continuation or branch of the private conversion chat).
2. Attach the public toolkit ZIP. Paste the public tutorial prompt above.
3. Review the completed tutorial and its shared preview, including any files that may appear.
4. Select **Share** in that new conversation, then **Create link** or **Copy link**, depending on the UI.
5. Confirm the link begins `https://chatgpt.com/share/` and test it in a signed-out/incognito window if appropriate.
6. Publish that **new link**, not a link to the private conversion conversation.

At the time this guide was prepared, OpenAI's Help Center states that a personal-account shared conversation can include uploaded files and content visible in the conversation. Review the share preview every time. ChatGPT's sharing UI may change.

Official reference: https://help.openai.com/en/articles/7925741-sharing-conversations-and-scheduled-tasks-in-chatgpt

## If you want a reusable permanent download link to the actual files

The **ChatGPT share link is a conversation snapshot**, not a versioned code repository or guaranteed file-hosting mechanism. For the scripts and guide, a separate public file host may be better:

**GitHub:** Create a new public repository, upload the `scripts/`, `docs/`, `README_START_HERE.md`, `START_NEW_CHAT_PROMPT.txt`, and `requirements.txt`. Add an initial release ZIP. Review contents before publishing. Use the repository URL in the public ChatGPT tutorial.

**Google Drive:** Upload **only** the `Motorola_RF_Public_Toolkit.zip`, set **General access → Anyone with the link → Viewer** in Drive (if your account policy allows), then copy the public file link. Do not assume a Drive file is public just because it has a URL; verify permissions in an incognito browser.

**Other hosting:** A read-only ZIP download on a site you control is fine. Never publish files with the actual codeplug's `DBNodeCmpBytes` or XML contents by accident.

## Keep private; avoid sharing in any public conversation/repository

- Original or merged real `.xctb` archives; `.ctb2` or `.ctb` archives.
- The RF ZIP exported from an actual organization unless expressly authorized and scrubbed.
- `*.decrypted.xml`, `*.DBNode.xml`, `*.DBNodeCmpBytes.bin` and generated HTML explorers for a real radio.
- Hardware serial numbers and host identifiers, group/private radio IDs, radio aliases and subscriber IDs.
- Privacy/encryption keys, RAS/access secrets, passwords, authentication credentials, certificates, codeplug passwords, protected archive passwords.
- Hidden IP addresses, remote site topology, dispatch/agency configuration, RF frequencies/tone systems where publication is unauthorized.
- Unlicensed Motorola binaries, CPS DLLs, device-license payloads, Windows registry and database exports unrelated to the conversion toolkit.

## Redaction guidelines

- Make a **copy** to sanitize; never redact the only good original.
- Do not use naive string replace within a binary `.xctb` (checksum, GZIP, AES block and DBNode references will break).
- Do not publish a 'sanitized working codeplug' unless you have actually removed/neutralized identifiers and secrets, updated all references, repackaged it, decoded it, and validated its integrity. A display alias change is not sufficient to remove hidden data.
- Best public example: wholly synthetic CSVs plus a diagram of a fictional DBNode graph. The public toolkit already contains the technical details needed without exposing any live codeplug.
- `scripts/privacy_inventory.py` is only an inventory helper; it **cannot guarantee** all secrets are detected or scrubbed.

## Version and license considerations

Motorola CPS 2.0, Radio Foundry, and radio firmware evolve. This reverse-engineered schema is unofficial. Check model support, RF/legal authorization, local transmitter rules and private data obligations. No script in this toolkit enables Motorola feature licenses or bypasses radio entitlements.
