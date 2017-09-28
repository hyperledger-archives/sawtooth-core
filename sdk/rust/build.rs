extern crate cc;

fn main() {
    println!("cargo:rustc-link-lib={}={}", "dylib", "crypto");
    cc::Build::new()
        .file("../c/loader.c")
        .compile("libloader.a");
}
