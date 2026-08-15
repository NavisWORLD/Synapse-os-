use std::ffi::CString;
use std::io;
use std::os::raw::{c_char, c_int};
use std::path::Path;
use std::time::Duration;

const SYNAPSE_OK: c_int = 0;
const SYNAPSE_ENOENT: c_int = 2;
const SYNAPSE_EBUFFER: c_int = 4;

#[link(name = "synapse_abi")]
extern "C" {
    fn synapse_abi_version() -> u32;
    fn synapse_status_read(
        path: *const c_char,
        buffer: *mut c_char,
        capacity: usize,
        required: *mut usize,
    ) -> c_int;
    fn synapse_service_reachable(host: *const c_char, port: u16, timeout_ms: u32) -> c_int;
}

fn abi_error(code: c_int) -> io::Error {
    let kind = if code == SYNAPSE_ENOENT {
        io::ErrorKind::NotFound
    } else if code == SYNAPSE_EBUFFER {
        io::ErrorKind::InvalidData
    } else {
        io::ErrorKind::Other
    };
    io::Error::new(kind, format!("Synapse ABI error {code}"))
}

pub fn abi_version() -> u32 {
    unsafe { synapse_abi_version() }
}

pub fn raw_status<P: AsRef<Path>>(path: P) -> io::Result<String> {
    let path_text = path.as_ref().to_string_lossy();
    let c_path = CString::new(path_text.as_bytes())
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "path contains a NUL byte"))?;
    let mut required = 0usize;
    let rc = unsafe { synapse_status_read(c_path.as_ptr(), std::ptr::null_mut(), 0, &mut required) };
    if rc != SYNAPSE_OK {
        return Err(abi_error(rc));
    }
    let mut buffer = vec![0u8; required];
    let rc = unsafe {
        synapse_status_read(
            c_path.as_ptr(),
            buffer.as_mut_ptr().cast::<c_char>(),
            buffer.len(),
            &mut required,
        )
    };
    if rc != SYNAPSE_OK {
        return Err(abi_error(rc));
    }
    if let Some(nul) = buffer.iter().position(|byte| *byte == 0) {
        buffer.truncate(nul);
    }
    String::from_utf8(buffer).map_err(|err| io::Error::new(io::ErrorKind::InvalidData, err))
}

pub fn service_reachable(port: u16, timeout: Duration) -> bool {
    service_reachable_host("127.0.0.1", port, timeout)
}

pub fn service_reachable_host(host: &str, port: u16, timeout: Duration) -> bool {
    if port == 0 {
        return false;
    }
    let Ok(c_host) = CString::new(host) else {
        return false;
    };
    let millis = timeout.as_millis().min(u32::MAX as u128) as u32;
    unsafe { synapse_service_reachable(c_host.as_ptr(), port, millis) == 1 }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;

    #[test]
    fn abi_is_v1() {
        assert_eq!(abi_version(), 1);
    }

    #[test]
    fn reads_status_through_abi() {
        let path = std::env::temp_dir().join(format!("synapse-rust-{}.json", std::process::id()));
        fs::write(&path, "{\"rust\":true}").unwrap();
        let value = raw_status(&path).unwrap();
        fs::remove_file(&path).ok();
        assert_eq!(value, "{\"rust\":true}");
    }

    #[test]
    fn invalid_port_is_rejected() {
        assert!(!service_reachable(0, Duration::from_millis(5)));
    }
}
