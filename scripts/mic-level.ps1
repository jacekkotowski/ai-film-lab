# Windows microphone level: read it, or set it.
#
#   powershell -File scripts\mic-level.ps1                 set it to 85 %
#   powershell -File scripts\mic-level.ps1 -Set 80         set it to 80 %
#   powershell -File scripts\mic-level.ps1 -ReadOnly       only show it
#
# Works on the DEFAULT recording device -- the one Windows shows with the
# green tick in the Recording tab. Not part of ffilm/; it changes nothing
# in the film, only the Windows slider that conferencing apps also move.
param([int]$Set = 85, [switch]$ReadOnly)

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

[StructLayout(LayoutKind.Sequential)] public struct PropertyKey { public Guid fmtid; public uint pid; }
[StructLayout(LayoutKind.Sequential)] public struct PropVariant { public ushort vt; ushort r1, r2, r3; public IntPtr p; public IntPtr p2; }

[ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDeviceEnumerator {
    int EnumAudioEndpoints(int flow, int mask, out IntPtr devices);
    int GetDefaultAudioEndpoint(int flow, int role, out IMMDevice device);
}
[ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IMMDevice {
    int Activate(ref Guid iid, int ctx, IntPtr p, [MarshalAs(UnmanagedType.IUnknown)] out object o);
    int OpenPropertyStore(int access, out IPropertyStore store);
}
[ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IPropertyStore {
    int GetCount(out uint n);
    int GetAt(uint i, out PropertyKey k);
    int GetValue(ref PropertyKey k, out PropVariant v);
}
[ComImport, Guid("5CDF2C82-841E-4546-9722-0CF74078229A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IAudioEndpointVolume {
    int RegisterControlChangeNotify(IntPtr n);
    int UnregisterControlChangeNotify(IntPtr n);
    int GetChannelCount(out uint n);
    int SetMasterVolumeLevel(float db, ref Guid ctx);
    int SetMasterVolumeLevelScalar(float level, ref Guid ctx);
    int GetMasterVolumeLevel(out float db);
    int GetMasterVolumeLevelScalar(out float level);
}
[ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")] public class MMDeviceEnumerator { }

public static class Mic {
    static IMMDevice Device() {
        IMMDevice d;
        // flow 1 = capture, role 0 = console
        ((IMMDeviceEnumerator)new MMDeviceEnumerator()).GetDefaultAudioEndpoint(1, 0, out d);
        return d;
    }
    public static string Name() {
        IPropertyStore s; Device().OpenPropertyStore(0, out s);
        var key = new PropertyKey { fmtid = new Guid("A45C254E-DF1C-4EFD-8020-67D146A850E0"), pid = 14 };
        PropVariant v; s.GetValue(ref key, out v);
        return Marshal.PtrToStringUni(v.p);
    }
    static IAudioEndpointVolume Volume() {
        var iid = typeof(IAudioEndpointVolume).GUID; object o;
        Device().Activate(ref iid, 23, IntPtr.Zero, out o);
        return (IAudioEndpointVolume)o;
    }
    public static float Get() { float l; Volume().GetMasterVolumeLevelScalar(out l); return l; }
    public static void Set(float level) { var g = Guid.Empty; Volume().SetMasterVolumeLevelScalar(level, ref g); }
}
'@

"Device : $([Mic]::Name())"
"Level  : $([math]::Round([Mic]::Get() * 100)) %"
if (-not $ReadOnly) {
    if ($Set -lt 0 -or $Set -gt 100) { throw "level must be 0-100" }
    [Mic]::Set($Set / 100.0)
    "Now    : $([math]::Round([Mic]::Get() * 100)) %"
}
