use std::collections::HashMap;
use std::ffi::c_void;
use std::sync::OnceLock;
use minhook::MinHook;

type BOOL = i32;
type HMODULE = isize;
const TRUE: BOOL = 1;

#[link(name = "kernel32")]
extern "system" {
    fn LoadLibraryW(lpLibFileName: *const u16) -> HMODULE;
    fn GetProcAddress(hModule: HMODULE, lpProcName: *const u8) -> usize;
    fn GetModuleHandleW(lpModuleName: *const u16) -> HMODULE;
}

static REAL_VERSION: OnceLock<HMODULE> = OnceLock::new();
static ATLASES: OnceLock<HashMap<u32, &'static [u8]>> = OnceLock::new();

// Embed 53 Turkish font atlases covering all 156 font descriptors for Range 2 (Latin Extended-A: 0x0100..0x0180)
static ATLAS_BLOB: &[u8] = include_bytes!("../turkish_atlases.bin");

fn init_atlases() -> &'static HashMap<u32, &'static [u8]> {
    ATLASES.get_or_init(|| {
        let mut map = HashMap::new();
        if ATLAS_BLOB.len() >= 4 {
            let count = u32::from_le_bytes(ATLAS_BLOB[0..4].try_into().unwrap()) as usize;
            let mut offset = 4usize;
            for _ in 0..count {
                if offset + 8 > ATLAS_BLOB.len() {
                    break;
                }
                let file_id = u32::from_le_bytes(ATLAS_BLOB[offset..offset + 4].try_into().unwrap());
                let length = u32::from_le_bytes(ATLAS_BLOB[offset + 4..offset + 8].try_into().unwrap()) as usize;
                offset += 8;
                if offset + length > ATLAS_BLOB.len() {
                    break;
                }
                map.insert(file_id, &ATLAS_BLOB[offset..offset + length]);
                offset += length;
            }
        }
        map
    })
}

type FnReadFile = unsafe extern "system" fn(
    p_archive: *mut c_void,
    file_id: u32,
    flags: u8,
    p_out_len: *mut u32,
    p_extra: *mut c_void,
) -> *mut c_void;

static mut S_ORIG_READ_FILE: Option<FnReadFile> = None;

unsafe extern "system" fn detour_read_file(
    p_archive: *mut c_void,
    file_id: u32,
    flags: u8,
    p_out_len: *mut u32,
    p_extra: *mut c_void,
) -> *mut c_void {
    let atlases = init_atlases();
    if let Some(&atlas) = atlases.get(&file_id) {
        let mut orig_len: u32 = 0;
        if let Some(orig) = S_ORIG_READ_FILE {
            let _ = orig(p_archive, file_id, flags, &mut orig_len, p_extra);
        }

        if !p_out_len.is_null() {
            *p_out_len = atlas.len() as u32;
        }

        if !p_archive.is_null() {
            // Update uncompressed and expected size fields in archive object
            let p98 = (p_archive as *mut u8).add(0x98) as *mut u32;
            let pf4 = (p_archive as *mut u8).add(0xF4) as *mut u32;
            *p98 = atlas.len() as u32;
            *pf4 = atlas.len() as u32;
        }

        return atlas.as_ptr() as *mut c_void;
    }

    if let Some(orig) = S_ORIG_READ_FILE {
        orig(p_archive, file_id, flags, p_out_len, p_extra)
    } else {
        std::ptr::null_mut()
    }
}

unsafe fn find_pattern(base: *const u8, size: usize, pattern: &[u8], mask: &str) -> Option<usize> {
    let plen = pattern.len();
    if size < plen {
        return None;
    }
    let mask_bytes = mask.as_bytes();
    for i in 0..=(size - plen) {
        let mut matched = true;
        for k in 0..plen {
            if mask_bytes[k] == b'x' && *base.add(i + k) != pattern[k] {
                matched = false;
                break;
            }
        }
        if matched {
            return Some(i);
        }
    }
    None
}

unsafe fn find_read_file_target() -> Option<*mut c_void> {
    let h_gw2 = GetModuleHandleW(std::ptr::null()) as *const u8;
    if h_gw2.is_null() {
        return None;
    }

    // Pattern for FileArchive::ReadFile:
    // 48 89 5C 24 10 55 56 57 41 56 41 57 48 83 EC 40 8B FA 48 8B E9
    let pattern = [
        0x48, 0x89, 0x5C, 0x24, 0x10, 0x55, 0x56, 0x57,
        0x41, 0x56, 0x41, 0x57, 0x48, 0x83, 0xEC, 0x40,
        0x8B, 0xFA, 0x48, 0x8B, 0xE9,
    ];
    let mask = "xxxxxxxxxxxxxxxxxxxxx";

    // Read DOS header e_lfanew at offset 0x3C
    let e_lfanew = *(h_gw2.add(0x3C) as *const i32) as usize;
    let nt_header = h_gw2.add(e_lfanew);
    let num_sections = *(nt_header.add(6) as *const u16) as usize;
    let size_of_opt_header = *(nt_header.add(20) as *const u16) as usize;
    let section_headers = nt_header.add(24 + size_of_opt_header);

    for s in 0..num_sections {
        let sec = section_headers.add(s * 40);
        let sec_name = std::slice::from_raw_parts(sec, 8);
        if sec_name.starts_with(b".text") {
            let virt_size = *(sec.add(8) as *const u32) as usize;
            let virt_addr = *(sec.add(12) as *const u32) as usize;
            let text_base = h_gw2.add(virt_addr);
            if let Some(offset) = find_pattern(text_base, virt_size, &pattern, mask) {
                return Some(text_base.add(offset) as *mut c_void);
            }
        }
    }

    // Known live RVA fallback 0xDBDDD0
    Some(h_gw2.add(0xDBDDD0) as *mut c_void)
}

