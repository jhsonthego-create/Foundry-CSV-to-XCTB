#!/usr/bin/env python3
"""Read-only Radio Foundry CSV ZIP -> Motorola dependency plan.

No Motorola files or RF source files are changed. The output plan is sensitive:
it includes names, frequencies and IDs; do not publish it without review.

Example:
  python rf_preflight.py --rf rf-export.zip --motorola-xctb source.xctb \
      --min-mhz 136 --max-mhz 174 --out import-plan.json

For non-example radios, use --min-mhz / --max-mhz that match YOUR radio,
and OMIT / FIX only entries the operator explicitly authorizes.
"""
import argparse, collections, csv, io, json, re, sys
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import ZipFile

GROUP_MAP = {'contacts.csv': 'PCRContacts',
             'rx-group-lists.csv': 'DigitalRXGroupList',
             'zones.csv': 'Zone', 'channels.csv': 'ConventionalPersonality'}
FIELD_MAP = {'PCRContacts':'ContactName','DigitalRXGroupList':'RXTG_RXTGLISTALIAS',
             'Zone':'ZP_ZONEALIAS','ConventionalPersonality':'CP_CNVPERSALIAS',
             'ScanItems':'SSP_SCANLISTALIAS','RoamList':'SSP_SCANLISTALIAS'}
XSI = '{http://www.w3.org/2001/XMLSchema-instance}type'
REQUIRED = {
 'contacts.csv':['Name','ID','Call Type'],
 'rx-group-lists.csv':['Name','Contacts'],
 'channels.csv':['Name','Mode','RX Frequency (MHz)','TX Frequency (MHz)',
                 'Bandwidth (kHz)','RX Tone','TX Tone','Color Code','Timeslot',
                 'TX Contact','RX Group List','Roaming'],
 'zones.csv':['Name','Channels']
}


def field(record,name):
    return next((c.get('Value') for c in record if c.get('Name') == name),'')


def norm(s):
    return (s or '').strip().casefold()


def yes(s):
    if norm(s) in ('yes','true','1'):return True
    if norm(s) in ('no','false','0',''):return False
    raise ValueError('Unrecognized boolean value: {!r}'.format(s))


def unique_names(rows,kind):
    names = [norm(r['Name']) for r in rows]
    if not all(names) or len(set(names)) != len(names):
        raise ValueError(f'{kind}: missing or duplicate source display names; cannot safely resolve name-based links')


def allocate(rows, existing, limit,kind):
    used = set(existing)
    result = {}
    renamed = []
    for row in rows:
        original = row['Name'].strip()
        collides = norm(original) in used
        suffix = '-RF' if collides else ''
        if len(suffix) >= limit:
            raise ValueError('Invalid name length')
        base = original[:limit-len(suffix)]
        proposed = base + suffix
        if norm(proposed) in used:
            raise ValueError(f'{kind}: cannot create unique name for {original!r}; manual rename required')
        used.add(norm(proposed))
        result[original] = proposed
        if original != proposed:
            renamed.append(dict(kind=kind,source=original,target=proposed,
                                reason='existing name collision' if collides else 'length limit'))
    return result,renamed


def parse_tone(value):
    text=value.strip().upper()
    if not text or text in ('OFF','NONE','CSQ'):return dict(type='CSQ',value=None)
    m=re.fullmatch(r'D(\d{3})([NI])',text)
    if m:return dict(type='DPL',code=m.group(1),inverted=(m.group(2)=='I'))
    try:
        v=float(text)
        if not 50<=v<=300:raise ValueError()
    except ValueError:
        raise ValueError('Unsupported analog tone: '+repr(value))
    return dict(type='TPL',frequency_hz=v)


def read_dbnode_name_sets(dbnode_bytes):
    root=ET.fromstring(dbnode_bytes)
    main=next((e for e in root if e.tag.rsplit('}',1)[-1]=='DBNode'),None)
    if main is None:raise ValueError('No primary DBNode record')
    result={}
    for group,fn in FIELD_MAP.items():
        p=next((el for el in main if el.get('Name')==group),None)
        names=[]
        if p is not None:
            names=[field(record,fn) for record in p if record.get(XSI)=='Record']
        result[group]=names
    return result


def read_rf(zippath):
    out={}
    with ZipFile(zippath) as z:
        base={x.split('/')[-1].casefold():x for x in z.namelist() if not x.endswith('/')}
        for key,cols in REQUIRED.items():
            if key not in base:raise ValueError('RF ZIP missing '+key)
            text=z.read(base[key]).decode('utf-8-sig')
            r=csv.DictReader(io.StringIO(text))
            missing=[col for col in cols if col not in (r.fieldnames or [])]
            if missing:raise ValueError(f'{key}: missing columns {missing}')
            out[key]=list(r)
            unique_names(out[key],key)
    return out


