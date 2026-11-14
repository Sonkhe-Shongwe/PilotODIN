// Decode classic x64 FileIO and StackWalk records into runner-temp rows.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <evntrace.h>
#include <evntcons.h>

#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
const GUID fileIo{0x90cbdc39, 0x4a3e, 0x11d1, {0x84, 0xf4, 0, 0, 0xf8, 4, 0x64, 0xe3}};
const GUID stackWalk{0xdef2fe46, 0x7bd6, 0x4b80, {0xbd, 0x94, 0xf5, 0x7f, 0xe2, 0x0d, 0x0c, 0xe3}};
const GUID image{0x2cb15d1d, 0x5fc1, 0x11d2, {0xab, 0xe1, 0, 0xa0, 0xc9, 0x11, 0xf5, 0x18}};
const GUID process{0x3d6fa8d0, 0xfe05, 0x11d0, {0x9d, 0xda, 0, 0xc0, 0x4f, 0xd7, 0xba, 0x7c}};
const GUID thread{0x3d6fa8d1, 0xfe05, 0x11d0, {0x9d, 0xda, 0, 0xc0, 0x4f, 0xd7, 0xba, 0x7c}};

struct Context {
    std::ofstream rows;
    unsigned lost = 0;
    unsigned decodeErrors = 0;
    unsigned stackKeyRecords = 0;
};

template <typename T>
T field(const EVENT_RECORD& record, size_t offset) {
    if (offset + sizeof(T) > record.UserDataLength) {
        throw std::runtime_error("short ETW field");
    }
    T value{};
    std::memcpy(&value, static_cast<const BYTE*>(record.UserData) + offset, sizeof(value));
    return value;
}

std::string trace_text(const EVENT_RECORD& record, size_t offset) {
    std::wstring value;
    for (; offset + sizeof(wchar_t) <= record.UserDataLength; offset += sizeof(wchar_t)) {
        const auto ch = field<wchar_t>(record, offset);
        if (!ch) {
            break;
        }
        if (ch < L' ') {
            return {};
        }
        value += ch;
    }
    if (value.empty()) {
        return {};
    }
    const auto length = static_cast<int>(value.size());
    const int count = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(), length,
                                          nullptr, 0, nullptr, nullptr);
    if (count <= 0) {
        return {};
    }
    std::string result(static_cast<size_t>(count), '\0');
    if (WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(), length,
                            result.data(), count, nullptr, nullptr) != count) {
        return {};
    }
    return result;
}

void decode_file(const EVENT_RECORD& record, std::ostream& rows) {
    const auto& header = record.EventHeader;
    const auto opcode = header.EventDescriptor.Opcode;
    const auto version = header.EventDescriptor.Version;
    const auto stamp = header.TimeStamp.QuadPart;
    if (opcode == 0 || opcode == 32 || opcode == 36) {
        const auto path = trace_text(record, 8);
        if (!path.empty()) {
            rows << "name\t" << field<std::uint64_t>(record, 0) << '\t' << path << '\n';
        }
        return;
    }
    if (opcode == 76) {
        const auto irp = field<std::uint64_t>(record, 0);
        const auto status = field<std::uint32_t>(record, 16);
        rows << "end\t" << stamp << '\t' << irp << '\t' << status << '\n';
        return;
    }
    if (opcode < 64 || opcode > 77) {
        return;
    }
    const bool readWrite = opcode == 67 || opcode == 68;
    const auto irp = field<std::uint64_t>(record, readWrite ? 8 : 0);
    if (opcode != 68 && opcode != 69 && opcode != 73) {
        rows << "other\t" << stamp << '\t' << irp << '\n';
        return;
    }
    if (version != 2 && version != 3) {
        throw std::runtime_error("unexpected classic FileIO version");
    }
    const size_t objectOffset = readWrite ? (version == 2 ? 24 : 16) : (version == 2 ? 16 : 8);
    const auto object = field<std::uint64_t>(record, objectOffset);
    const auto key = field<std::uint64_t>(record, objectOffset + 8);
    const size_t threadOffset = version == 2 ? (readWrite ? 16 : 8)
                                              : (opcode == 73 ? 24 : 32);
    const auto issuing = field<std::uint32_t>(record, threadOffset);
    const auto detail = opcode == 73 ? 0 : field<std::uint32_t>(record,
        version == 2 ? 40 : 36);
    const auto flags = readWrite ? field<std::uint32_t>(record, version == 2 ? 44 : 40) : 0;
    const auto offset = readWrite ? field<std::uint64_t>(record, 0) : 0;
    rows << "request\t" << stamp << '\t' << static_cast<unsigned>(opcode)
         << '\t' << header.ProcessId << '\t' << header.ThreadId << '\t' << issuing
         << '\t' << irp << '\t' << key << '\t' << object << '\t' << detail
         << '\t' << flags << '\t' << offset << '\n';
}

