use std::ffi::c_void;
use std::sync::OnceLock;

type BOOL = i32;
type HMODULE = isize;
const TRUE: BOOL = 1;

#[link(name = "kernel32")]
extern "system" {
    fn LoadLibraryW(lpLibFileName: *const u16) -> HMODULE;
    fn GetProcAddress(hModule: HMODULE, lpProcName: *const u8) -> usize;
}

static REAL_VERSION: OnceLock<HMODULE> = OnceLock::new();

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
        // DLL_PROCESS_ATTACH
        let _ = get_real_fn(b"GetFileVersionInfoW\0");

        // Spawn background thread to load Nexus (d3d11.dll) and turkish_font.dll
        std::thread::spawn(|| {
            std::thread::sleep(std::time::Duration::from_millis(50));
            unsafe {
                let d3d11 = wide("d3d11.dll");
                LoadLibraryW(d3d11.as_ptr());
                let font = wide("addons\\turkish_font.dll");
                LoadLibraryW(font.as_ptr());
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
