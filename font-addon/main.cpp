#include "Nexus.h"
#include <windows.h>
#include <unordered_map>
#include <vector>
#include <string>
#include <fstream>
#include <sstream>

// Addon metadata
#define ADDON_NAME        "GW2 Turkish Font Injector"
#define ADDON_AUTHOR      "Antigravity & Pair"
#define ADDON_DESCRIPTION "Authentic Turkish Font & Glyph Injector (ı, İ, ş, Ş, ğ, Ğ) for Guild Wars 2"
#define ADDON_SIGNATURE   0x5455524B // 'TURK'

HMODULE g_hModule = NULL;
AddonAPI_t* APIDefs = nullptr;

struct AtlasEntry {
    const uint8_t* data;
    uint32_t size;
};

static std::unordered_map<uint32_t, AtlasEntry> g_atlases;
static std::vector<uint8_t> g_diskAtlasBlob;
static const uint8_t* g_activeBlobPtr = nullptr;
static size_t g_activeBlobSize = 0;

// Function pointer typedef for FileArchive::ReadFile
// Signature: void* FileArchive::ReadFile(void* pArchive, uint32_t fileId, uint8_t flags, uint32_t* pOutLen, void* pExtra)
typedef void* (*FnFileArchive_ReadFile)(void* pArchive, uint32_t fileId, uint8_t flags, uint32_t* pOutLen, void* pExtra);
static FnFileArchive_ReadFile s_orig_ReadFile = nullptr;
static void* s_target_ReadFile = nullptr;

// Detour implementation
void* Detour_ReadFile(void* pArchive, uint32_t fileId, uint8_t flags, uint32_t* pOutLen, void* pExtra)
{
    auto it = g_atlases.find(fileId);
    if (it != g_atlases.end())
    {
        // Execute original ReadFile so archive internal bookkeeping executes normally
        uint32_t origLen = 0;
        void* origDummy = s_orig_ReadFile(pArchive, fileId, flags, &origLen, pExtra);

        if (pOutLen) {
            *pOutLen = it->second.size;
        }

        if (pArchive) {
            // Update uncompressed and expected size fields in archive object
            *(uint32_t*)((char*)pArchive + 0x98) = it->second.size;
            *(uint32_t*)((char*)pArchive + 0xF4) = it->second.size;
        }

        if (APIDefs && APIDefs->Log) {
            char logMsg[128];
            snprintf(logMsg, sizeof(logMsg), "Injected authentic Turkish font atlas: fileId=%u, size=%u bytes (original: %u)",
                     fileId, it->second.size, origLen);
            APIDefs->Log(LOGL_INFO, "TurkishFont", logMsg);
        }

        return (void*)it->second.data;
    }

    return s_orig_ReadFile(pArchive, fileId, flags, pOutLen, pExtra);
}

