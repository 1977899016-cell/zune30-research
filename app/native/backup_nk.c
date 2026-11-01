/* Offline candidate only. Reads NK; writes exclusively to a pre-existing,
 * exact-size, token-identified generic MTP carrier. Never creates files,
 * changes registry, flashes, reboots, or performs raw device IO.
 * A separate boot-entry installation decision is required before deployment.
 */
typedef unsigned int U;
typedef unsigned short W;
typedef unsigned char B;
#include "ce_imports.h"
#include "config104.h"
#define API(n,T) ((T)(*(volatile U*)IAT_##n))
typedef U(*ONE)(U);
typedef U(*OPEN)(const W*,U,U,U,U,U,U);
typedef U(*RW)(U,void*,U,U*,U);
typedef U(*SEEK)(U,U,U*,U);
typedef struct { B magic[16], token[16]; U version, capacity, object, state, size, error, checksum, permission; } Header;
/* The host binds this complete 64-byte header after ordinary-object creation.
 * Volatile prevents compile-time folding of the template object ID/token. */
static volatile const Header expected={"ZTEST1BACKUP104",TOKEN104,104,CAPACITY104,OBJECT104,0,0,0,0,0};
static Header h;
static W root[260],path[280];
static B* buf;
static U carrier=~0u;
static U same(const void*a,const volatile void*b,U n){const B*x=a;const volatile B*y=b;while(n--)if(*x++!=*y++)return 0;return 1;}
static U pos(U f,U n){return API(SetFilePointer,SEEK)(f,n,0,0)==n;}
static U read_at(U f,U at,void*out,U n){U got=0;return pos(f,at)&&API(ReadFile,RW)(f,out,n,&got,0)&&got==n;}
static U write_at(U at,void*in,U n){U got=0;return at<=CAPACITY104&&n<=CAPACITY104-at&&pos(carrier,at)&&API(WriteFile,RW)(carrier,in,n,&got,0)&&got==n;}
static U save(void){return write_at(0,&h,64)&&API(FlushFileBuffers,ONE)(carrier);}
static void hex(W*out,U n,U digits){static const W x[]=L"0123456789abcdef";while(digits){out[--digits]=x[n&15];n>>=4;}}
static U find_carrier(void){
 U dll=API(LoadLibraryW,U(*)(const W*))((const W*)L"pmcapi.dll");
 if(!dll)return 0;
 U proc=API(GetProcAddressW,U(*)(U,const W*))(dll,(const W*)L"PmcGetPath");
 if(!proc||(int)((U(*)(U,W*,U))proc)(4,root,260)<0)return 0;
 U len=0;while(len<260&&root[len])len++;if(!len||len>245)return 0;
 for(U attempt=0;attempt<2;attempt++){
  for(U i=0;i<len;i++)path[i]=root[i];
  U id=attempt?(expected.object&0x00ffffffu):expected.object;
  path[len]='\\';hex(path+len+1,id>>16,4);path[len+5]='\\';
  hex(path+len+6,(id>>8)&255,2);path[len+8]='\\';hex(path+len+9,id&255,2);
  path[len+11]='.';path[len+12]='b';path[len+13]='i';path[len+14]='n';path[len+15]=0;
  /* First inspect using read-only access. A mismatched file is never opened writable. */
  U f=API(CreateFileW,OPEN)(path,0x80000000,1,0,3,0x80,0);
  if(f==~0u)continue;
  U high=0,sz=API(GetFileSize,U(*)(U,U*))(f,&high);
  U ok=!high&&sz==CAPACITY104&&read_at(f,0,&h,64)&&same(&h,&expected,60);
  API(CloseHandle,ONE)(f);
  if(!ok)continue;
  carrier=API(CreateFileW,OPEN)(path,0xc0000000,0,0,3,0x80,0);
  if(carrier==~0u)return 0;
  high=0;sz=API(GetFileSize,U(*)(U,U*))(carrier,&high);
  /* Exclusive open, then repeat all validation to cover a change between opens. */
  if(!high&&sz==CAPACITY104&&read_at(carrier,0,&h,64)&&same(&h,&expected,60))return 1;
  API(CloseHandle,ONE)(carrier);carrier=~0u;return 0;
 }
 return 0;
}
static U copy_nk(void){
 U f=API(CreateFileW,OPEN)((const W*)L"\\Hard Disk\\nk.bin",0x80000000,1,0,3,0x80,0);
 if(f==~0u)return 10;
 U high=0,size=API(GetFileSize,U(*)(U,U*))(f,&high),error=0;
 if(high||size<39||size>CAPACITY104-64)error=11;
 if(!error&&(!read_at(f,0,buf,7)||!same(buf,"B000FF\n",7)))error=12;
 for(U at=0;!error&&at<size;){
  U n=size-at;if(n>32768)n=32768;
  if(!read_at(f,at,buf,n)||!read_at(f,at,buf+32768,n)||!same(buf,buf+32768,n)){error=13;break;}
  if(!read_at(carrier,64+at,buf+65536,n)){error=14;break;}
  for(U i=0;i<n;i++){h.checksum+=buf[i];buf[i]^=buf[65536+i];}
  if(!write_at(64+at,buf,n)){error=15;break;}
  at+=n;h.size=at;
 }
 API(CloseHandle,ONE)(f);return error;
}
__attribute__((section(".text.entry"))) void entry(void){
 API(SignalStarted,ONE)(85);API(Sleep,ONE)(2500);
 if(find_carrier()){
  h.state=1;h.permission=API(GetCurrentPermissions,U(*)(void))();
  if(save()){
   buf=(B*)API(LocalAlloc,U(*)(U,U))(0,98304);
   h.error=buf?copy_nk():16;h.state=h.error?3:2;save();
   if(buf)API(LocalFree,ONE)((U)buf);
  }
  API(CloseHandle,ONE)(carrier);
 }
 API(ExitThread,ONE)(0);
}
