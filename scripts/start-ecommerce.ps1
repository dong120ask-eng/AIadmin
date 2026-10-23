param(
    [string]$DataDir = (Join-Path $env:LOCALAPPDATA 'AIadmin\ecommerce-pilot'),
    [ValidateRange(1024,65535)][int]$Port = 8766,
    [switch]$NoBrowser,
    [switch]$CheckOnly,
    [ValidateRange(1,120)][int]$StartupTimeoutSeconds = 30,
    [string]$LogDir,
    # Optional local automation stop signal; no HTTP shutdown endpoint.
    [string]$StopFile
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONUNBUFFERED = '1'
$Root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$DataDir = [IO.Path]::GetFullPath($DataDir)
$ExitCode = 1
$Job = $null
$Child = $null
$LauncherLog = $null
$Pumps = @()
$Utf8 = New-Object Text.UTF8Encoding($false)

function Write-PilotLog([string]$Message) {
    Write-Host $Message
    if ($LauncherLog) {
        [IO.File]::AppendAllText($LauncherLog, "$(Get-Date -Format o) $Message`r`n", $Utf8)
    }
}

# PS5.1 has no ArgumentList. Windows CRT rules preserve trailing backslashes.
function Quote-PilotArgument([string]$Value) {
    $Escaped = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
    $Escaped = [regex]::Replace($Escaped, '(\\+)$', '$1$1')
    return '"' + $Escaped + '"'
}

function Start-PilotPython([string[]]$Arguments, [string]$Stdout, [string]$Stderr) {
    $Joined = (($PythonArgs + $Arguments) | ForEach-Object { Quote-PilotArgument $_ }) -join ' '
    # ProcessStartInfo treats paths literally; Start-Process may resolve [] as
    # PowerShell wildcards in a working directory. Keep native argv quoting.
    $Info = New-Object Diagnostics.ProcessStartInfo
    $Info.FileName = $PythonExe
    $Info.Arguments = $Joined
    $Info.WorkingDirectory = $Root
    $Info.UseShellExecute = $false
    $Info.CreateNoWindow = $true
    $Info.RedirectStandardOutput = $true
    $Info.RedirectStandardError = $true
    $Process = New-Object Diagnostics.Process
    $Process.StartInfo = $Info
    $OutStream = New-Object IO.FileStream($Stdout, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite, 1)
    $ErrStream = New-Object IO.FileStream($Stderr, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::ReadWrite, 1)
    $Started = $false
    try {
        [void]$Process.Start()
        $Started = $true
        [EcommercePilotJob]::Assign($Job, $Process.Handle)
        $script:Pumps += [pscustomobject]@{ Id=$Process.Id; Task=$Process.StandardOutput.BaseStream.CopyToAsync($OutStream); Stream=$OutStream }
        $script:Pumps += [pscustomobject]@{ Id=$Process.Id; Task=$Process.StandardError.BaseStream.CopyToAsync($ErrStream); Stream=$ErrStream }
    } catch {
        if ($Started -and -not $Process.HasExited) { $Process.Kill() }
        $OutStream.Dispose()
        $ErrStream.Dispose()
        throw
    }
    return $Process
}

try {
    if (-not $LogDir) { $LogDir = Join-Path $DataDir 'launcher-logs' }
    $LogDir = [IO.Path]::GetFullPath($LogDir)
    [IO.Directory]::CreateDirectory($LogDir) | Out-Null
    $Run = (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N')
    $LauncherLog = Join-Path $LogDir "$Run-launcher.log"
    $Stdout = Join-Path $LogDir "$Run-service.stdout.log"
    $Stderr = Join-Path $LogDir "$Run-service.stderr.log"
    Write-PilotLog "启动日志：$LauncherLog"
    # Prefer setup-python / the operator's PATH version over py -3's latest.
    if (Get-Command python -CommandType Application -ErrorAction SilentlyContinue) {
        $PythonExe = (Get-Command python -CommandType Application | Select-Object -First 1).Source
        $PythonArgs = @()
    } elseif (Get-Command py -CommandType Application -ErrorAction SilentlyContinue) {
        $PythonExe = (Get-Command py -CommandType Application | Select-Object -First 1).Source
        $PythonArgs = @('-3')
    } else { throw '请安装 Python 3.12 或更新版，并添加到 PATH 或启用 Python Launcher。' }

    if (-not ('EcommercePilotJob' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class EcommercePilotJob {
    [StructLayout(LayoutKind.Sequential)] struct Basic {
        public long ProcessTime, JobTime; public uint Flags;
        public UIntPtr MinWorkingSet, MaxWorkingSet; public uint ActiveProcesses;
        public UIntPtr Affinity; public uint Priority, Scheduling;
    }
    [StructLayout(LayoutKind.Sequential)] struct Io {
        public ulong ReadOps, WriteOps, OtherOps, ReadBytes, WriteBytes, OtherBytes;
    }
    [StructLayout(LayoutKind.Sequential)] struct Extended {
        public Basic Basic; public Io Io;
        public UIntPtr ProcessMemory, JobMemory, PeakProcessMemory, PeakJobMemory;
    }
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern SafeFileHandle CreateJobObject(IntPtr attributes, string name);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool SetInformationJobObject(SafeFileHandle job, int kind, ref Extended limits, uint size);
    [DllImport("kernel32.dll", SetLastError=true)]
    static extern bool AssignProcessToJobObject(SafeFileHandle job, IntPtr process);
    public static SafeFileHandle Create() {
        SafeFileHandle job = CreateJobObject(IntPtr.Zero, null);
        if (job.IsInvalid) throw new Win32Exception();
        Extended limits = new Extended(); limits.Basic.Flags = 0x2000;
        if (!SetInformationJobObject(job, 9, ref limits, (uint)Marshal.SizeOf(typeof(Extended)))) {
            int error = Marshal.GetLastWin32Error(); job.Dispose(); throw new Win32Exception(error);
        }
        return job;
    }
    public static void Assign(SafeFileHandle job, IntPtr process) {
        if (!AssignProcessToJobObject(job, process)) throw new Win32Exception();
    }
}
'@
    }
    Write-PilotLog "Python：$PythonExe"
    $Job = [EcommercePilotJob]::Create()
    $CheckOut = Join-Path $LogDir "$Run-check.stdout.log"
    $CheckErr = Join-Path $LogDir "$Run-check.stderr.log"
    $Child = Start-PilotPython @('-c', "import sys,sqlite3; assert sys.version_info >= (3,12), 'Requires Python 3.12+'; from workbench.ecommerce import TOOLS,QUALITY; print('Python ' + sys.version.split()[0] + ' / SQLite / offline modules OK')") $CheckOut $CheckErr
    if (-not $Child.WaitForExit(15000)) { throw '运行环境检查超时。' }
    foreach ($Pump in $Pumps) { $Pump.Task.Wait(5000) | Out-Null; $Pump.Stream.Dispose() }
    $Pumps = @()
    if ($Child.ExitCode -ne 0) { throw "运行环境检查失败，需要 Python 3.12+ 和完整源码。错误日志：$CheckErr" }
    Write-PilotLog ([IO.File]::ReadAllText($CheckOut, $Utf8).Trim())
    if ($CheckOnly) {
        Write-PilotLog '启动脚本检查通过，未启动服务器，未导入数据。'
        $ExitCode = 0
    } else {
        if ($StopFile -and (Test-Path -LiteralPath $StopFile)) { throw '停止信号文件已存在；请使用新的停止信号路径。' }
        $Listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, $Port)
        $Listener.ExclusiveAddressUse = $true
        try { $Listener.Start() } catch { throw "端口 $Port 已被占用，服务未启动。" } finally { $Listener.Stop() }
        $Child = Start-PilotPython @('-m', 'workbench.ecommerce', 'serve', '--data-dir', $DataDir, '--port', "$Port") $Stdout $Stderr
        Write-PilotLog "SERVICE_PID=$($Child.Id)"
        $Base = "http://127.0.0.1:$Port"
        $Deadline = [DateTime]::UtcNow.AddSeconds($StartupTimeoutSeconds)
        $Ready = $false
        while ([DateTime]::UtcNow -lt $Deadline) {
            if ($Child.HasExited) { throw "服务异常退出，退出码 $($Child.ExitCode)。错误日志：$Stderr" }
            # Only this child's post-bind message may authorize the HTTP probe.
            if ([IO.File]::Exists($Stdout) -and [IO.File]::ReadAllText($Stdout, $Utf8).Contains($Base)) {
                try {
                    $Response = Invoke-WebRequest -UseBasicParsing -Uri "$Base/api/ecommerce/config" -TimeoutSec 1
                    $Config = $Response.Content | ConvertFrom-Json
                    if ($Response.StatusCode -eq 200 -and $Config.token -and -not $Child.HasExited) { $Ready = $true; break }
                } catch { }
            }
            Start-Sleep -Milliseconds 100
        }
        if (-not $Ready) { throw "HTTP 就绪检查超时（$StartupTimeoutSeconds 秒）。错误日志：$Stderr" }
        Write-PilotLog "HTTP_READY=$Base"
        Write-PilotLog "数据目录：$DataDir；按 Ctrl+C 停止。备份前请先停服。"
        if (-not $NoBrowser) { Start-Process $Base }
        while (-not ($StopFile -and (Test-Path -LiteralPath $StopFile))) {
            if ($Child.HasExited) { throw "服务异常退出，退出码 $($Child.ExitCode)。错误日志：$Stderr" }
            Start-Sleep -Milliseconds 100
        }
        Write-PilotLog '收到本机停止信号。'
        $ExitCode = 0
    }
} catch {
    if (-not $LauncherLog) {
        $Fallback = Join-Path ([IO.Path]::GetTempPath()) 'AIadmin-ecommerce-logs'
        [IO.Directory]::CreateDirectory($Fallback) | Out-Null
        $LauncherLog = Join-Path $Fallback ([guid]::NewGuid().ToString('N') + '-launcher.log')
    }
    Write-PilotLog "启动或运行失败：$($_.Exception.Message)"
    Write-PilotLog "出错位置：$($_.InvocationInfo.PositionMessage)"
    Write-PilotLog "请检查端口和目录写权限。启动日志：$LauncherLog"
} finally {
    if ($Job) { $Job.Dispose() }
    if ($Child) {
        if (-not $Child.HasExited) { $Child.WaitForExit(5000) | Out-Null }
        $Child.Dispose()
    }
    foreach ($Pump in $Pumps) { $Pump.Task.Wait(5000) | Out-Null; $Pump.Stream.Dispose() }
    if ($LauncherLog) { Write-PilotLog "启动器结束，退出码 $ExitCode；所启动的服务进程已清理。" }
}
exit $ExitCode