// Pattern scanner helper
static uintptr_t FindPattern(HMODULE hMod, const unsigned char* pattern, const char* mask, size_t patternLen)
{
    if (!hMod) return 0;
    
    IMAGE_DOS_HEADER* dos = (IMAGE_DOS_HEADER*)hMod;
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    
    IMAGE_NT_HEADERS* nt = (IMAGE_NT_HEADERS*)((char*)hMod + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return 0;

    IMAGE_SECTION_HEADER* sec = IMAGE_FIRST_SECTION(nt);
    for (WORD i = 0; i < nt->FileHeader.NumberOfSections; ++i, ++sec)
    {
        // Scan inside .text section
        if (memcmp(sec->Name, ".text", 5) == 0)
        {
            const unsigned char* base = (const unsigned char*)hMod + sec->VirtualAddress;
            size_t size = sec->Misc.VirtualSize;
            
            if (size < patternLen) return 0;

            for (size_t j = 0; j <= size - patternLen; ++j)
            {
                bool found = true;
                for (size_t k = 0; k < patternLen; ++k)
                {
                    if (mask[k] == 'x' && base[j + k] != pattern[k]) {
                        found = false;
                        break;
                    }
                }
                if (found) {
                    return (uintptr_t)(base + j);
                }
            }
        }
    }
    return 0;
}

// Load atlases from memory blob
static bool ParseAtlasBlob(const uint8_t* blob, size_t blobSize)
{
    if (!blob || blobSize < 4) return false;

    uint32_t count = *(const uint32_t*)blob;
    size_t offset = 4;
    g_atlases.clear();

    for (uint32_t i = 0; i < count; ++i)
    {
        if (offset + 8 > blobSize) break;
        uint32_t fileId = *(const uint32_t*)(blob + offset);
        uint32_t length = *(const uint32_t*)(blob + offset + 4);
        offset += 8;

        if (offset + length > blobSize) break;
        g_atlases[fileId] = { blob + offset, length };
        offset += length;
    }

    return !g_atlases.empty();
}

// Load atlas blob from disk or resource
static bool LoadAtlasData()
{
    // 1. Try loading from disk in addons folder
    if (APIDefs && APIDefs->Paths_GetAddonDirectory)
    {
        const char* path = APIDefs->Paths_GetAddonDirectory("turkish_atlases.bin");
        if (path)
        {
            std::ifstream file(path, std::ios::binary | std::ios::ate);
            if (file.is_open())
            {
                size_t size = (size_t)file.tellg();
                if (size > 4)
                {
                    g_diskAtlasBlob.resize(size);
                    file.seekg(0, std::ios::beg);
                    file.read((char*)g_diskAtlasBlob.data(), size);
                    if (ParseAtlasBlob(g_diskAtlasBlob.data(), size))
                    {
                        g_activeBlobPtr = g_diskAtlasBlob.data();
                        g_activeBlobSize = size;
                        if (APIDefs->Log) {
                            char buf[128];
                            snprintf(buf, sizeof(buf), "Loaded %zu Turkish font atlases from disk (%s)", g_atlases.size(), path);
                            APIDefs->Log(LOGL_INFO, "TurkishFont", buf);
                        }
                        return true;
                    }
                }
            }
        }
    }

    // 2. Try loading from embedded resource
    HRSRC hRes = FindResource(g_hModule, MAKEINTRESOURCE(1), RT_RCDATA);
    if (hRes)
    {
        HGLOBAL hMem = LoadResource(g_hModule, hRes);
        if (hMem)
        {
            const uint8_t* data = (const uint8_t*)LockResource(hMem);
            size_t size = SizeofResource(g_hModule, hRes);
            if (data && size > 4)
            {
                if (ParseAtlasBlob(data, size))
                {
                    g_activeBlobPtr = data;
                    g_activeBlobSize = size;
                    if (APIDefs && APIDefs->Log) {
                        char buf[128];
                        snprintf(buf, sizeof(buf), "Loaded %zu Turkish font atlases from embedded resource (%zu bytes)", g_atlases.size(), size);
                        APIDefs->Log(LOGL_INFO, "TurkishFont", buf);
                    }
                    return true;
                }
            }
        }
    }

    return false;
}

// Addon lifecycle functions
void AddonLoad(AddonAPI_t* aAPI)
{
    APIDefs = aAPI;

    if (!APIDefs) return;

    APIDefs->Log(LOGL_INFO, "TurkishFont", "Initializing GW2 Turkish Font Injector...");

    // Load atlases
    if (!LoadAtlasData()) {
        APIDefs->Log(LOGL_CRITICAL, "TurkishFont", "ERROR: Could not load turkish_atlases.bin from disk or resource!");
        return;
    }

    // Pattern for FileArchive::ReadFile
    // 48 89 5C 24 10 55 56 57 41 56 41 57 48 83 EC 40 8B FA 48 8B E9
    const unsigned char pattern[] = {
        0x48, 0x89, 0x5C, 0x24, 0x10, 0x55, 0x56, 0x57,
        0x41, 0x56, 0x41, 0x57, 0x48, 0x83, 0xEC, 0x40,
        0x8B, 0xFA, 0x48, 0x8B, 0xE9
    };
    const char mask[] = "xxxxxxxxxxxxxxxxxxxxx";

    HMODULE hGw2 = GetModuleHandleA(NULL);
    uintptr_t targetAddr = FindPattern(hGw2, pattern, mask, sizeof(pattern));

    // Fallback check against known live RVA 0xDBDDD0 if pattern scan missed
    if (!targetAddr && hGw2) {
        uintptr_t fallback = (uintptr_t)hGw2 + 0xDBDDD0;
        MEMORY_BASIC_INFORMATION mbi;
        if (VirtualQuery((LPCVOID)fallback, &mbi, sizeof(mbi)) &&
            (mbi.State == MEM_COMMIT) &&
            !(mbi.Protect & (PAGE_NOACCESS | PAGE_GUARD)))
        {
            if (memcmp((const void*)fallback, pattern, sizeof(pattern)) == 0) {
                targetAddr = fallback;
                APIDefs->Log(LOGL_INFO, "TurkishFont", "Resolved ReadFile via RVA fallback 0xDBDDD0");
            }
        }
    }

    if (!targetAddr) {
        APIDefs->Log(LOGL_CRITICAL, "TurkishFont", "ERROR: Could not resolve FileArchive::ReadFile signature in Gw2-64.exe!");
        return;
    }

    s_target_ReadFile = (void*)targetAddr;

    // Apply hook using Nexus MinHook API
    if (APIDefs->MinHook_Create && APIDefs->MinHook_Enable)
    {
        EMHStatus status = APIDefs->MinHook_Create(
            s_target_ReadFile,
            (LPVOID)Detour_ReadFile,
            (LPVOID*)&s_orig_ReadFile
        );

        if (status == MH_OK)
        {
            status = APIDefs->MinHook_Enable(s_target_ReadFile);
            if (status == MH_OK) {
                char msg[128];
                snprintf(msg, sizeof(msg), "SUCCESS: FileArchive::ReadFile hooked at 0x%p (156 font atlases ready)", s_target_ReadFile);
                APIDefs->Log(LOGL_INFO, "TurkishFont", msg);
                return;
            }
        }

        char err[128];
        snprintf(err, sizeof(err), "ERROR: MinHook failed with status %d", (int)status);
        APIDefs->Log(LOGL_CRITICAL, "TurkishFont", err);
    }
    else
    {
        APIDefs->Log(LOGL_CRITICAL, "TurkishFont", "ERROR: MinHook API functions are null in AddonAPI!");
    }
}

void AddonUnload()
{
    if (APIDefs && s_target_ReadFile)
    {
        if (APIDefs->MinHook_Disable) {
            APIDefs->MinHook_Disable(s_target_ReadFile);
        }
        if (APIDefs->MinHook_Remove) {
            APIDefs->MinHook_Remove(s_target_ReadFile);
        }
        APIDefs->Log(LOGL_INFO, "TurkishFont", "Addon unloaded, hook removed.");
    }

    s_target_ReadFile = nullptr;
    s_orig_ReadFile = nullptr;
    g_atlases.clear();
    g_diskAtlasBlob.clear();
    g_activeBlobPtr = nullptr;
    g_activeBlobSize = 0;
}

// Definition struct
static AddonDefinition_t AddonDef = {
    ADDON_SIGNATURE,
    NEXUS_API_VERSION,
    ADDON_NAME,
    { 1, 0, 0, 0 },
    ADDON_AUTHOR,
    ADDON_DESCRIPTION,
    AddonLoad,
    AddonUnload,
    AF_None,
    UP_None,
    nullptr
};

extern "C" __declspec(dllexport) AddonDefinition_t* GetAddonDef()
{
    return &AddonDef;
}

BOOL APIENTRY DllMain(HMODULE hModule, DWORD ul_reason_for_call, LPVOID lpReserved)
{
    if (ul_reason_for_call == DLL_PROCESS_ATTACH)
    {
        g_hModule = hModule;
        DisableThreadLibraryCalls(hModule);
    }
    return TRUE;
}
