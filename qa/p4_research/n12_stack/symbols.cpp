// Resolve RVAs against a matched local PDB without inspecting live processes.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <dbghelp.h>

#include <array>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

int wmain(int argc, wchar_t** argv) {
    if (argc != 5) {
        return 2;
    }
    const auto session = GetCurrentProcess();
    SymSetOptions(SYMOPT_DEFERRED_LOADS | SYMOPT_EXACT_SYMBOLS | SYMOPT_FAIL_CRITICAL_ERRORS |
                  SYMOPT_NO_PROMPTS | SYMOPT_IGNORE_NT_SYMPATH);
    if (!SymInitializeW(session, argv[2], FALSE)) {
        return 3;
    }

    const DWORD64 base = 0x10000000;
    std::ifstream input{std::filesystem::path(argv[3])};
    std::ofstream output{std::filesystem::path(argv[4])};
    if (!input || !output || SymLoadModuleExW(session, nullptr, argv[1], nullptr, base,
                                              0, nullptr, 0) != base) {
        SymCleanup(session);
        return 4;
    }

    DWORD64 rva = 0;
    while (input >> rva) {
        alignas(SYMBOL_INFO) std::array<std::byte, sizeof(SYMBOL_INFO) + 1024> buffer{};
        auto* symbol = reinterpret_cast<SYMBOL_INFO*>(buffer.data());
        symbol->SizeOfStruct = sizeof(SYMBOL_INFO);
        symbol->MaxNameLen = 1024;
        DWORD64 displacement = 0;
        if (!SymFromAddr(session, base + rva, &displacement, symbol)) {
            continue;
        }
        IMAGEHLP_MODULE64 module{};
        module.SizeOfStruct = sizeof(module);
        if (!SymGetModuleInfo64(session, base + rva, &module) || (module.SymType != SymPdb && module.SymType != SymDia) ||
            module.PdbUnmatched || module.DbgUnmatched || !module.LoadedPdbName[0] ||
            module.BaseOfImage != base || symbol->ModBase != base ||
            symbol->Address < base || symbol->Address > base + rva || !symbol->NameLen || symbol->NameLen >= symbol->MaxNameLen ||
            (symbol->Size && displacement >= symbol->Size)) {
            continue;
        }
        output << rva << '\t' << std::string(symbol->Name, symbol->NameLen) << '\n';
    }
    const bool ok = input.eof() && output.good();
    SymCleanup(session);
    return ok ? 0 : 5;
}
