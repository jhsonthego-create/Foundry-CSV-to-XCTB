#!/usr/bin/env python3
"""Synthetic, non-radio regression tests. No real Motorola/RF data included.
Run from toolkit root: python -m unittest discover -s tests -v
"""
import base64,csv,gzip,hashlib,io,json,os,struct,subprocess,sys,tempfile,unittest,xml.etree.ElementTree as ET,zlib
from pathlib import Path
from zipfile import ZipFile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import xctb_roundtrip as x

XSI='{http://www.w3.org/2001/XMLSchema-instance}type'


def mk_dbnode():
    db=ET.Element('DBNode',{'Name':'Configs'})
    main=ET.SubElement(db,'DBNode',{XSI:'Record','Name':'0','UUID':'11111111-1111-4111-8111-111111111111'})
    for name in ('PCRContacts','DigitalRXGroupList','Zone','ConventionalPersonality','RoamList','ScanItems'):
        s=ET.SubElement(main,'DBNode',{XSI:'RefSet','Name':name})
        if name in ('PCRContacts','ConventionalPersonality'):
            r=ET.SubElement(s,'DBNode',{XSI:'Record','Name':'0','UUID':('22222222-2222-4222-8222-222222222222' if name=='PCRContacts' else '33333333-3333-4333-8333-333333333333')})
            ET.SubElement(r,'DBNode',{XSI:'DBField','Name':('ContactName' if name=='PCRContacts' else 'CP_CNVPERSALIAS'),'Value':('TG1' if name=='PCRContacts' else 'ALPHA')})
    return ET.tostring(db,encoding='utf-8')


def make_synthetic_xctb(db):
    co=zlib.compressobj(level=6,wbits=-15)
    bz=base64.b64encode(co.compress(db)+co.flush()).decode()
    xm=f'<MatrixRadio><WorkingCodeplug><Configuration><DBNodeCmpBytes>{bz}</DBNodeCmpBytes></Configuration></WorkingCodeplug></MatrixRadio>'.encode()
    inner={'version':'1.0','checksum':base64.b64encode(x.sha(xm)).decode(),'keyViewPassword':''}
    ib=json.dumps(inner).encode()
    blob=struct.pack('<I',len(ib))+ib+xm
    g=gzip.compress(blob,mtime=0)
    iv=bytes.fromhex('01020304050607080910111213141516')
    hdr={'version':'1.0','type':'xctb','protect':'d','stamp':base64.b64encode(iv).decode(), 'dataModelVersion':{'Version':'2.159.125'}}
    hb=json.dumps(hdr,indent=2).replace('\n','\r\n').encode()
    pad=16-(len(g)%16)
    from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
    enc=Cipher(algorithms.AES(x.derive(iv)),modes.CBC(iv)).encryptor()
    cipher=enc.update(g+bytes([pad])*pad)+enc.finalize()
    return b'Synthetic XCTB demo (not a real radio) '+struct.pack('<I',len(hb))+hb+cipher


def zip_csv(path):
    def c(rows):
        t=io.StringIO();w=csv.DictWriter(t,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        return t.getvalue()
    data={
     'contacts.csv':c([{'Number':'1','Name':'TG1','ID':'101','Call Type':'Group','Timeslot':''}]),
     'rx-group-lists.csv':c([{'Number':'1','Name':'ListA','Contacts':'TG1'}]),
     'zones.csv':c([{'Name':'ZoneA','Channels':'ALPHA|BRAVO'}]),
     'channels.csv':c([
       {'Number':'1','Name':'ALPHA','Mode':'FM','RX Frequency (MHz)':'146.520','TX Frequency (MHz)':'146.520','Power':'Low','Timeout (s)':'60','Bandwidth (kHz)':'12.5','RX Tone':'100.0','TX Tone':'D131N','Squelch':'0','Color Code':'1','Timeslot':'1','TX Contact':'','RX Group List':'','RX Only':'No','VOX':'No','DMO':'No','Roaming':'No'},
       {'Number':'2','Name':'BRAVO','Mode':'DMR','RX Frequency (MHz)':'146.535','TX Frequency (MHz)':'146.535','Power':'Low','Timeout (s)':'60','Bandwidth (kHz)':'12.5','RX Tone':'','TX Tone':'','Squelch':'0','Color Code':'1','Timeslot':'2','TX Contact':'TG1','RX Group List':'ListA','RX Only':'No','VOX':'No','DMO':'No','Roaming':'Yes'}])
    }
    with ZipFile(path,'w') as z:
        for k,v in data.items():z.writestr(k,v)

class TestPublicTools(unittest.TestCase):
    def test_codec_roundtrip_and_no_original_change(self):
        source=make_synthetic_xctb(mk_dbnode())
        u=x.unpack(source)
        self.assertEqual(x.inflate_dbnode(u['xml']),mk_dbnode())
        changed=mk_dbnode().replace(b'TG1',b'TG2')
        xm=x.insert_dbnode(u['xml'],changed)
        out=x.repack(u,xm)
        self.assertNotEqual(out,source)
        self.assertEqual(x.unpack(out)['xml'],xm)
        self.assertEqual(x.inflate_dbnode(x.unpack(out)['xml']),changed)
        self.assertEqual(x.unpack(source)['xml'],u['xml'])
    def test_bad_integrity_fails_closed(self):
        source=bytearray(make_synthetic_xctb(mk_dbnode()));source[-1]^=17
        with self.assertRaises(ValueError):x.unpack(bytes(source))
    def test_rf_plan_remaps_collision_and_roaming(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            (td/'src.dbnode.xml').write_bytes(mk_dbnode())
            zip_csv(td/'rf.zip')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/rf_preflight.py'),'--rf',str(td/'rf.zip'),
              '--motorola-dbnode',str(td/'src.dbnode.xml'),'--out',str(td/'plan.json')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr+'\n'+result.stdout)
            p=json.loads((td/'plan.json').read_text())
            self.assertEqual(p['to_import']['channels'],2)
            self.assertEqual(p['name_mappings']['contacts']['TG1'],'TG1-RF')
            self.assertEqual(p['name_mappings']['channels']['ALPHA'],'ALPHA-RF')
            self.assertEqual(p['rx_groups'][0]['contacts'],['TG1-RF'])
            self.assertEqual(p['zones'][0]['channels'],['ALPHA-RF','BRAVO'])
            self.assertEqual(p['roam_lists'],{'ZoneA':['BRAVO']})
            self.assertEqual(p['channels'][1]['tx_contact'],'TG1-RF')
            self.assertEqual(p['channels'][1]['roam_list'],'ZoneA')
            self.assertFalse(p['channels'][1]['extended_range_direct_mode'])
            self.assertEqual(p['channels'][0]['power'],'HIGH')

if __name__=='__main__':unittest.main()
