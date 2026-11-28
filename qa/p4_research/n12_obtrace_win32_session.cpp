// G2.25 dormant Windows source candidate, no executable entrypoint.
// No source path can start a session until a separate reviewed activation.
// Compilation alone cannot verify native capture or provider semantics.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <evntrace.h>
#include <evntprov.h>
#include <evntcons.h>
#include <tdh.h>
#include <array>
#include <cstdint>
#include <cstddef>
#include <climits>
#include <cwchar>

namespace pilotodin::g225 {
constexpr bool kNativeExecutionEnabled = false;
constexpr GUID kObTrace = {0x89497f50, 0xeffe, 0x4440,
                           {0x8c,0xf2,0xce,0x6b,0x1c,0xdc,0xac,0xa7}};
constexpr ULONG kMaxTraceMiB = 32;
constexpr ULONG kMaxBuffers = 64;

struct Properties {
    EVENT_TRACE_PROPERTIES props{};
    wchar_t logger[96]{};
    wchar_t filename[1024]{};
};

// No copy, no attachment to existing logger, no stop-by-name on collision.
// A future authorised caller must create a unique disposable runner path,
// check a fresh approval and implement bounded time + deletion on all exits.
class Session {
    Properties p_{};
    TRACEHANDLE owned_{};
public:
    Session() = default;
    Session(const Session&) = delete;
    Session& operator=(const Session&) = delete;
    ~Session() { if (owned_) (void)stop(); }

    ULONG start(const wchar_t* unique_name, const wchar_t* private_etl) {
        if (!kNativeExecutionEnabled) return ERROR_ACCESS_DISABLED_BY_POLICY;
        if (owned_ || !unique_name || !private_etl ||
            wcsncmp(unique_name, L"PilotODIN-G225-", 15) != 0 ||
            wcslen(unique_name) >= _countof(p_.logger) ||
            wcslen(private_etl) >= _countof(p_.filename))
            return ERROR_INVALID_PARAMETER;
        p_ = {};
        wcscpy_s(p_.logger, unique_name);
        wcscpy_s(p_.filename, private_etl);
        auto& p = p_.props;
        p.Wnode.BufferSize = static_cast<ULONG>(sizeof(p_));
        p.Wnode.Flags = WNODE_FLAG_TRACED_GUID;
        p.Wnode.ClientContext = 1;  // QPC; consumer must convert to shared system time.
        p.LogFileMode = EVENT_TRACE_SYSTEM_LOGGER_MODE | EVENT_TRACE_FILE_MODE_SEQUENTIAL;
        p.BufferSize = 64;
        p.MinimumBuffers = 8;
        p.MaximumBuffers = kMaxBuffers;
        p.MaximumFileSize = kMaxTraceMiB;
        p.LoggerNameOffset = static_cast<ULONG>(offsetof(Properties, logger));
        p.LogFileNameOffset = static_cast<ULONG>(offsetof(Properties, filename));
        TRACEHANDLE candidate{};
        const ULONG result = StartTraceW(&candidate, unique_name, &p);
        if (result != ERROR_SUCCESS) return result; // Includes collision; never stop it.
        owned_ = candidate;
        // SDK 20348+ system provider mapping; no classic provider GUID as a
        // manifest provider and no guessed numeric keyword.
        const ULONG enabled = EnableTraceEx2(owned_, &SystemObjectProviderGuid,
            EVENT_CONTROL_CODE_ENABLE_PROVIDER, TRACE_LEVEL_INFORMATION,
            SYSTEM_OBJECT_KW_HANDLE, 0, 0, nullptr);
        if (enabled != ERROR_SUCCESS) {
            const ULONG stopped = stop();
            return stopped == ERROR_SUCCESS ? enabled : stopped;
        }
        return ERROR_SUCCESS;
    }

    ULONG stop() {
        if (!owned_) return ERROR_INVALID_HANDLE;
        const ULONG result = ControlTraceW(owned_, nullptr, &p_.props,
                                            EVENT_TRACE_CONTROL_STOP);
        // Retain owned handle on failure for cleanup retry; never stop any
        // other trace or silently claim the trace is cleaned.
        if (result == ERROR_SUCCESS) owned_ = 0;
        return result;
    }
    const EVENT_TRACE_PROPERTIES& counters() const { return p_.props; }
};

// TDH obtains named property bytes; never parse guessed raw payload offsets.
// No ObjectName, path, PID, pointer or numeric handle is printed/persisted.
static bool property(PEVENT_RECORD record, const wchar_t* name, ULONG width,
                     std::uint64_t& value) {
    PROPERTY_DATA_DESCRIPTOR desc{};
    desc.PropertyName = reinterpret_cast<ULONGLONG>(name);
    desc.ArrayIndex = ULONG_MAX;
    ULONG size{};
    if (TdhGetPropertySize(record, 0, nullptr, 1, &desc, &size) != ERROR_SUCCESS ||
        size != width || width > 8) return false;
    std::array<BYTE, 8> bytes{};
    if (TdhGetProperty(record, 0, nullptr, 1, &desc, size, bytes.data()) != ERROR_SUCCESS)
        return false;
    value = 0;
    for (ULONG i = 0; i < size; ++i) value |= std::uint64_t(bytes[i]) << (8*i);
    return value != 0;
}

struct PrivateEvent {
    UCHAR opcode{};
    LONGLONG raw_timestamp{};
    ULONG header_pid{}, header_tid{};
    std::uint64_t object{}, type{}, handle{}, target_handle{}, target_pid{};
};

bool decode(PEVENT_RECORD record, PrivateEvent& out) {
    if (!record) return false;
    const auto& h = record->EventHeader;
    const auto op = h.EventDescriptor.Opcode;
    const bool b32 = (h.Flags & EVENT_HEADER_FLAG_32_BIT_HEADER) != 0;
    const bool b64 = (h.Flags & EVENT_HEADER_FLAG_64_BIT_HEADER) != 0;
    if (!IsEqualGUID(h.ProviderId, kObTrace) || h.EventDescriptor.Version != 2 ||
        !(h.Flags & EVENT_HEADER_FLAG_CLASSIC_HEADER) || b32 == b64 ||
        (op != 32 && op != 33 && op != 34) ||
        !h.ProcessId || !h.ThreadId || h.TimeStamp.QuadPart <= 0)
        return false;
    PrivateEvent e{};
    e.opcode = op;
    e.raw_timestamp = h.TimeStamp.QuadPart; // NOT converted or compared here.
    e.header_pid = h.ProcessId;
    e.header_tid = h.ThreadId;
    if (!property(record, L"Object", b32 ? 4 : 8, e.object) ||
        !property(record, L"ObjectType", 2, e.type)) return false;
    if (op == 34) {
        if (!property(record, L"SourceHandle", 4, e.handle) ||
            !property(record, L"TargetHandle", 4, e.target_handle) ||
            !property(record, L"TargetProcessId", 4, e.target_pid)) return false;
    } else if (!property(record, L"Handle", 4, e.handle)) return false;
    out = e;
    return true;
}
} // namespace pilotodin::g225
