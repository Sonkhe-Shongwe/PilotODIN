// G2.13: generated-only PSS feasibility, NEVER a PilotODIN process capture.
// The guarded Windows workflow is DISARMED until a fresh one-use owner approval.
// Reads only a new disposable fixture under GitHub RUNNER_TEMP. Public output
// contains fixed labels only. No raw PIDs, paths, handles or object names.
#include <windows.h>
#include <processsnapshot.h>
#include <cstddef>
#include <cstdio>
#include <cwchar>
#include <cstring>

static_assert(sizeof(void*) == 8, "G2.13 is x64-only");
static_assert(sizeof(PSS_HANDLE_ENTRY) == 136, "PSS HANDLE_ENTRY ABI size drift");
static_assert(offsetof(PSS_HANDLE_ENTRY, Handle) == 0, "Handle offset drift");
static_assert(offsetof(PSS_HANDLE_ENTRY, Flags) == 8, "Flags offset drift");
static_assert(offsetof(PSS_HANDLE_ENTRY, ObjectType) == 12, "ObjectType offset drift");
static_assert(offsetof(PSS_HANDLE_ENTRY, CaptureTime) == 16, "CaptureTime offset drift");
static_assert(offsetof(PSS_HANDLE_ENTRY, CreationTime) == 48, "CreationTime offset drift");
static_assert(offsetof(PSS_HANDLE_ENTRY, TypeNameLength) == 56, "TypeNameLength offset drift");
static_assert(offsetof(PSS_HANDLE_ENTRY, TypeName) == 64, "TypeName offset drift");
static_assert(offsetof(PSS_HANDLE_ENTRY, ObjectNameLength) == 72, "ObjectNameLength offset drift");
static_assert(offsetof(PSS_HANDLE_ENTRY, ObjectName) == 80, "ObjectName offset drift");
static_assert(offsetof(PSS_HANDLE_ENTRY, TypeSpecificInformation) == 88,
              "TypeSpecificInformation offset drift");
static_assert(PSS_WALK_HANDLES == 2, "PSS handle walk constant drift");
static_assert(PSS_CAPTURE_HANDLES == 0x4, "PSS HANDLE flag drift");
static_assert(PSS_CAPTURE_HANDLE_BASIC_INFORMATION == 0x10,
              "PSS BASIC flag drift");
static_assert(PSS_HANDLE_HAVE_TYPE == 0x1, "PSS Type flag drift");
static_assert(PSS_HANDLE_HAVE_NAME == 0x2, "PSS Name flag drift");