def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--rf',type=Path,required=True)
    root=ap.add_mutually_exclusive_group(required=True)
    root.add_argument('--motorola-xctb',type=Path)
    root.add_argument('--motorola-dbnode',type=Path)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--limit',type=int,default=16)
    ap.add_argument('--min-mhz',type=float,default=136.0)
    ap.add_argument('--max-mhz',type=float,default=174.0)
    ap.add_argument('--omit-channel',action='append',default=[])
    ap.add_argument('--fix-tx',action='append',default=[],metavar='NAME=MHz')
    ap.add_argument('--fix-rx',action='append',default=[],metavar='NAME=MHz')
    args=ap.parse_args()
    if not 3<=args.limit<=64 or args.min_mhz>=args.max_mhz:raise ValueError('Invalid name or band limits')
    if args.motorola_xctb:
        from xctb_roundtrip import unpack,inflate_dbnode
        original=unpack(args.motorola_xctb.read_bytes())
        db=inflate_dbnode(original['xml'])
    else:db=args.motorola_dbnode.read_bytes()
    names=read_dbnode_name_sets(db)
    rf=read_rf(args.rf)
    c=rf['contacts.csv']; rg=rf['rx-group-lists.csv'];ch=rf['channels.csv']; z=rf['zones.csv']
    omit={norm(x) for x in args.omit_channel}
    missing_omits=omit-{norm(x['Name']) for x in ch}
    if missing_omits:raise ValueError('Omit name(s) not found: '+str(missing_omits))
    fixes={}
    for side, items in [('TX',args.fix_tx),('RX',args.fix_rx)]:
        for item in items:
            if '=' not in item:raise ValueError('Frequency repair format must be NAME=MHz')
            name,value=item.rsplit('=',1)
            if norm(name) not in {norm(x['Name']) for x in ch}:raise ValueError('Fix channel not found: '+name)
            fixes[(side,norm(name))]=float(value)
    ch=[x for x in ch if norm(x['Name']) not in omit]
    renames=[];mappings={}
    for k,rows,g,kind in [ ('contacts',c,'PCRContacts','Contact'),
                            ('rx_groups',rg,'DigitalRXGroupList','RX Group'),
                            ('channels',ch,'ConventionalPersonality','Channel'),
                            ('zones',z,'Zone','Zone')]:
        mappings[k],new=allocate(rows,{norm(v) for v in names[g]},args.limit,kind)
        renames.extend(new)
    lookup={key:{norm(old):new for old,new in mapping.items()} for key,mapping in mappings.items()}
    allowed_contacts={norm(x['Name']) for x in c}
    allowed_groups={norm(x['Name']) for x in rg}
    allowed_channels={norm(x['Name']) for x in ch}
    errors=[]; warnings=[];normalized=[]
    for x in rg:
        for ref in filter(None,(p.strip() for p in x['Contacts'].split('|'))):
            if norm(ref) not in allowed_contacts:errors.append(f'RX Group {x["Name"]}: missing contact {ref}')
    zone_assignments={}
    for x in z:
        entries=[p.strip() for p in x['Channels'].split('|') if p.strip()]
        zone_assignments[x['Name']]=[]
        for entry in entries:
            if norm(entry) in omit:
                warnings.append(f'Zone {x["Name"]}: omitted channel {entry}')
            elif norm(entry) not in allowed_channels:
                errors.append(f'Zone {x["Name"]}: unknown channel {entry}')
            else:zone_assignments[x['Name']].append(entry)
    # Build normalized channels and verify source relationships.
    for x in ch:
        name=x['Name'];mode=x['Mode'].strip().upper()
        if mode not in ('FM','DMR'):errors.append(f'{name}: unsupported Mode {mode}')
        rx=float(x['RX Frequency (MHz)']);tx=float(x['TX Frequency (MHz)'])
        rx=fixes.get(('RX',norm(name)),rx)
        tx=fixes.get(('TX',norm(name)),tx)
        if not(args.min_mhz<=rx<=args.max_mhz):errors.append(f'{name}: RX {rx} MHz outside {args.min_mhz}-{args.max_mhz}')
        if not(args.min_mhz<=tx<=args.max_mhz):errors.append(f'{name}: TX {tx} MHz outside {args.min_mhz}-{args.max_mhz}')
        contact=x['TX Contact'].strip();group=x['RX Group List'].strip()
        if contact and norm(contact) not in allowed_contacts:errors.append(f'{name}: TX Contact missing: {contact}')
        if group and norm(group) not in allowed_groups:errors.append(f'{name}: RX Group missing: {group}')
        if yes(x.get('DMO','')) and abs(rx-tx)>1e-6:errors.append(f'{name}: DMO requested but RX/TX differ')
        if mode=='FM':
            parsed_tone={'rx':parse_tone(x['RX Tone']),'tx':parse_tone(x['TX Tone'])}
        else:parsed_tone=None
        assigned=[zone for zone,entries in zone_assignments.items() if norm(name) in {norm(v) for v in entries}]
        roaming_zones=assigned if yes(x['Roaming']) else []
        if yes(x['Roaming']) and not assigned:warnings.append(f'{name}: Roaming=Yes but channel is in no zone')
        if len(roaming_zones)>1:errors.append(f'{name}: appears as roaming in multiple zones, yet personality has one Scan/Roam List reference')
        normalized.append(dict(original_name=name,name=mappings['channels'][name],mode=mode,
                               rx_mhz=rx,tx_mhz=tx,power='HIGH',timeout_s=x.get('Timeout (s)',''),
                               bandwidth_khz=x['Bandwidth (kHz)'],rx_only=yes(x.get('RX Only','')),
                               vox=yes(x.get('VOX','')),color_code=x.get('Color Code',''),
                               timeslot=x.get('Timeslot',''),
                               tx_contact=lookup['contacts'].get(norm(contact)) if contact else None,
                               rx_group=lookup['rx_groups'].get(norm(group)) if group else None,
                               tones=parsed_tone,
                               dmo_source=yes(x.get('DMO','')),
                               extended_range_direct_mode=False,
                               ip_site_connect=yes(x['Roaming']) and mode=='DMR',
                               roaming=yes(x['Roaming']),zones=[mappings['zones'][zone] for zone in assigned],
                               roam_list=mappings['zones'][roaming_zones[0]] if roaming_zones else None))
    # Roam lists must contain DIGITAL members; user-defined roaming may include analog channels, flag for manual review.
    roams={}
    for zone, assigned in zone_assignments.items():
        members=[x for x in normalized if norm(x['original_name']) in {norm(t) for t in assigned} and x['roaming']]
        if members:
            for x in members:
                if x['mode']!='DMR':errors.append(f'{x["original_name"]}: analog Roaming=Yes cannot use IP Site Connect roam-list mode')
            roams[mappings['zones'][zone]]=[x['name'] for x in members]
    # A zone-named list can collide with an EXISTING Motorola roam list.
    # Keep zone alias unchanged, suffix just the NEW roam-list name if needed.
    roam_names,extra_renames=allocate([{'Name':k} for k in roams],
                                     {norm(v) for v in names['RoamList']},args.limit,'Roam List')
    renames.extend(extra_renames)
    roams={roam_names[k]:v for k,v in roams.items()}
    for x in normalized:
        if x['roam_list'] is not None:
            x['roam_list']=roam_names[x['roam_list']]
    status='OK' if not errors else 'ERROR'
    plan=dict(status=status,description='READ-ONLY RF-to-Motorola proposed dependency plan; NOT a merged codeplug',
              motorola_original_name_counts={k:len(v) for k,v in names.items()},
              source_counts={k:len(v) for k,v in rf.items()},
              to_import=dict(contacts=len(c),rx_groups=len(rg),channels=len(ch),zones=len(z),roam_lists=len(roams)),
              omitted_channels=[r['Name'] for r in rf['channels.csv'] if norm(r['Name']) in omit],
              frequency_repairs=[dict(side=side,channel=name,new_mhz=value) for (side,name),value in fixes.items()],
              renames=renames,name_mappings={**mappings,'roam_lists':roam_names},
              contacts=[dict(source=x['Name'],name=mappings['contacts'][x['Name']],id=x['ID'],call_type=x['Call Type']) for x in c],
              rx_groups=[dict(source=x['Name'],name=mappings['rx_groups'][x['Name']],
                              contacts=[lookup['contacts'][norm(k)] for k in x['Contacts'].split('|') if k.strip()]) for x in rg],
              channels=normalized,
              zones=[dict(source=zone,name=mappings['zones'][zone],
                          channels=[lookup['channels'][norm(ch)] for ch in entries]) for zone,entries in zone_assignments.items()],
              roam_lists=roams,errors=errors,warnings=warnings,
              notes=['Existing Motorola records must not be edited',
                     'Create contacts -> RX groups -> channels -> zone/channel assignments -> roam lists -> channel roam refs',
                     'Radio feature flags and authorization are NOT modified',
                     'No Extended Range Direct Mode on unsupported Motorola models',
                     'No scan lists can be inferred without source definitions',
                     'Motorola CPS validation required; no radio writes from this tool'])
    if args.out.exists():raise FileExistsError('Refusing to overwrite existing output '+str(args.out))
    args.out.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('PLAN:',args.out,'STATUS:',status)
    print('COUNTS:',plan['to_import'],'RENAMES:',len(renames),'ERRORS:',len(errors),'WARNINGS:',len(warnings))
    for error in errors:print('ERROR:',error)
    for warning in warnings:print('WARNING:',warning)
    if errors:sys.exit(2)

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,ET.ParseError) as ex:sys.exit('ERROR: '+str(ex))
