extern crate cc;

fn main() {
    println!("cargo:rustc-link-lib={}={}", "dylib", "crypto");
    cc::Build::new()
        .file("../c/loader.c")
        .file("../c/c11_support.c")
        .include("../c")
        .compile("libloader.a");
}
