use std::{io, ptr};

fn main() {
    unsafe {
        // As far as I understand, mmap(2) is the way how memory allocators get memory from the OS
        let mem = libc::mmap(
            ptr::null_mut(),
            2048,
            libc::PROT_READ | libc::PROT_WRITE,
            libc::MAP_PRIVATE | libc::MAP_ANONYMOUS,
            -1,
            0
        );
        if mem == libc::MAP_FAILED {
            let errno = io::Error::last_os_error().raw_os_error().unwrap_or(0);
            println!("mmap failed. errno={:?}", errno)
        } else {
            println!("got memory {:?}", mem);
        }
    }
}
