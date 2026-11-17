#!/usr/bin/env python3
"""Conservative PRIVATE DATA INVENTORY for an extracted XML/HTML/TXT file.
This tool does not redact anything and cannot certify a file is public-safe.
Only potentially sensitive FIELD NAMES and finding counts are shown, not values.
Usage: python privacy_inventory.py private.decrypted.xml
"""
import argparse,collections,re,sys
from pathlib import Path

PATTERNS={
 'credentials/passwords':r'(?i)(PASS(?:WORD)?|SECRET|TOKEN|CREDENTIAL|CERTIFICAT|AUTHPASSWORD)',
 'cryptography/access keys':r'(?i)(KEY|PRIVACY|RAS|AES|ENCRYPT|KMF|OTAR)',
 'identity/host/radio ID':r'(?i)(SERIAL|HARDWAREUUID|RADIOID|SUBSCRIBER|CONTACTID|CALLLSTID|IMEI|HOSTID|IPADDRESS)',
 'site/network settings':r'(?i)(FREQ|NETWORK|SITE|IPADDR|ROAM|SCAN|CHANNEL|ZONE)',
}

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('input',type=Path)
 args=ap.parse_args()
 if args.input.suffix.lower() not in ('.xml','.html','.txt'):
  raise ValueError('This helper only inventories XML/HTML/TXT, NOT encrypted XCTB files')
 text=args.input.read_text(encoding='utf-8',errors='replace')
 fields=re.findall(r'\bName=[\'\"]([^\'\"<>]{1,200})[\'\"]',text)
 names=fields or re.findall(r'\b(?:Password|SerialNumber|RadioID|Key|Privacy)[A-Za-z0-9_]*',text)
 print('SOURCE:',args.input)
 print('WARNING: This is NOT a sanitizer or permission to publish the data.')
 for category,pattern in PATTERNS.items():
  hits=sorted(set(f for f in names if re.search(pattern,f)))
  print('\n',category,':',len(hits),'distinct suspicious field names')
  for name in hits[:25]:print(' ',name)
  if len(hits)>25:print('  ... additional fields omitted')
 print('\nDECISION: Treat original radio data as PRIVATE until manually reviewed and fully sanitized.')

if __name__=='__main__':
 try:main()
 except (ValueError,OSError) as ex:sys.exit('ERROR: '+str(ex))
