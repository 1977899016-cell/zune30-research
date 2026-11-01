"""Small fixed-base ARM CE executable builder for owned research utilities."""
import struct
from pathlib import Path
import pefile
BASE=0x10000;CODE=0x1000;DATA=0x3000;IMPORTS=0x5000
def align(n,b):return (n+b-1)&-b
def make_imports(names, coredll):
    pe=pefile.PE(str(coredll))
    exports={s.name.decode():s.ordinal for s in pe.DIRECTORY_ENTRY_EXPORT.symbols if s.name}
    data=bytearray(40);ilt=IMPORTS+len(data)
    thunks=b''.join(struct.pack('<I',exports[n]|0x80000000) for n in names)+bytes(4)
    data+=thunks;iat=IMPORTS+len(data);data+=thunks;dll=IMPORTS+len(data);data+=b'coredll.dll\0'
    struct.pack_into('<5I',data,0,ilt,0,0,dll,iat)
    return bytes(data),iat,{n:BASE+iat+4*i for i,n in enumerate(names)}
def build(code,data,idata,iat,count):
    assert len(code)<=0x2000 and len(data)<=0x2000 and len(idata)<=0x1000
    dos=bytearray(128);dos[:2]=b'MZ';struct.pack_into('<I',dos,60,128)
    coff=struct.pack('<HHIIIHH',0x1c0,3,0,0,0,224,0x103);opt=bytearray(224)
    struct.pack_into('<H',opt,0,0x10b);struct.pack_into('<III',opt,4,align(len(code),512),align(len(data),512)+align(len(idata),512),0)
    struct.pack_into('<III',opt,16,CODE,CODE,DATA);struct.pack_into('<III',opt,28,BASE,4096,512)
    struct.pack_into('<HHHHHH',opt,40,4,0,0,0,4,20);struct.pack_into('<II',opt,56,0x6000,512);struct.pack_into('<HH',opt,68,9,0)
    struct.pack_into('<IIIIII',opt,72,65536,4096,1048576,4096,0,16);struct.pack_into('<II',opt,104,IMPORTS,40);struct.pack_into('<II',opt,192,iat,(count+1)*4)
    sections=[];payload=bytearray();offset=512
    for name,rva,blob,flags in [(b'.text',CODE,code,0x60000020),(b'.data',DATA,data,0xc0000040),(b'.idata',IMPORTS,idata,0xc0000040)]:
        size=align(len(blob),512);sections.append(struct.pack('<8sIIIIIIHHI',name,len(blob),rva,size,offset,0,0,0,0,flags));payload+=blob+bytes(size-len(blob));offset+=size
    header=dos+b'PE\0\0'+coff+opt+b''.join(sections);assert len(header)<=512
    image=header+bytes(512-len(header))+payload
    parsed=pefile.PE(data=image);assert parsed.OPTIONAL_HEADER.Subsystem==9 and len(parsed.DIRECTORY_ENTRY_IMPORT[0].imports)==count
    return image