namespace {
constexpr DWORD kCapture = PSS_CAPTURE_HANDLES | PSS_CAPTURE_HANDLE_BASIC_INFORMATION;
constexpr unsigned kMaximumRows = 256;

bool checked_environment(const wchar_t* name, const wchar_t* expected) {
  wchar_t value[128] = {};
  DWORD length = GetEnvironmentVariableW(name, value, 128);
  return length != 0 && length < 128 && wcscmp(value, expected) == 0;
}
const char* probe() {
  // Defense in depth. Source SHA/direct-parent/one-use approval is independently
  // checked by the STILL-DISARMED workflow before this executable is compiled.
  if (!checked_environment(L"GITHUB_ACTIONS", L"true") ||
      !checked_environment(L"RUNNER_OS", L"Windows") ||
      !checked_environment(L"RUNNER_ENVIRONMENT", L"github-hosted") ||
      !checked_environment(L"GITHUB_RUN_ATTEMPT", L"1") ||
      !checked_environment(L"PILOTODIN_G213_GENERATED_CONSENT",
                           L"I_APPROVE_ONE_GENERATED_PSS_FEASIBILITY")) {
    return "G213_SCOPE_NOT_AUTHORIZED";
  }

  wchar_t root[MAX_PATH] = {};
  DWORD rootlen = GetEnvironmentVariableW(L"RUNNER_TEMP", root, MAX_PATH);
  if (!rootlen || rootlen >= MAX_PATH) return "G213_ROOT_UNVERIFIED";
  DWORD attributes = GetFileAttributesW(root);
  if (attributes == INVALID_FILE_ATTRIBUTES ||
      !(attributes & FILE_ATTRIBUTE_DIRECTORY) ||
      (attributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
    return "G213_ROOT_UNVERIFIED";
  }

  // Create precisely one generated temporary fixture. The name is never
  // printed/uploaded and is deleted on cleanup, even on capture failure.
  wchar_t fixture_name[MAX_PATH] = {};
  if (!GetTempFileNameW(root, L"G13", 0, fixture_name))
    return "G213_FIXTURE_UNAVAILABLE";

  HANDLE file = CreateFileW(
      fixture_name, GENERIC_READ | GENERIC_WRITE | DELETE, 0, nullptr, OPEN_EXISTING,
      FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_DELETE_ON_CLOSE, nullptr);
  if (file == INVALID_HANDLE_VALUE) {
    DeleteFileW(fixture_name);
    return "G213_FIXTURE_UNAVAILABLE";
  }

  HPSS snapshot = nullptr;
  HPSSWALK marker = nullptr;
  const char* verdict = "G213_PSS_INCOMPLETE";
  do {
    DWORD result = PssCaptureSnapshot(GetCurrentProcess(), kCapture, 0, &snapshot);
    if (result != ERROR_SUCCESS || !snapshot) break;
    result = PssWalkMarkerCreate(nullptr, &marker);
    if (result != ERROR_SUCCESS || !marker) break;

    bool matched_fixture = false;
    bool file_type_present = false;
    bool bad_name_or_entry = false;
    bool completed_walk = false;

    for (unsigned i = 0; i <= kMaximumRows; ++i) {
      PSS_HANDLE_ENTRY entry = {};
      result = PssWalkSnapshot(snapshot, PSS_WALK_HANDLES, marker,
                               &entry, sizeof(entry));
      if (result == ERROR_NO_MORE_ITEMS) {
        completed_walk = true;
        break;
      }
      if (result != ERROR_SUCCESS || i == kMaximumRows) break;
      if ((entry.Flags & PSS_HANDLE_HAVE_NAME) ||
          entry.ObjectName || entry.ObjectNameLength ||
          (entry.Flags & ~0x0F) ||
          entry.TypeNameLength > 128 || (entry.TypeNameLength % 2)) {
        bad_name_or_entry = true;
        break;
      }
      if (entry.Handle != file) continue;
      if (matched_fixture) {
        bad_name_or_entry = true;
        break;
      }
      matched_fixture = true;
      if ((entry.Flags & PSS_HANDLE_HAVE_TYPE) && entry.TypeName &&
          entry.TypeNameLength == 4 * sizeof(wchar_t) &&
          wmemcmp(entry.TypeName, L"File", 4) == 0) {
        file_type_present = true;
      }
    }
    if (bad_name_or_entry || !completed_walk) {
      verdict = "G213_HANDLE_WALK_INCOMPLETE";
    } else if (!matched_fixture) {
      verdict = "G213_GENERATED_HANDLE_NOT_OBSERVED";
    } else if (file_type_present) {
      verdict = "G213_GENERATED_FILE_TYPE_PRESENT";
    } else {
      verdict = "G213_GENERATED_FILE_TYPE_UNAVAILABLE";
    }
  } while (false);

  bool cleanup_ok = true;
  if (marker && PssWalkMarkerFree(marker) != ERROR_SUCCESS) cleanup_ok = false;
  if (snapshot && PssFreeSnapshot(GetCurrentProcess(), snapshot) != ERROR_SUCCESS)
    cleanup_ok = false;
  if (!CloseHandle(file)) cleanup_ok = false;
  // DELETE_ON_CLOSE is a best-effort generated-root cleanup. A surviving
  // fixture should keep the result BLOCKED, never be silently credited.
  DWORD after = GetFileAttributesW(fixture_name);
  if (after != INVALID_FILE_ATTRIBUTES) {
    if (!DeleteFileW(fixture_name)) cleanup_ok = false;
    cleanup_ok = false;
  }
  return cleanup_ok ? verdict : "G213_GENERATED_CLEANUP_UNVERIFIED";
}
} // namespace

int wmain() {
  const char* result = probe();
  std::printf("g2_13=%s\n", result);
  // "UNAVAILABLE" is a valid negative diagnostic, NOT a native acceptance.
  return (std::strcmp(result, "G213_GENERATED_FILE_TYPE_PRESENT") == 0 ||
          std::strcmp(result, "G213_GENERATED_FILE_TYPE_UNAVAILABLE") == 0)
             ? 0 : 2;
}
