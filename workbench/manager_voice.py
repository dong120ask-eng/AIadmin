"""Replaceable synchronous speech port. Windows installed voices/recognizers only."""
import os
import subprocess
from typing import Protocol
from .store import Problem


class SpeechPort(Protocol):
    def listen(self) -> str: ...
    def speak(self, message: str) -> None: ...


class WindowsSpeech:
    def _call(self, script, value=''):
        if os.name != 'nt':
            raise Problem('系统语音仅支持Windows；可继续使用文字入口')
        try:
            result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                                    input=value.encode('utf-8'), stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, timeout=40, shell=False)
        except (OSError, subprocess.SubprocessError):
            raise Problem('系统语音不可用或超时，请使用文字入口')
        if result.returncode:
            raise Problem('系统未安装可用的中文语音包或麦克风不可用')
        return result.stdout.decode('utf-8-sig', 'replace').strip()

    def listen(self):
        return self._call('''$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.Encoding]::UTF8;
Add-Type -AssemblyName System.Speech;
$r=New-Object System.Speech.Recognition.SpeechRecognitionEngine([Globalization.CultureInfo]::GetCultureInfo('zh-CN'));
try { $r.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar)); $r.SetInputToDefaultAudioDevice();
$x=$r.Recognize([TimeSpan]::FromSeconds(15)); if($null -eq $x){throw 'no speech'}; [Console]::Write($x.Text) } finally {$r.Dispose()}''')

    def speak(self, message):
        self._call('''$ErrorActionPreference='Stop'; [Console]::InputEncoding=[Text.Encoding]::UTF8;
Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer;
try {$s.Speak([Console]::In.ReadToEnd())} finally {$s.Dispose()}''', message)
