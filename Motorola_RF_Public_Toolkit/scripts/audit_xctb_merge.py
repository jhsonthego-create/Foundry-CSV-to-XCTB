#!/usr/bin/env python3
"""Read-only preservation/reference audit of ORIGINAL versus MERGED XCTB.

Verifies wrapper/integrity, duplicate UUIDs, preservation of all old records,
record group deltas, and selected inter-record links. This is structural QA
only, not a substitute for Motorola CPS open/compile/on-radio validation.

  python audit_xctb_merge.py original.xctb candidate.xctb --out audit.json
"""
import argparse,collections,hashlib,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
from xctb_roundtrip import unpack,inflate_dbnode

XSI='{http://www.w3.org/2001/XMLSchema-instance}type'
GROUPS=['PCRContacts','DigitalRXGroupList','ConventionalPersonality','Zone','RoamList','ScanItems']

def field(rec,name):return next((c.get('Value') for c in rec if c.get('Name')==name),None)
def get_main(db):return next(c for c in db if c.tag.rsplit('}',1)[-1]=='DBNode')
def get_set(main,name):return next((c for c in main if c.get('Name')==name),None)
def get_records(root):
 return {x.get('UUID'):x for x in root.iter() if x.get(XSI)=='Record' and x.get('UUID')}
def source(path):
 data=path.read_bytes();u=unpack(data);db=ET.fromstring(inflate_dbnode(u['xml']));
 ids=[x.get('UUID') for x in db.iter() if x.get(XSI)=='Record' and x.get('UUID')];
 duplicates=[k for k,v in collections.Counter(ids).items() if v>1]
 return u,db,ids,duplicates,hashlib.sha256(data).hexdigest()

