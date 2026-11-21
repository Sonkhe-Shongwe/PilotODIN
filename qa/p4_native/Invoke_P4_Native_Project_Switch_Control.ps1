Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public static class P4DialogControls {
    private delegate bool WindowCallback(IntPtr window, IntPtr data);

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(WindowCallback callback, IntPtr data);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetWindowText(IntPtr window, StringBuilder text, int capacity);

    [DllImport("user32.dll")]
    private static extern bool EnumChildWindows(IntPtr parent, WindowCallback callback, IntPtr data);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern int GetClassName(IntPtr window, StringBuilder text, int capacity);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);

    [DllImport("user32.dll")]
    private static extern bool IsWindowEnabled(IntPtr window);

    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr window);

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    private static extern IntPtr SendMessageTimeout(
        IntPtr window, uint message, IntPtr wParam, StringBuilder text,
        uint flags, uint timeout, out IntPtr result);

    [DllImport("user32.dll", EntryPoint = "SendMessageTimeoutW")]
    private static extern IntPtr SendButtonMessage(
        IntPtr window, uint message, IntPtr wParam, IntPtr lParam,
        uint flags, uint timeout, out IntPtr result);

    public static IntPtr[] FindDialogs(uint expectedPid, out int appWindowCount) {
        var dialogs = new List<IntPtr>();
        int count = 0;
        EnumWindows((window, data) => {
            uint owner;
            GetWindowThreadProcessId(window, out owner);
            if (owner != expectedPid || !IsWindowVisible(window)) return true;
            count++;
            var title = new StringBuilder(256);
            GetWindowText(window, title, title.Capacity);
            if (title.ToString() == "PilotODIN - Unsaved changes") dialogs.Add(window);
            return true;
        }, IntPtr.Zero);
        appWindowCount = count;
        return dialogs.ToArray();
    }

    public static int TryClick(IntPtr dialog, uint expectedPid, string action, out int buttonCount) {
        uint owner;
        GetWindowThreadProcessId(dialog, out owner);
        if (owner != expectedPid) throw new InvalidOperationException("Dialog owner changed.");
        var stay = new List<IntPtr>();
        var change = new List<IntPtr>();
        int count = 0;
        EnumChildWindows(dialog, (window, data) => {
            uint childPid;
            GetWindowThreadProcessId(window, out childPid);
            var kind = new StringBuilder(256);
            GetClassName(window, kind, kind.Capacity);
            string className = kind.ToString();
            bool isButton = className == "Button" || className.StartsWith("WindowsForms10.BUTTON.", StringComparison.Ordinal);
            if (childPid != expectedPid || !isButton || !IsWindowVisible(window)) return true;
            count++;
            var label = new StringBuilder(256);
            IntPtr result;
            if (SendMessageTimeout(window, 0x000D, (IntPtr)label.Capacity, label, 2, 250, out result) == IntPtr.Zero)
                return true;
            if (label.ToString() == "Stay") stay.Add(window);
            if (label.ToString() == "Switch project") change.Add(window);
            return true;
        }, IntPtr.Zero);
        buttonCount = count;
        if (stay.Count > 1 || change.Count > 1) return -1;
        if (stay.Count != 1 || change.Count != 1) return 0;
        IntPtr button = action == "Stay" ? stay[0] : change[0];
        if (!IsWindowEnabled(button)) return 0;
        IntPtr click;
        if (SendButtonMessage(button, 0x00F5, IntPtr.Zero, IntPtr.Zero, 2, 1000, out click) == IntPtr.Zero)
            throw new InvalidOperationException("The native button did not acknowledge BM_CLICK.");
        return 1;
    }
}
'@

function Invoke-P4NativeProjectSwitchControl {
    param(
        [Parameter(Mandatory = $true)][int]$AppProcessId,
        [Parameter(Mandatory = $true)][ValidateSet('Stay', 'Switch project')][string]$Action,
        [ValidateRange(1, 12)][int]$TimeoutSeconds = 12
    )

    $stage = 'APP_WINDOW_NOT_VISIBLE'
    $appWindowCount = 0
    $nativeButtonCount = 0
    $deadline = [System.Diagnostics.Stopwatch]::StartNew()

    while ($deadline.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        $dialogs = [P4DialogControls]::FindDialogs([uint32]$AppProcessId, [ref]$appWindowCount)
        if ($dialogs.Count -gt 1) { throw 'DIALOG_AMBIGUOUS: multiple matching project-switch dialogs' }
        if ($dialogs.Count -eq 1) {
            $stage = 'DIALOG_FOUND_BUTTONS_MISSING'
            $click = [P4DialogControls]::TryClick($dialogs[0], [uint32]$AppProcessId, $Action, [ref]$nativeButtonCount)
            if ($click -lt 0) { throw 'BUTTONS_AMBIGUOUS: multiple matching native button handles' }
            if ($click -gt 0) {
                Write-Output 'Project-switch action delivered using native button handles'
                return
            }
        } elseif ($appWindowCount -gt 0 -and $stage -eq 'APP_WINDOW_NOT_VISIBLE') {
            $stage = 'APP_VISIBLE_DIALOG_MISSING'
        }
        Start-Sleep -Milliseconds 200
    }
    throw "Native project-switch discovery timed out. Stage=$stage; visible app window count=$appWindowCount; native button count=$nativeButtonCount"
}
