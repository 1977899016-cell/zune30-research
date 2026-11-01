"""Tk interface. Actual device actions run in a serialized separate worker process."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import secrets
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser
from . import VERSION
from .storage import read_json, atomic_json, Session

HELP = 'https://github.com/1977899016-cell/zune30-research/blob/main/docs/zh-CN/assistant.md'
RECOVERY_HELP = ('1. 保持 USB 连接，顶部 HOLD 解锁。\n'
    '2. 按住“返回”，短按“播放”后松开播放，继续按返回约 20 秒。\n'
    '3. 黄色 Pyxis maintenance 出现后松开全部键。\n'
    '4. 只短按一次返回，进入“连接电脑恢复”画面。\n\n'
    '不要选择恢复出厂、格式化或初始化磁盘，不改 SIG。\n'
    '确认电脑官方 Zune 软件没有更新/同步任务，再退出它以释放 USB。\n\n'
    '进入恢复画面后点击“确定”，工具只写回这台机器的原始 NK。')

class Window:
    def __init__(self, folder, demo=False):
        self.folder, self.demo = Path(folder), demo
        self.folder.mkdir(parents=True, exist_ok=True)
        self.backup_root = self.folder / 'Backups'
        self.busy, self.current, self.events = False, {}, queue.Queue()
        self.root = tk.Tk()
        self.root.title('ZZ AUDIO · Zune 30 升级助手 ' + VERSION)
        height = min(800, self.root.winfo_screenheight() - 80)
        self.root.geometry('790x' + str(height)); self.root.minsize(700, min(600, height))
        self.root.configure(bg='#f3f5f8')
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        style = ttk.Style(self.root)
        if 'vista' in style.theme_names(): style.theme_use('vista')
        style.configure('TLabel', font=('Microsoft YaHei UI', 10))
        style.configure('TButton', font=('Microsoft YaHei UI', 10), padding=(10, 6))
        style.configure('Card.TFrame', background='white')
        style.configure('Card.TLabel', background='white')
        style.configure('Heading.TLabel', background='white', font=('Microsoft YaHei UI', 12, 'bold'))
        outer = ttk.Frame(self.root); outer.pack(fill='both', expand=True)
        canvas = tk.Canvas(outer, highlightthickness=0, bg='#f3f5f8')
        scrollbar = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y'); canvas.pack(side='left', fill='both', expand=True)
        main = ttk.Frame(canvas, padding=22)
        content = canvas.create_window((0, 0), window=main, anchor='nw')
        main.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(content, width=event.width))
        self.root.bind('<MouseWheel>', lambda event: canvas.yview_scroll(int(-event.delta / 120), 'units'))
        ttk.Label(main, text='Zune 30 升级助手', font=('Microsoft YaHei UI', 22, 'bold')).pack(anchor='w')
        ttk.Label(main, text='1.0 TEST → 3.3 兼容研究版  ·  ZZ AUDIO').pack(anchor='w', pady=(4, 10))
        notice = ('实验版 Alpha：已通过离线测试，尚未完成本工具的真机端到端验收。\n'
                  '只支持已核对的 30G TEST 构建；不修改启动器、SIG 或分区。')
        ttk.Label(main, text=notice, foreground='#9b5200', wraplength=710).pack(anchor='w', pady=(0, 12))
        self.device_text = tk.StringVar(value='尚未检查设备。请只连接一台 Zune，然后点击“检查连接”。')
        ttk.Label(main, textvariable=self.device_text, wraplength=700).pack(anchor='w', pady=(0, 10))
        self.inspect_button = self.card(main, '1  检查连接', '读取设备身份和固件版本，不安装任何程序。', '检查连接', self.inspect)
        self.backup_button = self.card(main, '2  备份原机', '自动分两轮读取原系统、完整闪存和硬盘前部；过程会重启。', '开始 / 继续备份', self.backup)
        self.upgrade_button = self.card(main, '3  准备并升级', '先选你已有的官方 3.3 NK/CAB；构建、校验后再确认安装。', '选择固件 / 升级', self.prepare_or_upgrade)
        self.experimental = tk.BooleanVar(value=False)
        ttk.Checkbutton(main, text='我了解这是实验版，并允许我点击的备份／升级／恢复步骤写入设备。',
                        variable=self.experimental, command=self.update_controls).pack(anchor='w', pady=(12, 8))
        self.status = tk.StringVar(value='就绪。首次升级前必须先完成原机备份和恢复验证。')
        ttk.Label(main, textvariable=self.status, wraplength=710).pack(anchor='w', pady=(2, 6))
        self.bar = ttk.Progressbar(main, mode='determinate', maximum=100)
        self.bar.pack(fill='x', pady=(0, 10))
        footer = ttk.Frame(main); footer.pack(fill='x')
        self.restore_button = ttk.Button(footer, text='恢复原系统 / 首次恢复验证', command=self.restore)
        self.restore_button.pack(side='left')
        ttk.Button(footer, text='打开私有备份', command=self.open_backups).pack(side='left', padx=6)
        ttk.Button(footer, text='使用说明', command=lambda: webbrowser.open(HELP)).pack(side='right')
        ttk.Label(main, text='备份和镜像只保存在本机，不上传到网络。黑屏时可能需要手动按键进入恢复画面。',
                  foreground='#657080', wraplength=710).pack(anchor='w', pady=(10, 0))
        cached = read_json(self.folder / 'last-device.PRIVATE.json', {})
        if cached:
            self.current = cached
            self.device_text.set('上次设备：' + cached.get('firmware', '') + '；请先重新检查连接。')
        self.checked = False
        self.update_controls()
        self.root.after(100, self.poll)
        if demo:
            self.status.set('演示预览：所有设备操作都已禁用，没有连接或读取 Zune。')

    def card(self, parent, title, description, action, command):
        frame = ttk.Frame(parent, style='Card.TFrame', padding=13)
        frame.pack(fill='x', pady=5)
        text = ttk.Frame(frame, style='Card.TFrame'); text.pack(side='left', fill='x', expand=True)
        ttk.Label(text, text=title, style='Heading.TLabel').pack(anchor='w')
        ttk.Label(text, text=description, style='Card.TLabel', wraplength=470).pack(anchor='w', pady=(3, 0))
        button = ttk.Button(frame, text=action, command=command); button.pack(side='right', padx=(10, 0))
        return button

    def update_controls(self):
        ready = not self.busy and not self.demo
        serial = bool(self.current.get('serial'))
        allow = ready and serial and self.experimental.get()
        self.inspect_button.state(['!disabled' if ready else 'disabled'])
        backup_ok = allow and self.checked and self.current.get('expected_backup_firmware', False)
        self.backup_button.state(['!disabled' if backup_ok else 'disabled'])
        upgrade_ok = allow and self.checked and self.current.get('backups_complete', False) and self.current.get('expected_backup_firmware', False)
        self.upgrade_button.state(['!disabled' if upgrade_ok else 'disabled'])
        self.restore_button.state(['!disabled' if allow and self.current.get('restore_available', False) else 'disabled'])

    def refresh_local(self):
        serial = self.current.get('serial')
        if serial:
            session = Session(self.backup_root, serial)
            self.current.update(backups_complete=session.data.get('backups_complete', False),
                prepared=session.data.get('prepared', False), recovery_verified=session.data.get('recovery_writeback_observed', False),
                workspace=str(session.root))
            try:
                session.verified_original_nk(); self.current['restore_available'] = True
            except ValueError:
                self.current['restore_available'] = False

    def inspect(self): self.start('inspect')

    def backup(self):
        question = ('USB 备份需要临时安装原生备份程序，将替换已有的 qtk.exe，并分两轮重启。\n'
            '旧 qtk.exe 本身无法在替换前通过此接口备份。\n\n'
            '备份程序只读取系统/闪存/硬盘源；它会写入自己的备份容器。\n'
            '本工具尚未完成真机端到端验收，失败可能需要手动恢复。\n\n开始或继续本机备份？')
        if messagebox.askokcancel('开始原机备份', question, parent=self.root): self.start('backup')

    def prepare_or_upgrade(self):
        self.refresh_local()
        if not self.current.get('recovery_verified'):
            messagebox.showinfo('先完成恢复验证', '备份已保存。首次升级前，请先点击“恢复原系统 / 首次恢复验证”，\n按提示进入恢复画面并写回原机系统。确认恢复可用后再升级。', parent=self.root)
            return
        if not self.current.get('prepared'):
            source = filedialog.askopenfilename(parent=self.root, title='选择你已有的官方 Zune 30G 3.30.39 NK 或 CAB', filetypes=[('固件 NK / CAB', '*.bin *.BIN *.cab *.CAB'), ('所有文件', '*.*')])
            if source: self.start('prepare', source)
            return
        text = ('将安装基于官方 3.3 的本机定制兼容镜像。它包含本机旧数据的开机 RAM 兼容逻辑，\n'
                '不是完全未修改的微软原版。\n\n原机备份已校验；可能黑屏，届时需要按键进入恢复画面。\n'
                '不改启动器、SIG 或分区。安装提交只发送一次。\n\n现在开始升级？')
        if messagebox.askokcancel('确认本次升级', text, parent=self.root): self.start('upgrade')

    def restore(self):
        if messagebox.askokcancel('先进入恢复画面', RECOVERY_HELP, parent=self.root): self.start('restore')

    def start(self, action, source=''):
        if self.busy or self.demo: return
        self.busy = True; self.last_action = action; self.last_result = None
        self.status.set('正在执行，请保持窗口和 USB 连接。'); self.bar['value'] = 0
        self.update_controls()
        command = [sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, '-X', 'utf8', '-B', str(Path(__file__).resolve().parents[1] / 'main.py')]
        command += ['--worker', action, '--backup-root', str(self.backup_root)]
        if self.current.get('serial'): command += ['--serial', self.current['serial']]
        if source: command += ['--source', source]
        ipc = self.folder / 'WorkerLogs' / ('operation-' + secrets.token_hex(8) + '.PRIVATE.jsonl')
        command += ['--ipc-file', str(ipc)]
        def work():
            try:
                process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                    encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                position = 0
                def drain():
                    nonlocal position
                    if not ipc.exists(): return
                    with ipc.open('r', encoding='utf-8') as stream:
                        stream.seek(position)
                        while True:
                            start = stream.tell(); line = stream.readline()
                            if not line or not line.endswith('\n'):
                                stream.seek(start); break
                            try: self.events.put(json.loads(line))
                            except ValueError: pass
                        position = stream.tell()
                while process.poll() is None:
                    drain(); time.sleep(0.15)
                drain()
                errors = process.stderr.read(); code = process.wait()
                if code and errors: self.events.put({'event': 'error', 'message': '工具运行异常；请保留本地日志。' + errors[-500:]})
                self.events.put({'event': 'finished', 'code': code})
            except Exception as exc:
                self.events.put({'event': 'error', 'message': str(exc)})
                self.events.put({'event': 'finished', 'code': 1})
        threading.Thread(target=work, daemon=True).start()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event['event'] == 'progress':
                    self.status.set(event['message'])
                    if event.get('percent') is not None: self.bar['value'] = event['percent']
                elif event['event'] == 'error':
                    self.status.set(event['message'])
                    messagebox.showerror('本次操作已停止', event['message'], parent=self.root)
                elif event['event'] == 'result':
                    result = event['result']; self.last_result = result
                    if self.last_action == 'inspect':
                        self.current = result; self.checked = True
                        atomic_json(self.folder / 'last-device.PRIVATE.json', result)
                        self.device_text.set('已连接：Zune  ·  固件 ' + result['firmware'] + '  ·  身份末尾 ' + result['serial'][-8:])
                        self.status.set('连接检查完成。' + ('可以开始备份。' if result['expected_backup_firmware'] else '当前版本仅开放检查或已有备份的恢复。'))
                    else:
                        if result.get('firmware'):
                            self.current['firmware'] = result['firmware']
                            self.current['expected_backup_firmware'] = result['firmware'] == '01.00.00186.00-02.04'
                        self.status.set(result.get('message', '完成'))
                        self.refresh_local()
                        messagebox.showinfo('本步骤结果', result.get('message', '完成'), parent=self.root)
                elif event['event'] == 'finished':
                    self.busy = False; self.refresh_local(); self.update_controls()
                    if event['code'] == 0 and self.last_action == 'prepare':
                        self.upgrade_button.configure(text='确认并安装升级')
                    elif self.last_action == 'upgrade' and self.last_result and self.last_result.get('needs_recovery'):
                        messagebox.showinfo('需要恢复引导', '工具未重复提交。请点击“恢复原系统”，按提示进入恢复画面。', parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def open_backups(self):
        path = Path(self.current.get('workspace', self.backup_root)); path.mkdir(parents=True, exist_ok=True)
        if os.name == 'nt': os.startfile(path)

    def close(self):
        if self.busy:
            messagebox.showwarning('操作进行中', '请等待本次操作结束再关闭窗口。安装提交不能通过强制退出安全取消。', parent=self.root)
            return
        self.root.destroy()