def main():
 ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
 ap.add_argument('original',type=Path);ap.add_argument('merged',type=Path)
 ap.add_argument('--out',type=Path,required=True)
 a=ap.parse_args()
 u0,d0,ids0,dup0,hash0=source(a.original)
 u1,d1,ids1,dup1,hash1=source(a.merged)
 old=get_records(d0);now=get_records(d1)
 missing=sorted(set(old)-set(now))
 altered=[id for id,record in old.items() if id in now and ET.tostring(record)!=ET.tostring(now[id])]
 allowed_top_uuid=get_main(d0).get('UUID')
 altered_real=[id for id in altered if id != allowed_top_uuid]
 added=set(now)-set(old)
 incoming=collections.Counter();failed=[]
 for id in added:
  record=now[id]
  for node in record.iter():
   if node.get(XSI)!='DBRefField':continue
   name=node.get('Name','');v=node.get('Value','');setname=node.get('ReferSetName','')
   if setname and len(v)==36 and v.count('-')==4 and v not in now:
    failed.append(dict(record=id,field=name,value=v,refer_set=setname))
   elif setname and len(v)==36 and v.count('-')==4:
    incoming[setname]+=1
 main0=get_main(d0);main1=get_main(d1)
 counts={}
 for name in GROUPS:
  x=get_set(main0,name);y=get_set(main1,name)
  oldgroup=[c for c in x if c.get(XSI)=='Record'] if x is not None else []
  newgroup=[c for c in y if c.get(XSI)=='Record'] if y is not None else []
  counts[name]=dict(original=len(oldgroup),candidate=len(newgroup),added=len(newgroup)-len(oldgroup))
 # Strong checks of special reference chains for newly added objects.
 check=[]
 for rec in (r for r in get_set(main1,'Zone') if r.get('UUID') in added):
  for refset in rec:
   if refset.get('Name')!='ZoneItems':continue
   for item in refset:
    if item.get(XSI)!='Record':continue
    v=field(item,'ZP_PERSIT')
    if v not in now:check.append(dict(kind='zone-personality',zone=rec.get('UUID'),value=v))
 for rec in (r for r in get_set(main1,'RoamList') if r.get('UUID') in added):
  for refset in rec:
   if refset.get('Name')!='RoamListItems':continue
   for item in refset:
    if item.get(XSI)!='Record':continue
    for fn in ['SSP_CNVPERCOMP_Zone','SSP_CNVPERCOMP']:
     v=field(item,fn)
     if v not in now:check.append(dict(kind=fn,roamlist=rec.get('UUID'),value=v))
 for rec in (r for r in get_set(main1,'ConventionalPersonality') if r.get('UUID') in added):
  v=field(rec,'CP_SCNROAMLISTIT')
  if v not in (None,'NONE','SELECTED') and v not in now:
   check.append(dict(kind='channel-scan-or-roam',channel=rec.get('UUID'),value=v))
 # Check that the enclosing parent changed ONLY by adding new RefSet records.
 skeleton=[]
 orig_main=get_main(d0);new_main=get_main(d1)
 if orig_main.attrib!=new_main.attrib:
  skeleton.append('Primary record attributes differ')
 base_children={c.get('Name') or c.tag.rsplit('}',1)[-1]:c for c in orig_main}
 cand_children={c.get('Name') or c.tag.rsplit('}',1)[-1]:c for c in new_main}
 for cname,orig_child in base_children.items():
  n=cand_children.get(cname)
  if n is None:
   skeleton.append('Primary record missing child: '+cname)
  elif orig_child.get(XSI)=='RefSet':
   if orig_child.attrib!=n.attrib:
    skeleton.append('Existing RefSet attrs changed: '+cname)
   old_nonrecords=[ET.tostring(v) for v in orig_child if v.get(XSI)!='Record']
   new_nonrecords=[ET.tostring(v) for v in n if v.get(XSI)!='Record']
   if old_nonrecords!=new_nonrecords:
    skeleton.append('RefSet helper nodes changed: '+cname)
  elif ET.tostring(orig_child)!=ET.tostring(n):
   skeleton.append('Existing primary field changed: '+cname)
 success=not any((dup0,dup1,missing,altered_real,failed,check,skeleton))
 report={'result':'PASS' if success else 'FAIL','scope':'STRUCTURAL VALIDATION ONLY; NOT CPS VALIDATION',
  'original':str(a.original),'candidate':str(a.merged),
  'original_sha256':hash0,'candidate_sha256':hash1,
  'original_data_model':u0['model'],'candidate_data_model':u1['model'],
  'original_uuid_records':len(ids0),'candidate_uuid_records':len(ids1),
  'original_uuids_unchanged':len(old)-len(missing)-len(altered),
  'expected_modified_parent_root':allowed_top_uuid if allowed_top_uuid in altered else None,
  'new_uuid_records':len(added),'duplicate_uuid_original':dup0,'duplicate_uuid_candidate':dup1,
  'missing_original_uuid_records':missing,'changed_original_uuid_records_outside_top':altered_real,
  'missing_new_refs':failed,'broken_structural_refs':check,
  'parent_root_skeleton_issues':skeleton,
  'new_resolved_refs_by_set':dict(incoming), 'top_level_group_counts':counts,
  'notes':['Input files are not modified','XML + DBNode integrity rechecked',
           'Does not prove radio hardware limitations, RF authorizations, CPS semantic compile, feature entitlements, or radio write safety']}
 if a.out.exists():raise FileExistsError('Refusing to overwrite '+str(a.out))
 a.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print('AUDIT:',report['result'])
 print('Original UUID records unchanged:',report['original_uuids_unchanged'],'of',len(old))
 print('New UUID records:',len(added));print('Group counts:',counts)
 print('Reference errors:',len(failed)+len(check),'Parent skeleton errors:',len(skeleton))
 print('OUTPUT:',a.out)
 if not success:sys.exit(2)

if __name__=='__main__':
 try:main()
 except (ValueError,OSError,KeyError,ET.ParseError) as ex:sys.exit('ERROR: '+str(ex))
