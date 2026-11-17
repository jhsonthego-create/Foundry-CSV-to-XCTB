#!/usr/bin/env python3
"""Research-only XCTB (default-protected) unpack/pack/verify utility.

Input file is NEVER modified. Tested with Motorola data-model 2.159.125.
The original source archive is required to preserve its wrapper and metadata.

Usage:
  python xctb_roundtrip.py inspect source.xctb
  python xctb_roundtrip.py extract source.xctb --out-dir extracted
  python xctb_roundtrip.py repack source.xctb --dbnode edited.DBNode.xml --out candidate.xctb
  python xctb_roundtrip.py repack source.xctb --xml edited.decrypted.xml --out candidate.xctb
  python xctb_roundtrip.py verify candidate.xctb

This rebuilds the binary container and internal checksums; it does NOT attest that
Motorola CPS will accept or compile modified configuration data. This is NOT a
radio-programming or entitlement-modification tool. Do not publish extracted XML
without checking it for passwords, RAS/EP keys, private IDs and frequencies.
"""
import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys
import xml.etree.ElementTree as ET
import zlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

DATA_MODELS = {'2.151.206', '2.153.50', '2.159.125'}
MAX_XML = 128 * 1024 * 1024
MAX_DBNODE = 256 * 1024 * 1024
MARKER = b'{\r\n  "version"'
DBNODE_REGEX = re.compile(rb'(<DBNodeCmpBytes>)([^<]*)(</DBNodeCmpBytes>)')


def sha(data):
    return hashlib.sha256(data).digest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def derive(iv):
    h = sha(b'627842')
    return sha(bytes(x ^ a ^ b for x, a, b in zip(iv, h[:16], h[16:])))


def unpack(raw):
    p = raw.find(MARKER)
    require(p >= 4, 'Not a recognized XCTB wrapper')
    size = struct.unpack_from('<I', raw, p - 4)[0]
    require(16 <= size <= 4096 and p + size < len(raw), 'Invalid XCTB JSON header length')
    head_bytes = raw[p:p + size]
    header = json.loads(head_bytes)
    require(header.get('type') == 'xctb' and header.get('protect') == 'd',
            'Only default-protected XCTB (protect=d) supported for WRITING; do not guess passwords')
    model = header.get('dataModelVersion', {}).get('Version')
    require(model in DATA_MODELS, f'Unsupported / untested XCTB data model: {model}')
    iv = base64.b64decode(header['stamp'], validate=True)
    require(len(iv) == 16, 'Invalid IV')
    ciphertext = raw[p + size:]
    require(ciphertext and len(ciphertext) % 16 == 0, 'Invalid AES ciphertext length')
    dec = Cipher(algorithms.AES(derive(iv)), modes.CBC(iv)).decryptor()
    padded = dec.update(ciphertext) + dec.finalize()
    padlen = padded[-1]
    require(1 <= padlen <= 16 and padded[-padlen:] == bytes([padlen]) * padlen, 'Bad AES padding')
    gz = padded[:-padlen]
    require(gz.startswith(b'\x1f\x8b\x08'), 'Decrypted payload is not GZIP')
    inner = gzip.decompress(gz)
    require(len(inner) >= 4, 'Truncated inner metadata')
    inner_size = struct.unpack_from('<I', inner, 0)[0]
    require(2 <= inner_size <= 4096 and 4 + inner_size < len(inner), 'Invalid inner JSON header')
    inner_bytes = inner[4:4 + inner_size]
    metadata = json.loads(inner_bytes)
    xml = inner[4 + inner_size:]
    require(len(xml) <= MAX_XML, 'XML too large')
    require(base64.b64encode(sha(xml)).decode('ascii') == metadata.get('checksum'),
            'Embedded XML SHA-256 checksum does not match')
    tree = ET.fromstring(xml)
    require(tree.tag.rsplit('}', 1)[-1] == 'MatrixRadio', 'Unexpected XML root')
    return dict(outer_prefix=raw[:p - 4], header=header, head_bytes=head_bytes,
                inner_bytes=inner_bytes, metadata=metadata, xml=xml,
                model=model, radio_root=tree)


def inflate_dbnode(xml):
    root = ET.fromstring(xml)
    matches = [el for el in root.iter() if el.tag.rsplit('}', 1)[-1] == 'DBNodeCmpBytes']
    require(len(matches) == 1 and matches[0].text, 'Expected one populated DBNodeCmpBytes element')
    compressed = base64.b64decode(''.join(matches[0].text.split()), validate=True)
    decoder = zlib.decompressobj(-15)
    data = decoder.decompress(compressed, MAX_DBNODE + 1)
    require(len(data) <= MAX_DBNODE and not decoder.unconsumed_tail, 'DBNode inflated above size cap')
    data += decoder.flush()
    require(decoder.eof and not decoder.unused_data and len(data) <= MAX_DBNODE,
            'DBNode deflate stream truncated or invalid')
    db = ET.fromstring(data)
    require(db.tag.rsplit('}', 1)[-1] == 'DBNode', 'DBNode XML root unexpected')
    return data