void WINAPI event_callback(PEVENT_RECORD record) {
    auto& context = *static_cast<Context*>(record->UserContext);
    auto& rows = context.rows;
    const auto& header = record->EventHeader;
    const auto& provider = header.ProviderId;
    const auto opcode = header.EventDescriptor.Opcode;
    const auto stamp = header.TimeStamp.QuadPart;
    try {
        if (provider == fileIo) {
            decode_file(*record, rows);
        } else if (provider == stackWalk && opcode == 32) {
            if (record->UserDataLength <= 16 || (record->UserDataLength - 16) % 8) {
                throw std::runtime_error("unexpected x64 StackWalk length");
            }
            rows << "stack\t" << field<std::uint64_t>(*record, 0) << '\t'
                 << field<std::uint32_t>(*record, 8) << '\t' << field<std::uint32_t>(*record, 12);
            for (size_t offset = 16; offset < record->UserDataLength; offset += 8) {
                rows << '\t' << field<std::uint64_t>(*record, offset);
            }
            rows << '\n';
        } else if (provider == stackWalk && (opcode == 37 || opcode == 38)) {
            const auto original = field<std::uint64_t>(*record, 0);
            const auto pid = field<std::uint32_t>(*record, 8);
            const auto tid = field<std::uint32_t>(*record, 12);
            const auto key = field<std::uint64_t>(*record, 16);
            rows << "reference\t" << original << '\t' << pid << '\t' << tid << '\t'
                 << static_cast<unsigned>(opcode) << '\t' << key << '\n';
            ++context.stackKeyRecords;
        } else if (provider == stackWalk && (opcode == 35 || opcode == 36)) {
            if (record->UserDataLength <= 8 || record->UserDataLength % 8) {
                throw std::runtime_error("unexpected x64 stack definition length");
            }
            rows << "definition\t" << field<std::uint64_t>(*record, 0);
            for (size_t offset = 8; offset < record->UserDataLength; offset += 8) {
                rows << '\t' << field<std::uint64_t>(*record, offset);
            }
            rows << '\n';
            ++context.stackKeyRecords;
        } else if (provider == process && opcode >= 1 && opcode <= 4 && header.EventDescriptor.Version >= 1) {
            rows << "process\t" << stamp << '\t' << static_cast<unsigned>(opcode) << '\t'
                 << field<std::uint32_t>(*record, 8) << '\n';
        } else if (provider == thread && opcode >= 1 && opcode <= 4 && header.EventDescriptor.Version >= 1) {
            rows << "thread\t" << stamp << '\t' << static_cast<unsigned>(opcode) << '\t'
                 << field<std::uint32_t>(*record, 0) << '\t' << field<std::uint32_t>(*record, 4) << '\n';
        } else if (provider == image && header.EventDescriptor.Version >= 2 &&
                   (opcode == 2 || opcode == 3 || opcode == 4 || opcode == 10)) {
            const auto path = trace_text(*record, 56);
            const auto base = field<std::uint64_t>(*record, 0);
            const auto size = field<std::uint64_t>(*record, 8);
            const auto pid = field<std::uint32_t>(*record, 16);
            if (!path.empty() && base && size) {
                rows << "image\t" << stamp << '\t' << static_cast<unsigned>(opcode) << '\t'
                     << pid << '\t' << base << '\t' << size << '\t' << path << '\n';
            }
        }
    } catch (const std::exception&) {
        ++context.decodeErrors;
    }
}

ULONG WINAPI buffer_callback(PEVENT_TRACE_LOGFILEW trace) {
    auto& context = *static_cast<Context*>(trace->Context);
    if (trace->EventsLost > context.lost) {
        context.lost = trace->EventsLost;
    }
    return TRUE;
}
}  // namespace

int wmain(int argc, wchar_t** argv) {
    if (argc != 3) {
        return 2;
    }
    Context context;
    context.rows.open(std::filesystem::path(argv[2]), std::ios::binary);
    if (!context.rows) {
        return 3;
    }
    EVENT_TRACE_LOGFILEW trace{};
    trace.LogFileName = argv[1];
    trace.ProcessTraceMode = PROCESS_TRACE_MODE_EVENT_RECORD | PROCESS_TRACE_MODE_RAW_TIMESTAMP;
    trace.EventRecordCallback = event_callback;
    trace.BufferCallback = buffer_callback;
    trace.Context = &context;
    TRACEHANDLE handle = OpenTraceW(&trace);
    if (handle == INVALID_PROCESSTRACE_HANDLE) {
        return 4;
    }
    const auto status = ProcessTrace(&handle, 1, nullptr, nullptr);
    CloseTrace(handle);
    context.rows.close();
    std::cout << "{\"events_lost\":" << context.lost
              << ",\"header_events_lost\":" << trace.LogfileHeader.EventsLost
              << ",\"buffers_lost\":" << trace.LogfileHeader.BuffersLost
              << ",\"decode_errors\":" << context.decodeErrors
              << ",\"stack_key_records\":" << context.stackKeyRecords
              << ",\"pointer_size\":" << trace.LogfileHeader.PointerSize << "}\n";
    return status == ERROR_SUCCESS && context.rows ? 0 : 5;
}
