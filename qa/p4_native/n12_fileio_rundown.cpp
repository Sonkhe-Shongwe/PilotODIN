// Native ETW consumer for the classic Kernel FileIo FileRundown event.
// FileIo_Name opcode 36 carries the file-name key and a UTF-16 path. Raw
// captures and decoded paths remain confined to the disposable runner temp.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <evntrace.h>
#include <evntcons.h>
#include <tdh.h>

#include <algorithm>
#include <climits>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <filesystem>
#include <cwchar>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <mutex>
#include <sstream>
#include <string>
#include <vector>
#include <utility>

namespace {
constexpr ULONG kRundownOpcode = 36;
constexpr ULONG kMaxPropertyBytes = 1024 * 1024;
const GUID kFileIoProvider = {
    0x90cbdc39, 0x4a3e, 0x11d1,
    {0x84, 0xf4, 0x00, 0x00, 0xf8, 0x04, 0x64, 0xe3}
};

struct DecodedName {
    std::uint64_t key = 0;
    std::wstring path;
};

struct Context {
    std::ofstream output;
    std::mutex mutex;
    ULONG tracePointerSize = 0;
    ULONGLONG classicFileEvents = 0;
    ULONGLONG rundownEvents = 0;
    ULONGLONG classicHeaderEvents = 0;
    ULONGLONG metadataSuccess = 0;
    ULONGLONG metadataFailure = 0;
    ULONGLONG tdhKeyPropertySuccess = 0;
    ULONGLONG tdhNamePropertySuccess = 0;
    ULONGLONG tdhRecords = 0;
    ULONGLONG rawSchemaRecords = 0;
    ULONGLONG decoderConflicts = 0;
    ULONGLONG undecodedRecords = 0;
    ULONGLONG invalidUtf8Records = 0;
    ULONGLONG callbackErrors = 0;
    ULONG minimumPayload = std::numeric_limits<ULONG>::max();
    ULONG maximumPayload = 0;
    std::map<ULONG, ULONGLONG> metadataStatuses;
    std::map<ULONG, ULONGLONG> keyStatuses;
    std::map<ULONG, ULONGLONG> nameStatuses;
    std::map<ULONG, ULONGLONG> pointerSizes;
    std::map<ULONG, ULONGLONG> versions;
    std::map<std::string, ULONGLONG> decoderSources;
};

bool reasonable_path(const std::wstring& path) {
    if (path.size() < 3 || path.front() != L'\\') {
        return false;
    }
    return std::none_of(path.begin(), path.end(), [](wchar_t ch) {
        return ch < 0x20;
    });
}

bool read_key_bytes(const std::vector<BYTE>& bytes, std::uint64_t& key) {
    if (bytes.size() == sizeof(std::uint32_t)) {
        std::uint32_t value = 0;
        std::memcpy(&value, bytes.data(), sizeof(value));
        key = value;
    } else if (bytes.size() == sizeof(std::uint64_t)) {
        std::uint64_t value = 0;
        std::memcpy(&value, bytes.data(), sizeof(value));
        key = value;
    } else {
        return false;
    }
    return key != 0;
}

bool read_wide_string_bytes(const std::vector<BYTE>& bytes, std::wstring& path) {
    if (bytes.size() < sizeof(wchar_t) || bytes.size() % sizeof(wchar_t) != 0) {
        return false;
    }
    const auto* chars = reinterpret_cast<const wchar_t*>(bytes.data());
    const std::size_t capacity = bytes.size() / sizeof(wchar_t);
    std::size_t length = 0;
    while (length < capacity && chars[length] != L'\0') {
        ++length;
    }
    if (length == 0 || length == capacity) {
        return false;
    }
    path.assign(chars, length);
    return reasonable_path(path);
}

bool to_utf8(const std::wstring& value, std::string& result) {
    if (value.empty() || value.size() > static_cast<std::size_t>(INT_MAX)) {
        return false;
    }
    const int required = WideCharToMultiByte(
        CP_UTF8, WC_ERR_INVALID_CHARS, value.data(), static_cast<int>(value.size()),
        nullptr, 0, nullptr, nullptr);
    if (required <= 0) {
        return false;
    }
    result.resize(static_cast<std::size_t>(required));
    return WideCharToMultiByte(
        CP_UTF8, WC_ERR_INVALID_CHARS, value.data(), static_cast<int>(value.size()),
        result.data(), required, nullptr, nullptr) == required;
}

std::string json_escape(const std::string& value) {
    std::ostringstream escaped;
    for (unsigned char ch : value) {
        switch (ch) {
        case '"': escaped << "\\\""; break;
        case '\\': escaped << "\\\\"; break;
        case '\b': escaped << "\\b"; break;
        case '\f': escaped << "\\f"; break;
        case '\n': escaped << "\\n"; break;
        case '\r': escaped << "\\r"; break;
        case '\t': escaped << "\\t"; break;
        default:
            if (ch < 0x20) {
                escaped << "\\u00" << std::hex << std::setw(2)
                        << std::setfill('0') << static_cast<unsigned int>(ch)
                        << std::dec;
            } else {
                escaped << static_cast<char>(ch);
            }
        }
    }
    return escaped.str();
}

ULONG get_property(
    PEVENT_RECORD event,
    PTDH_CONTEXT tdhContext,
    const wchar_t* propertyName,
    std::vector<BYTE>& value) {
    PROPERTY_DATA_DESCRIPTOR descriptor{};
    descriptor.PropertyName = reinterpret_cast<ULONGLONG>(propertyName);
    descriptor.ArrayIndex = std::numeric_limits<ULONG>::max();
    descriptor.Reserved = 0;

    ULONG size = 0;
    ULONG status = TdhGetPropertySize(
        event, 1, tdhContext, 1, &descriptor, &size);
    if (status != ERROR_SUCCESS) {
        return status;
    }
    if (size == 0 || size > kMaxPropertyBytes) {
        return ERROR_INVALID_DATA;
    }

    value.resize(size);
    status = TdhGetProperty(
        event, 1, tdhContext, 1, &descriptor, size, value.data());
    if (status != ERROR_SUCCESS) {
        value.clear();
    }
    return status;
}

bool decode_tdh(PEVENT_RECORD event, ULONG pointerSize, Context& context,
                DecodedName& decoded) {
    TDH_CONTEXT tdhContext{};
    tdhContext.ParameterValue = pointerSize;
    tdhContext.ParameterType = TDH_CONTEXT_POINTERSIZE;
    tdhContext.ParameterSize = 0;

    ULONG metadataSize = 0;
    ULONG metadataStatus = TdhGetEventInformation(
        event, 1, &tdhContext, nullptr, &metadataSize);
    if (metadataStatus == ERROR_INSUFFICIENT_BUFFER && metadataSize > 0 &&
        metadataSize <= kMaxPropertyBytes) {
        std::vector<BYTE> metadata(metadataSize);
        metadataStatus = TdhGetEventInformation(
            event, 1, &tdhContext,
            reinterpret_cast<PTRACE_EVENT_INFO>(metadata.data()), &metadataSize);
    }
    context.metadataStatuses[metadataStatus]++;
    if (metadataStatus == ERROR_SUCCESS) {
        ++context.metadataSuccess;
    } else {
        ++context.metadataFailure;
    }

    std::vector<BYTE> keyBytes;
    const ULONG keyStatus = get_property(event, &tdhContext, L"FileObject", keyBytes);
    context.keyStatuses[keyStatus]++;
    if (keyStatus == ERROR_SUCCESS) {
        ++context.tdhKeyPropertySuccess;
    }

    std::vector<BYTE> nameBytes;
    const ULONG nameStatus = get_property(event, &tdhContext, L"FileName", nameBytes);
    context.nameStatuses[nameStatus]++;
    if (nameStatus == ERROR_SUCCESS) {
        ++context.tdhNamePropertySuccess;
    }

    return keyStatus == ERROR_SUCCESS && nameStatus == ERROR_SUCCESS &&
           read_key_bytes(keyBytes, decoded.key) &&
           read_wide_string_bytes(nameBytes, decoded.path);
}

bool decode_raw_at_width(
    PEVENT_RECORD event, ULONG width, DecodedName& decoded) {
    if (event->UserData == nullptr || (width != 4 && width != 8) ||
        event->UserDataLength <= width + sizeof(wchar_t)) {
        return false;
    }

    const auto* payload = static_cast<const BYTE*>(event->UserData);
    if (width == 4) {
        std::uint32_t key = 0;
        std::memcpy(&key, payload, sizeof(key));
        decoded.key = key;
    } else {
        std::uint64_t key = 0;
        std::memcpy(&key, payload, sizeof(key));
        decoded.key = key;
    }
    if (decoded.key == 0) {
        return false;
    }

    bool terminated = false;
    for (std::size_t offset = width;
         offset + sizeof(wchar_t) <= event->UserDataLength;
         offset += sizeof(wchar_t)) {
        wchar_t ch = L'\0';
        std::memcpy(&ch, payload + offset, sizeof(ch));
        if (ch == L'\0') {
            terminated = true;
            break;
        }
        decoded.path.push_back(ch);
    }
    return terminated && reasonable_path(decoded.path);
}

bool decode_raw_schema(
    PEVENT_RECORD event, ULONG pointerSize, DecodedName& decoded) {
    // The documented FileIo_Name MOF layout is a pointer-qualified file key
    // followed by a null-terminated UTF-16 FileName. Only use this fallback
    // for the known FileIo_Name version, and reject ambiguous field offsets.
    if (event->EventHeader.EventDescriptor.Version != 2 ||
        (pointerSize != 4 && pointerSize != 8)) {
        return false;
    }

    std::vector<ULONG> widths{pointerSize};
    if (pointerSize == 8) {
        widths.push_back(4);
    }

    std::vector<DecodedName> candidates;
    for (ULONG width : widths) {
        DecodedName candidate;
        if (decode_raw_at_width(event, width, candidate)) {
            candidates.push_back(std::move(candidate));
        }
    }
    if (candidates.empty()) {
        return false;
    }
    for (std::size_t index = 1; index < candidates.size(); ++index) {
        if (candidates[index].key != candidates[0].key ||
            _wcsicmp(candidates[index].path.c_str(), candidates[0].path.c_str()) != 0) {
            return false;
        }
    }
    decoded = std::move(candidates[0]);
    return true;
}

void emit_numeric_map(const std::map<ULONG, ULONGLONG>& values) {
    std::cout << "{";
    bool first = true;
    for (const auto& item : values) {
        if (!first) std::cout << ",";
        first = false;
        std::cout << "\"" << item.first << "\":" << item.second;
    }
    std::cout << "}";
}

void emit_string_map(const std::map<std::string, ULONGLONG>& values) {
    std::cout << "{";
    bool first = true;
    for (const auto& item : values) {
        if (!first) std::cout << ",";
        first = false;
        std::cout << "\"" << item.first << "\":" << item.second;
    }
    std::cout << "}";
}

void print_summary(const Context& context, ULONG processStatus, ULONG closeStatus) {
    const ULONG minimumPayload =
        context.rundownEvents == 0 ? 0 : context.minimumPayload;
    std::cout
        << "{\"classic_file_events\":" << context.classicFileEvents
        << ",\"rundown_opcode_36\":" << context.rundownEvents
        << ",\"classic_header_events\":" << context.classicHeaderEvents
        << ",\"trace_pointer_size\":" << context.tracePointerSize
        << ",\"payload_bytes_min\":" << minimumPayload
        << ",\"payload_bytes_max\":" << context.maximumPayload
        << ",\"tdh_metadata_success\":" << context.metadataSuccess
        << ",\"tdh_metadata_failure\":" << context.metadataFailure
        << ",\"tdh_file_object_property_success\":" << context.tdhKeyPropertySuccess
        << ",\"tdh_file_name_property_success\":" << context.tdhNamePropertySuccess
        << ",\"tdh_records_written\":" << context.tdhRecords
        << ",\"raw_schema_records_written\":" << context.rawSchemaRecords
        << ",\"decoder_conflicts\":" << context.decoderConflicts
        << ",\"undecoded_records\":" << context.undecodedRecords
        << ",\"invalid_utf8_records\":" << context.invalidUtf8Records
        << ",\"callback_errors\":" << context.callbackErrors
        << ",\"process_trace_status\":" << processStatus
        << ",\"close_trace_status\":" << closeStatus
        << ",\"metadata_statuses\":";
    emit_numeric_map(context.metadataStatuses);
    std::cout << ",\"file_object_statuses\":";
    emit_numeric_map(context.keyStatuses);
    std::cout << ",\"file_name_statuses\":";
    emit_numeric_map(context.nameStatuses);
    std::cout << ",\"pointer_sizes\":";
    emit_numeric_map(context.pointerSizes);
    std::cout << ",\"event_versions\":";
    emit_numeric_map(context.versions);
    std::cout << ",\"decoder_sources\":";
    emit_string_map(context.decoderSources);
    std::cout << "}" << std::endl;
}

void WINAPI on_event(PEVENT_RECORD event) {
    if (event == nullptr || event->UserContext == nullptr) {
        return;
    }
    auto* context = static_cast<Context*>(event->UserContext);
    try {
        if (!IsEqualGUID(event->EventHeader.ProviderId, kFileIoProvider)) {
            return;
        }

        std::lock_guard<std::mutex> guard(context->mutex);
        ++context->classicFileEvents;
        if ((event->EventHeader.Flags & EVENT_HEADER_FLAG_CLASSIC_HEADER) != 0) {
            ++context->classicHeaderEvents;
        }
        if (event->EventHeader.EventDescriptor.Opcode != kRundownOpcode) {
            return;
        }

        ++context->rundownEvents;
        const ULONG payloadLength = event->UserDataLength;
        context->minimumPayload = (std::min)(context->minimumPayload, payloadLength);
        context->maximumPayload = (std::max)(context->maximumPayload, payloadLength);
        const ULONG version = event->EventHeader.EventDescriptor.Version;
        context->versions[version]++;

        const USHORT flags = event->EventHeader.Flags;
        const bool header32 = (flags & EVENT_HEADER_FLAG_32_BIT_HEADER) != 0;
        const bool header64 = (flags & EVENT_HEADER_FLAG_64_BIT_HEADER) != 0;
        ULONG pointerSize = 0;
        if (header32 != header64) {
            pointerSize = header32 ? 4 : 8;
        } else if (!header32 && !header64) {
            pointerSize = context->tracePointerSize;
        }
        if (pointerSize == 4 || pointerSize == 8) {
            context->pointerSizes[pointerSize]++;
        }

        DecodedName tdhDecoded;
        DecodedName rawDecoded;
        const bool tdhOk = (pointerSize == 4 || pointerSize == 8) &&
            decode_tdh(event, pointerSize, *context, tdhDecoded);
        const bool rawOk = decode_raw_schema(event, pointerSize, rawDecoded);

        DecodedName selected;
        std::string decoder;
        if (tdhOk && rawOk) {
            if (tdhDecoded.key != rawDecoded.key ||
                _wcsicmp(tdhDecoded.path.c_str(), rawDecoded.path.c_str()) != 0) {
                ++context->decoderConflicts;
                return;
            }
            selected = std::move(tdhDecoded);
            decoder = "tdh+raw-schema";
            ++context->tdhRecords;
        } else if (tdhOk) {
            selected = std::move(tdhDecoded);
            decoder = "tdh";
            ++context->tdhRecords;
        } else if (rawOk) {
            selected = std::move(rawDecoded);
            decoder = "raw-schema-v2";
            ++context->rawSchemaRecords;
        } else {
            ++context->undecodedRecords;
            return;
        }

        std::string utf8Path;
        if (!to_utf8(selected.path, utf8Path)) {
            ++context->invalidUtf8Records;
            return;
        }

        std::ostringstream key;
        key << "0x" << std::hex << std::nouppercase << selected.key;
        const std::string line =
            "{\"key\":\"" + key.str() + "\",\"path\":\"" +
            json_escape(utf8Path) + "\",\"decoder\":\"" + decoder + "\"}\n";
        context->output.write(line.data(), static_cast<std::streamsize>(line.size()));
        if (!context->output) {
            ++context->callbackErrors;
            return;
        }
        context->decoderSources[decoder]++;
    } catch (...) {
        try {
            std::lock_guard<std::mutex> guard(context->mutex);
            ++context->callbackErrors;
        } catch (...) {
            // Never allow an exception to cross the ETW callback boundary.
        }
    }
}
} // namespace

