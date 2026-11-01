/* Back up NOR and disk prefix. All source operations are reads. */
typedef struct {B magic[16];U version,trust,original_permission,original_kmode,restored,nor_bytes,disk_bytes,nor_sum,disk_sum,error,reserved[2];} Meta;
static Meta meta={"ZTEST1RAW109",109};
static const B guard[16]={0,0,15,225,19,0,160,227,128,0,128,227,64,0,128,227};
static const U oem[6]={0x88000000,0x80000000,64,0x80000000,0xa0000000,64};
static U cursor=128;
static U copy_memory(U address,B*out,U n){U got=0;return API(ReadProcessMemory,U(*)(U,U,void*,U,U*))(0x42,address,out,n,&got)&&got==n;}
static U export_chunk(U n){
 if(!read_at(carrier,cursor,buf+65536,n))return 0;
 for(U i=0;i<n;i++)buf[32768+i]=buf[i]^buf[65536+i];
 if(!write_at(cursor,buf+32768,n))return 0;
 for(U i=0;i<n;i++)h.checksum+=buf[i];
 cursor+=n;h.size=cursor-64;return 1;
}
static U capture_nor(void){
 U error=0,map=0,unmap=0;
 meta.original_permission=API(SetProcPermissions,ONE)(~0u);
 meta.original_kmode=API(SetKMode,ONE)(1);
 if(API(GetCurrentPermissions,U(*)(void))()!=~0u)error=20;
 if(!error&&(!copy_memory(0x88201000,buf,16)||!same(buf,guard,16)||!copy_memory(0x882019e0,buf,24)||!same(buf,oem,24)))error=21;
 if(!error){
  U dll=API(LoadLibraryW,U(*)(const W*))((const W*)L"ceddk.dll");
  U mapper=dll?API(GetProcAddressW,U(*)(U,const W*))(dll,(const W*)L"MmMapIoSpace"):0;
  unmap=dll?API(GetProcAddressW,U(*)(U,const W*))(dll,(const W*)L"MmUnmapIoSpace"):0;
  if(!mapper||!unmap)error=22;
  else{
   map=((U(*)(unsigned long long,U,U))mapper)(0xa0000000ull,0x200000,0);
   if(!map||(map&4095)||map>0xffe00000u)error=23;
   for(U at=0;!error&&at<0x200000;at+=32768){
    if(!copy_memory(map+at,buf,32768)||!copy_memory(map+at,buf+32768,32768)||!same(buf,buf+32768,32768)){error=24;break;}
    U sum=0;for(U i=0;i<32768;i++)sum+=buf[i];
    if(!export_chunk(32768)){error=25;break;}
    meta.nor_sum+=sum;meta.nor_bytes+=32768;
   }
  }
 }
 if(map&&unmap)((void(*)(U,U))unmap)(map,0x200000);
 API(SetKMode,ONE)(meta.original_kmode);
 U mode=API(SetKMode,ONE)(meta.original_kmode);
 API(SetProcPermissions,ONE)(meta.original_permission);
 meta.restored=((mode!=0)==(meta.original_kmode!=0))&&API(GetCurrentPermissions,U(*)(void))()==meta.original_permission;
 if(!meta.restored)error=26;
 return error;
}
typedef struct {U sector,count,buffers,status,callback,pointer,length;} SG;
static U disk_read(U f,U sector,B*out){
 SG q={sector,64,1,~0u,0,(U)out,32768};U returned=0;
 return API(DeviceIoControl,U(*)(U,U,void*,U,U,U,U*,U))(f,0x75c08,&q,28,0,0,&returned,0)&&q.status==0;
}
static U capture_disk(void){
 U f=API(CreateFileW,OPEN)((const W*)L"DSK1:",0x80000000,3,0,3,0,0);
 if(f==~0u)return 30;
 U error=0;
 for(U sector=0;sector<2048;sector+=64){
  if(!disk_read(f,sector,buf)||!disk_read(f,sector,buf+32768)||!same(buf,buf+32768,32768)){error=31;break;}
  U sum=0;for(U i=0;i<32768;i++)sum+=buf[i];
  if(!export_chunk(32768)){error=32;break;}
  meta.disk_sum+=sum;meta.disk_bytes+=32768;
 }
 API(CloseHandle,ONE)(f);return error;
}
static U capture(void){
 meta.trust=API(CeGetCurrentTrust,U(*)(void))();
 if(meta.trust!=2)return 19;
 U error=capture_nor();
 if(!error)error=capture_disk();
 return error;
}
__attribute__((section(".text.entry"))) void entry(void){
 API(SignalStarted,ONE)(85);API(Sleep,ONE)(2500);
 if(find_carrier()){
  h.state=1;h.permission=API(GetCurrentPermissions,U(*)(void))();
  if(save()){
   buf=(B*)API(LocalAlloc,U(*)(U,U))(0,98304);h.size=64;
   h.error=buf?capture():16;meta.error=h.error;
   if(buf){
    for(U i=0;i<64;i++)buf[i]=((B*)&meta)[i];
    U old_cursor=cursor;cursor=64;
    if(!export_chunk(64))h.error=33;
    cursor=old_cursor;h.size=old_cursor-64;
    API(LocalFree,ONE)((U)buf);
   }
   h.state=h.error?3:2;save();
  }
  API(CloseHandle,ONE)(carrier);
 }
 API(ExitThread,ONE)(0);
}
