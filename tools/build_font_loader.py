"""Native CE font loader. Read/load font, signal init even on failure, exit.

Does not write registry, boot settings, system image, memory of other processes,
flash, hardware registers, or fuses. Startup wiring is a separate boot-registry
candidate; this script itself never communicates with a device.
"""
from pathlib import Path
import argparse,hashlib,json
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM,KS_MODE_LITTLE_ENDIAN
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
from ce_pe import BASE,CODE,DATA,make_imports,build
DEFAULT_FONT = r'\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf'
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coredll',type=Path,required=True,help='coredll.dll extracted from your own 3.30 firmware')
    parser.add_argument('--font-size',type=int,default=8206424)
    parser.add_argument('--output',type=Path,default=Path('generated/ZCJKBoot.exe'))
    args=parser.parse_args()
    if not 1<=args.font_size<=64*1024*1024:parser.error('Font size must be 1..64 MiB')
    if args.output.exists():parser.error('Refusing to overwrite existing output')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    names=['CreateFileW','GetFileSize','CloseHandle','AddFontResourceW','Sleep','SignalStarted','ExitThread']
    idata,iat,imports=make_imports(names,args.coredll)
    font=DEFAULT_FONT;data=(font+'\0').encode('utf-16-le')
    def call(name):return f'ldr ip, ={imports[name]}; ldr ip, [ip]; blx ip'
    asm=f'''
        push {{r4-r6, lr}}
        sub sp, sp, #16
        mov r4, #0
    attempt:
        ldr r0, ={BASE+DATA}
        mov r1, #0x80000000
        mov r2, #1
        mov r3, #0
        mov r5, #3
        str r5, [sp]
        mov r5, #0x80
        str r5, [sp, #4]
        mov r5, #0
        str r5, [sp, #8]
        {call('CreateFileW')}
        mov r6, r0
        cmn r6, #1
        beq retry
        mov r0, r6
        mov r1, #0
        {call('GetFileSize')}
        mov r5, r0
        mov r0, r6
        {call('CloseHandle')}
        ldr r0, ={args.font_size}
        cmp r5, r0
        bne finish
        ldr r0, ={BASE+DATA}
        {call('AddFontResourceW')}
        cmp r0, #0
        bgt finish
    retry:
        mov r0, #100
        {call('Sleep')}
        add r4, r4, #1
        ldr r0, =300
        cmp r4, r0
        blo attempt
    finish:
        mov r0, #45
        {call('SignalStarted')}
        mov r0, #0
        {call('ExitThread')}
        b finish
    '''
    machine=bytes(Ks(KS_ARCH_ARM,KS_MODE_ARM|KS_MODE_LITTLE_ENDIAN).asm(asm,BASE+CODE)[0])
    assert not any(i.mnemonic in ('movw','movt','udiv','sdiv') for i in Cs(CS_ARCH_ARM,CS_MODE_ARM).disasm(machine,BASE+CODE))
    blob=build(machine,data,idata,iat,len(names));path=args.output;path.write_bytes(blob)
    report={'scope':'Native font loader candidate only; startup firmware not installed','executable':str(path),'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'font_path':font,'font_size_guard':args.font_size,'startup_launch_number':45,'retry_delay_ms':100,'maximum_attempts':300,'signals_start_even_on_font_failure':True,'writes_registry':False,'writes_firmware':False,'requires_XNA_or_CLR':False,'physical_device_boot_verified':False}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