def insert_dbnode(outer_xml, dbnode_xml):
    require(len(dbnode_xml) <= MAX_DBNODE, 'DBNode too large')
    dbroot = ET.fromstring(dbnode_xml)
    require(dbroot.tag.rsplit('}', 1)[-1] == 'DBNode', 'Expected DBNode XML')
    compressor = zlib.compressobj(level=9, wbits=-15)
    packed = compressor.compress(dbnode_xml) + compressor.flush()
    encoded = base64.b64encode(packed)
    matches = list(DBNODE_REGEX.finditer(outer_xml))
    require(len(matches) == 1, 'DBNodeCmpBytes must occur exactly once in simple XML form')
    match = matches[0]
    candidate = outer_xml[:match.start(2)] + encoded + outer_xml[match.end(2):]
    require(inflate_dbnode(candidate) == dbnode_xml, 'DBNode round-trip integrity test failed')
    return candidate


def repack(source_decoded, changed_xml):
    require(len(changed_xml) <= MAX_XML, 'New XML too large')
    xml_root = ET.fromstring(changed_xml)
    require(xml_root.tag.rsplit('}', 1)[-1] == 'MatrixRadio', 'Not MatrixRadio XML')
    inflate_dbnode(changed_xml)  # fail closed when DBNode compression is broken
    new_hash = base64.b64encode(sha(changed_xml))
    old_hash = source_decoded['metadata']['checksum'].encode('ascii')
    require(len(old_hash) == len(new_hash) and source_decoded['inner_bytes'].count(old_hash) == 1,
            'Cannot safely replace inner checksum')
    new_inner_header = source_decoded['inner_bytes'].replace(old_hash, new_hash, 1)
    inner = struct.pack('<I', len(new_inner_header)) + new_inner_header + changed_xml
    zipped = gzip.compress(inner, compresslevel=9, mtime=0)
    iv = os.urandom(16)
    old_stamp = source_decoded['header']['stamp'].encode('ascii')
    new_stamp = base64.b64encode(iv)
    require(len(old_stamp) == len(new_stamp) and source_decoded['head_bytes'].count(old_stamp) == 1,
            'Cannot safely replace outer IV stamp')
    head = source_decoded['head_bytes'].replace(old_stamp, new_stamp, 1)
    pad = 16 - len(zipped) % 16
    enc = Cipher(algorithms.AES(derive(iv)), modes.CBC(iv)).encryptor()
    crypt = enc.update(zipped + bytes([pad])*pad) + enc.finalize()
    output = source_decoded['outer_prefix'] + struct.pack('<I', len(head)) + head + crypt
    self_check = unpack(output)
    require(self_check['xml'] == changed_xml, 'Generated archive plaintext mismatch')
    return output


def write_new(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(raw)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('command', choices=['inspect', 'verify', 'extract', 'repack'])
    ap.add_argument('source', type=Path)
    ap.add_argument('--out-dir', type=Path)
    ap.add_argument('--xml', type=Path, help='Edited full MatrixRadio XML for repack')
    ap.add_argument('--dbnode', type=Path, help='Edited decompressed DBNode XML for repack')
    ap.add_argument('--out', type=Path, help='New XCTB output for repack')
    args = ap.parse_args()
    decoded = unpack(args.source.read_bytes())
    print('SOURCE:', args.source)
    print('DATA_MODEL:', decoded['model'])
    print('PROTECTION:', decoded['header']['protect'])
    print('XML_SHA256:', sha(decoded['xml']).hex())
    if args.command == 'inspect':
        return
    dbnode = inflate_dbnode(decoded['xml'])
    print('DBNODE_BYTES:', len(dbnode))
    print('VERIFIED: AES, GZIP, XML checksum, XML structure, raw DEFLATE DBNode')
    if args.command == 'verify':
        return
    if args.command == 'extract':
        dest = args.out_dir or args.source.parent
        a = dest / (args.source.stem + '.decrypted.xml')
        b = dest / (args.source.stem + '.DBNode.xml')
        require(a.resolve() != args.source.resolve() and b.resolve() != args.source.resolve(), 'Source collision')
        require(not a.exists() and not b.exists(), 'Output already exists: choose another --out-dir')
        write_new(a, decoded['xml'])
        write_new(b, dbnode)
        print('DECRYPTED_XML:', a)
        print('DBNODE_XML:', b)
        return
    require(bool(args.xml) ^ bool(args.dbnode), 'For repack provide exactly ONE of --xml or --dbnode')
    require(args.out is not None and args.out.suffix.lower() == '.xctb', '--out must be a .xctb filename')
    require(args.out.resolve() != args.source.resolve(), 'REFUSING to overwrite source XCTB')
    candidate_xml = args.xml.read_bytes() if args.xml else insert_dbnode(decoded['xml'], args.dbnode.read_bytes())
    new_raw = repack(decoded, candidate_xml)
    write_new(args.out, new_raw)
    print('OUTPUT:', args.out)
    print('OUTPUT_SHA256:', sha(new_raw).hex())
    print('WARNING: Archive format is verified; CPS open/compile and radio-write are NOT verified')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, IndexError, ET.ParseError, zlib.error, gzip.BadGzipFile) as ex:
        sys.exit('ERROR: ' + str(ex))