int wmain(int argc, wchar_t* argv[]) {
    if (argc != 3) {
        std::wcerr << L"Usage: n12_fileio_rundown.exe <trace.etl> <names.jsonl>\n";
        return 64;
    }

    Context context;
    context.output.open(std::filesystem::path(argv[2]), std::ios::binary | std::ios::trunc);
    if (!context.output) {
        std::cerr << "Could not create the private rundown output file.\n";
        return 2;
    }

    EVENT_TRACE_LOGFILEW logfile{};
    logfile.LogFileName = argv[1];
    logfile.ProcessTraceMode = PROCESS_TRACE_MODE_EVENT_RECORD;
    logfile.EventRecordCallback = &on_event;
    logfile.Context = &context;

    TRACEHANDLE trace = OpenTraceW(&logfile);
    if (trace == INVALID_PROCESSTRACE_HANDLE) {
        std::cerr << "OpenTraceW failed with Windows status " << GetLastError() << ".\n";
        return 3;
    }

    context.tracePointerSize = logfile.LogfileHeader.PointerSize;
    ULONG processStatus = ProcessTrace(
        &trace, 1, nullptr, nullptr);
    const ULONG closeStatus = CloseTrace(trace);
    context.output.flush();
    const bool outputOk = static_cast<bool>(context.output);
    context.output.close();

    print_summary(context, processStatus, closeStatus);
    if (processStatus != ERROR_SUCCESS) {
        return 4;
    }
    if (!outputOk) {
        return 5;
    }
    if (context.rundownEvents == 0) {
        return 6;
    }
    return 0;
}
