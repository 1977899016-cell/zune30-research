    push {r0-r12, lr}
    sub sp, sp, #1536
    mvn r0, #0
    str r0, [sp, #1396]
    bl open_log194
    mov r0, #10
    bl stage194
    ldr r4, =0x01e661d0
    ldr r5, [r4, #0x18]
    mov r6, #0
    mov r8, #0
    mov r9, #0
    ldr r0, [r4, #0x1c]
    cmp r0, #65536
    movne r8, #1
    bne finish
    ldr r0, [r4, #0x14]
    ldr r1, =0x02fd46e4
    cmp r0, r1
    movne r8, #2
    bne finish
    ldr r0, =0x01e66e58
    ldr r0, [r0]
    add r0, r0, #0x1000
    ldr r0, [r0]
    and r1, r0, #31
    cmp r1, #10
    movne r8, #3
    bne finish
    tst r0, #0x40000
    movne r8, #3
    bne finish
    mov r0, #0
    mov r1, #65536
    bl #0x02fdb950
    movs r6, r0
    moveq r8, #4
    beq finish
    mov r1, r5
    mov r2, #65536
    bl #0x02fdba10
    mov r0, #20
    bl stage194
    ldr r0, =source_path
    mov r1, #0x80000000
    mov r2, #1
    mov r3, #0
    mov ip, #3
    str ip, [sp]
    mov ip, #0x80
    str ip, [sp, #4]
    str r3, [sp, #8]
    bl #0x02fdbad0
    mov r7, r0
    cmn r0, #1
    moveq r8, #13
    beq restore
    add r1, sp, #1392
    mov r0, #0
    str r0, [r1]
    mov r0, r7
    bl #0x02fdbb90
    cmp r0, #65536
    movne r8, #14
    bne source_close
    ldr r0, [sp, #1392]
    cmp r0, #0
    movne r8, #14
    bne source_close
    mov r0, r7
    mov r1, r5
    mov r2, #65536
    add r3, sp, #1392
    mov ip, #0
    str ip, [sp]
    bl #0x02fdbb80
    cmp r0, #0
    moveq r8, #15
    beq source_close
    ldr r0, [sp, #1392]
    cmp r0, #65536
    movne r8, #15
source_close:
    mov r0, r7
    bl #0x02fdbae0
    cmp r8, #0
    bne restore
    mov r0, #30
    bl stage194
    add r0, sp, #1408
    bl #0x02fd6c78
    add r0, sp, #1408
    mov r1, r5
    mov r2, #65536
    bl #0x02fd77c0
    add r0, sp, #1408
    mov r1, sp
    bl #0x02fd78b8
    mov r0, sp
    ldr r1, =expected_sha1
    mov r2, #20
    bl #0x02fdba90
    cmp r0, #0
    movne r8, #5
    bne restore
    add r0, sp, #1504
    mov r1, r5
    mov r2, #32
    mov r3, #0
    bl #0x02fc7360
    cmp r0, #0
    moveq r8, #10
    beq restore
    ldr r7, =regions
region_loop:
    ldr r0, =3000
    add r0, r0, r9
    bl stage194
    ldrh r0, [r7]
    ldrh r11, [r7, #2]
    add r10, r5, r0
    mov r0, sp
    mov r1, r10
    mov r2, r11
    mov r3, #0
    bl #0x02fc7360
    cmp r0, #0
    moveq r8, #6
    beq restore
    ldr r0, =4000
    add r0, r0, r9
    bl stage194
    mov r0, r10
    mov r1, sp
    mov r2, r11
    bl #0x02fc73ac
    cmp r0, #0
    moveq r8, #7
    beq restore
    ldr r0, =5000
    add r0, r0, r9
    bl stage194
    add r0, sp, #704
    mov r1, r10
    mov r2, r11
    bl #0x02fc73cc
    cmp r0, #0
    moveq r8, #8
    beq restore
    mov r0, sp
    add r1, sp, #704
    mov r2, r11
    bl #0x02fdba90
    cmp r0, #0
    movne r8, #9
    bne restore
    add r7, r7, #4
    add r9, r9, #1
    cmp r9, #38
    bne region_loop
    mov r0, sp
    add r1, sp, #1504
    mov r2, #32
    bl #0x02fdba10
    add r0, sp, #1408
    bl #0x02fd6c78
    add r0, sp, #1408
    add r1, sp, #28
    mov r2, #4
    bl #0x02fd77c0
    add r0, sp, #1408
    add r1, r5, #32
    ldr r2, =65504
    bl #0x02fd77c0
    mov r0, #11
    str r0, [sp, #1404]
    add r0, sp, #1408
    add r1, sp, #1408
    sub r1, r1, #4
    mov r2, #4
    bl #0x02fd77c0
    add r0, sp, #1408
    add r1, sp, #8
    bl #0x02fd78b8
    ldr r0, =6000
    bl stage194
    mov r0, r5
    mov r1, sp
    mov r2, #32
    bl #0x02fc73ac
    cmp r0, #0
    moveq r8, #11
    beq restore
    bl #0x02fc7510
    cmp r0, #0
    moveq r8, #12
    beq restore
    b finish
restore:
    mov r0, r5
    mov r1, r6
    mov r2, #65536
    bl #0x02fdba10
finish:
    bl #0x02fc7510
    str r0, [sp, #1536]
    mov r0, sp
    mov r1, #0
    mov r2, #64
    bl #0x02fdb9c0
    ldr r0, =0x36363141
    str r0, [sp, #16]
    mov r0, #166
    str r0, [sp, #20]
    str r8, [sp, #24]
    str r9, [sp, #28]
    add r0, sp, #32
    ldr r1, =token
    mov r2, #16
    bl #0x02fdba10
    add r0, sp, #1408
    bl #0x02fd6c78
    add r0, sp, #1408
    mov r1, r5
    mov r2, #65536
    bl #0x02fd77c0
    add r0, sp, #1408
    add r1, sp, #48
    bl #0x02fd78b8
    ldr r7, [sp, #1396]
    cmn r7, #1
    beq backup_cleanup
    mov r0, r7
    mov r1, #8
    mov r2, #0
    mov r3, #0
    ldr ip, =0x03f97774
    blx ip
    mov r0, r7
    add r1, sp, #16
    mov r2, #48
    add r3, sp, #64
    mov ip, #0
    str ip, [sp]
    bl #0x02fdbbc0
    cmp r0, #0
    beq close_file
    ldr r0, [sp, #64]
    cmp r0, #48
    bne close_file
    mov r0, r7
    mov r1, r5
    mov r2, #65536
    add r3, sp, #64
    mov ip, #0
    str ip, [sp]
    bl #0x02fdbbc0
    mov r0, r7
    bl #0x02fdbbb0
close_file:
    ldr r0, =999
    bl stage194
    mov r0, r7
    bl #0x02fdbae0
backup_cleanup:
    cmp r6, #0
    movne r0, r6
    blne #0x02fdb9e0
    mov r0, sp
    mov r1, #0
    mov r2, #1536
    bl #0x02fdb9c0
    add sp, sp, #1536
    pop {r0-r12, pc}
open_log194:
    push {r4, lr}
    sub sp, sp, #24
    ldr r0, =file_path
    mov r1, #0x40000000
    mov r2, #0
    mov r3, #0
    mov ip, #1
    str ip, [sp]
    mov ip, #0x80
    str ip, [sp, #4]
    str r3, [sp, #8]
    bl #0x02fdbad0
    mov r4, r0
    str r0, [sp, #1428]
    cmn r0, #1
    beq open_done194
    ldr r1, =0x34393141
    str r1, [sp, #12]
    mov r1, #1
    str r1, [sp, #16]
    mov r1, #0
    str r1, [sp]
    add r1, sp, #12
    mov r2, #8
    add r3, sp, #20
    bl #0x02fdbbc0
    mov r0, r4
    bl #0x02fdbbb0
open_done194:
    add sp, sp, #24
    pop {r4, pc}
stage194:
    push {r0-r3, ip, lr}
    sub sp, sp, #16
    ldr r0, [sp, #1436]
    cmn r0, #1
    beq stage_done194
    mov r1, #4
    mov r2, #0
    mov r3, #0
    ldr ip, =0x03f97774
    blx ip
    ldr r0, [sp, #1436]
    add r1, sp, #16
    mov r2, #4
    add r3, sp, #8
    mov ip, #0
    str ip, [sp]
    bl #0x02fdbbc0
    ldr r0, [sp, #1436]
    bl #0x02fdbbb0
stage_done194:
    add sp, sp, #16
    pop {r0-r3, ip, pc}
    .ltorg
expected_sha1:
    .space 20
token:
    .space 16
regions:
