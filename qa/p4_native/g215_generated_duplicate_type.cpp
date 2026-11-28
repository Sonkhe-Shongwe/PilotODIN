// G2.15: generated-only DuplicateHandle/GetFileType feasibility.
// Never queries filenames, captures WebView2, reads data or scans system handles.
// Native execution requires a separately source-pinned one-use hosted-Windows gate.
#include <windows.h>
#include <cstdio>
#include <cstring>
#include <cwchar>

static_assert(sizeof(void*) == 8, "G2.15 requires x64");
static_assert(DUPLICATE_SAME_ACCESS == 0x00000002, "DuplicateHandle option drift");
static_assert(FILE_TYPE_DISK == 0x0001, "GetFileType disk enum drift");

namespace {
bool env_equals(const wchar_t* name, const wchar_t* expected) {
  wchar_t value[128] = {};
  DWORD n = GetEnvironmentVariableW(name, value, 128);
  return n != 0 && n < 128 && wcscmp(value, expected) == 0;
}

const char* probe() {
  if (!env_equals(L"GITHUB_ACTIONS", L"true") ||
      !env_equals(L"RUNNER_OS", L"Windows") ||
      !env_equals(L"RUNNER_ENVIRONMENT", L"github-hosted") ||
      !env_equals(L"GITHUB_RUN_ATTEMPT", L"1") ||
      !env_equals(L"PILOTODIN_G215_GENERATED_CONSENT",
                  L"I_APPROVE_ONE_G215_GENERATED_DUPLICATE_TYPE")) {
    return "G215_SCOPE_BLOCKED";
  }
  wchar_t root[MAX_PATH] = {};
  DWORD length = GetEnvironmentVariableW(L"RUNNER_TEMP", root, MAX_PATH);
  if (!length || length >= MAX_PATH) return "G215_ROOT_BLOCKED";
  DWORD attributes = GetFileAttributesW(root);
  if (attributes == INVALID_FILE_ATTRIBUTES ||
      !(attributes & FILE_ATTRIBUTE_DIRECTORY) ||
      (attributes & FILE_ATTRIBUTE_REPARSE_POINT)) {
    return "G215_ROOT_BLOCKED";
  }

  wchar_t filename[MAX_PATH] = {};
  if (!GetTempFileNameW(root, L"G15", 0, filename)) {
    return "G215_FIXTURE_BLOCKED";
  }
  HANDLE original = CreateFileW(
      filename, GENERIC_READ | GENERIC_WRITE | DELETE, 0, nullptr,
      OPEN_EXISTING, FILE_ATTRIBUTE_TEMPORARY | FILE_FLAG_DELETE_ON_CLOSE,
      nullptr);
  if (original == INVALID_HANDLE_VALUE) {
    DeleteFileW(filename);
    return "G215_FIXTURE_BLOCKED";
  }

  const char* verdict = "G215_DUPLICATE_BLOCKED";
  HANDLE duplicated = nullptr;
  do {
    if (!DuplicateHandle(GetCurrentProcess(), original, GetCurrentProcess(),
                         &duplicated, 0, FALSE, DUPLICATE_SAME_ACCESS) ||
        !duplicated || duplicated == INVALID_HANDLE_VALUE) {
      break;
    }
    SetLastError(NO_ERROR);
    DWORD kind = GetFileType(duplicated);
    if (kind == FILE_TYPE_DISK) {
      verdict = "G215_GENERATED_DISK_TYPE_PRESENT";
    } else if (kind == FILE_TYPE_UNKNOWN) {
      // GetLastError can distinguish API failure from valid UNKNOWN,
      // but neither outcome may be silently treated as FILE_TYPE_DISK.
      DWORD code = GetLastError();
      verdict = code == NO_ERROR ? "G215_TYPE_UNKNOWN" : "G215_TYPE_BLOCKED";
    } else {
      verdict = "G215_NOT_DISK";
    }
  } while (false);

  bool cleanup = true;
  if (duplicated && duplicated != INVALID_HANDLE_VALUE &&
      !CloseHandle(duplicated)) cleanup = false;
  if (!CloseHandle(original)) cleanup = false;
  if (GetFileAttributesW(filename) != INVALID_FILE_ATTRIBUTES) {
    if (!DeleteFileW(filename)) cleanup = false;
    cleanup = false;  // Even successful fallback deletion is not a clean pass.
  }
  return cleanup ? verdict : "G215_CLEANUP_BLOCKED";
}
}  // namespace

int wmain() {
  const char* result = probe();
  std::printf("g2_15=%s\n", result);
  // This only proves a temporary file's API type, NEVER R02.5 acceptance.
  return std::strcmp(result, "G215_GENERATED_DISK_TYPE_PRESENT") == 0 ? 0 : 2;
}
