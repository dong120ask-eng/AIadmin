"""Native Tk desktop; workers never access Tk controls from background threads."""
import json
import queue as threadsafe
import threading
import tkinter as tk
from tkinter import ttk
from .manager import TENANT, understand
from .manager_voice import WindowsSpeech
from .store import Problem


def launch(queue, speech=None):
    speech = speech or WindowsSpeech()
    root = tk.Tk(); root.title('AIadmin · AI总经理（第一阶段原型）'); root.geometry('900x680')
    frame = ttk.Frame(root, padding=20); frame.pack(fill='both', expand=True)
    ttk.Label(frame, text='本地文件任务 · 文字入口始终可用', font=('', 16)).pack(anchor='w')
    ttk.Label(frame, text='格式：创建文件 hello.txt，内容为你好，AIadmin\n仅在新任务目录生成文本；模型费用未知。语音识别后须检查文字。').pack(anchor='w', pady=10)
    entry = tk.Text(frame, height=4); entry.pack(fill='x')
    entry.insert('1.0', '创建文件 hello.txt，内容为你好，AIadmin')
    authorized = tk.BooleanVar(); cost = tk.BooleanVar()
    ttk.Checkbutton(frame, text='授权执行队列中最早的一项本地文件任务（先检查下方任务内容）', variable=authorized).pack(anchor='w')
    ttk.Checkbutton(frame, text='允许本次使用现有Codex权益，接受费用未知', variable=cost).pack(anchor='w')
    row = ttk.Frame(frame); row.pack(fill='x', pady=8)
    output = tk.Text(frame, wrap='word'); output.pack(fill='both', expand=True)
    mailbox = threadsafe.Queue(); busy = False

    def show(value):
        output.delete('1.0', 'end'); output.insert('1.0', value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2))

    def background(work, kind='result'):
        nonlocal busy
        if busy: return
        busy = True
        def execute():
            try: mailbox.put((kind, work()))
            except Exception as error:
                mailbox.put(('error', str(error) if isinstance(error, Problem) else '操作失败；检查本机运行环境'))
        threading.Thread(target=execute, daemon=True).start()

    def submit():
        try:
            sentence = entry.get('1.0', 'end').strip()
            contract = understand(sentence)
            if not contract['executable']: raise Problem(contract['reason'])
            show(queue.submit(sentence)); authorized.set(False); cost.set(False)
        except Problem as error: show(str(error))

    def run():
        allow, fee = authorized.get(), cost.get()
        authorized.set(False); cost.set(False)
        background(lambda: queue.run_next(allow, fee))

    def poll():
        nonlocal busy
        try:
            kind, value = mailbox.get_nowait(); busy = False
            if kind == 'speech':
                entry.delete('1.0', 'end'); entry.insert('1.0', value)
                show('识别完成，请检查文字后点击“识别并登记”。')
            else: show(value)
        except threadsafe.Empty: pass
        root.after(100, poll)

    ttk.Button(row, text='语音输入', command=lambda: background(speech.listen, 'speech')).pack(side='left')
    ttk.Button(row, text='识别并登记', command=submit).pack(side='left')
    ttk.Button(row, text='执行最早任务', command=run).pack(side='left')
    ttk.Button(row, text='刷新状态', command=lambda: show(queue.tasks(TENANT))).pack(side='left')
    ttk.Button(row, text='恢复检查', command=lambda: show(queue.recover())).pack(side='left')
    def report():
        tasks = queue.tasks(TENANT)
        summary = '暂无任务' if not tasks else ('最新任务状态：' + tasks[-1]['state'] + '。' + (tasks[-1]['result'] or {}).get('summary', '尚未通过独立检查。'))
        background(lambda: speech.speak(summary))
    ttk.Button(row, text='语音汇报', command=report).pack(side='left')
    def close():
        if busy: show('任务执行中。请等待超时或完成后退出，避免状态未知。'); return
        root.destroy()
    root.protocol('WM_DELETE_WINDOW', close)
    show(queue.tasks(TENANT)); poll(); root.mainloop()