unsafe fn install_font_hook() {
    init_atlases();
    if let Some(target) = find_read_file_target() {
        if let Ok(orig) = MinHook::create_hook(target, detour_read_file as *mut c_void) {
            S_ORIG_READ_FILE = Some(std::mem::transmute(orig));
            let _ = MinHook::enable_hook(target);
        }
    }
}

fn wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

fn get_real_fn(name: &[u8]) -> usize {
    let h = REAL_VERSION.get_or_init(|| unsafe {
        let p = wide("C:\\Windows\\System32\\version.dll");
        LoadLibraryW(p.as_ptr())
    });
    if *h == 0 {
        return 0;
    }
    unsafe { GetProcAddress(*h, name.as_ptr()) }
}

#[no_mangle]
pub unsafe extern "system" fn DllMain(
    _hinst: isize,
    reason: u32,
    _reserved: *mut c_void,
) -> BOOL {
    if reason == 1 {
        // DLL_PROCESS_ATTACH: Hook FileArchive::ReadFile immediately so font assets are intercepted at engine boot!
        install_font_hook();

        // Spawn background thread to load Nexus (d3d11.dll) smoothly
        std::thread::spawn(|| {
            std::thread::sleep(std::time::Duration::from_millis(50));
            unsafe {
                let d3d11 = wide("d3d11.dll");
                LoadLibraryW(d3d11.as_ptr());
            }
        });
    }
    TRUE
}

macro_rules! forward {
    ($name:ident, ($($arg:ident: $typ:ty),*) -> $ret:ty) => {
        #[no_mangle]
        pub unsafe extern "system" fn $name($($arg: $typ),*) -> $ret {
            let fp = get_real_fn(concat!(stringify!($name), "\0").as_bytes());
            if fp != 0 {
                let f: unsafe extern "system" fn($($typ),*) -> $ret = std::mem::transmute(fp);
                f($($arg),*)
            } else {
                std::mem::zeroed()
            }
        }
    };
}

forward!(GetFileVersionInfoA, (filename: *const u8, handle: u32, len: u32, data: *mut c_void) -> BOOL);
forward!(GetFileVersionInfoByHandle, (handle: isize, reserved: u32, len: u32, data: *mut c_void) -> BOOL);
forward!(GetFileVersionInfoExA, (flags: u32, filename: *const u8, handle: u32, len: u32, data: *mut c_void) -> BOOL);
forward!(GetFileVersionInfoExW, (flags: u32, filename: *const u16, handle: u32, len: u32, data: *mut c_void) -> BOOL);
forward!(GetFileVersionInfoSizeA, (filename: *const u8, handle: *mut u32) -> u32);
forward!(GetFileVersionInfoSizeExA, (flags: u32, filename: *const u8, handle: *mut u32) -> u32);
forward!(GetFileVersionInfoSizeExW, (flags: u32, filename: *const u16, handle: *mut u32) -> u32);
forward!(GetFileVersionInfoSizeW, (filename: *const u16, handle: *mut u32) -> u32);
forward!(GetFileVersionInfoW, (filename: *const u16, handle: u32, len: u32, data: *mut c_void) -> BOOL);
forward!(VerFindFileA, (flags: u32, app: *const u8, src: *const u8, dest: *const u8, cur: *mut u8, cur_len: *mut u32, dest_dir: *mut u8, dest_len: *mut u32) -> u32);
forward!(VerFindFileW, (flags: u32, app: *const u16, src: *const u16, dest: *const u16, cur: *mut u16, cur_len: *mut u32, dest_dir: *mut u16, dest_len: *mut u32) -> u32);
forward!(VerInstallFileA, (flags: u32, src: *const u8, dest: *const u8, src_dir: *const u8, dest_dir: *const u8, cur_dir: *const u8, tmp: *mut u8, tmp_len: *mut u32) -> u32);
forward!(VerInstallFileW, (flags: u32, src: *const u16, dest: *const u16, src_dir: *const u16, dest_dir: *const u16, cur_dir: *const u16, tmp: *mut u16, tmp_len: *mut u32) -> u32);
forward!(VerLanguageNameA, (lang: u32, sz: *mut u8, sz_len: u32) -> u32);
forward!(VerLanguageNameW, (lang: u32, sz: *mut u16, sz_len: u32) -> u32);
forward!(VerQueryValueA, (block: *const c_void, sub: *const u8, buf: *mut *mut c_void, len: *mut u32) -> BOOL);
forward!(VerQueryValueW, (block: *const c_void, sub: *const u16, buf: *mut *mut c_void, len: *mut u32) -> BOOL);
