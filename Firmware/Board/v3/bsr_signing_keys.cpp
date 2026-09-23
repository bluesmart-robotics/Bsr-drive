/*
 * BSR firmware lineage signing keys (PUBLIC halves only)
 * ========================================================
 *
 * See docs/FIRMWARE_LINEAGE_BSR.md for the full design. In short: this file
 * is the ONE file that differs between BSR's private firmware forks
 * ("E-dolly-control", "flight-control-khepri-libel"). It carries only the
 * PUBLIC half of each fork's Ed25519 signing key, plus a short "key id"
 * (the first 16 bytes of sha256(public_key)) that gets burned into a
 * board's OTP the first time that fork's firmware runs on it.
 *
 * The matching PRIVATE keys are held offline by BSR (never in this
 * repository, in any commit, in any fork - public or private) and are used
 * only on a build machine to sign release binaries. This is a plain
 * application of Kerckhoffs's principle: the whole point of this file being
 * public is that it doesn't matter who can read it - security rests
 * entirely on the private key, not on hiding this code.
 *
 * This translation unit compiles to nothing at all unless BSR_PRODUCT_ID is
 * defined (see Tupfile.lua's CONFIG_BSR_PRODUCT option) - the public,
 * unsigned build never has this file's symbols and therefore cannot ever
 * satisfy check_firmware_lineage() in board.cpp.
 */

#include <cstdint>

#if defined(BSR_PRODUCT_ID)

#if BSR_PRODUCT_ID == 1
// --- E-dolly-control ------------------------------------------------------
// Ed25519 public key, generated 2026-09-23. Key id = sha256(pubkey)[0:16].
// NOTE: `extern` is required here even though this is the defining
// translation unit - in C++ (unlike C), a global `const` has internal
// linkage by default, which would make it invisible to board.cpp's own
// `extern` declaration and fail at link time.
extern const uint8_t bsr_signer_public_key[32] = {
    0x62, 0x02, 0x0f, 0x81, 0xba, 0xbf, 0x27, 0x02, 0xcf, 0xdc, 0x88, 0x66,
    0x20, 0xf7, 0xfb, 0xa6, 0x97, 0x78, 0x4e, 0x0b, 0xb6, 0xab, 0x86, 0xa4,
    0x1f, 0x44, 0x54, 0x03, 0x37, 0xe4, 0x05, 0xd3,
};
extern const uint8_t bsr_signer_key_id[16] = {
    0x2d, 0xa5, 0x9a, 0xe4, 0x54, 0x1a, 0xd8, 0x2e,
    0xf1, 0xc7, 0x94, 0x2f, 0x98, 0x76, 0xc3, 0x87,
};

#elif BSR_PRODUCT_ID == 2
// --- flight-control-khepri-libel -------------------------------------------
// Ed25519 public key, generated 2026-09-23. Key id = sha256(pubkey)[0:16].
extern const uint8_t bsr_signer_public_key[32] = {
    0x4c, 0x24, 0x28, 0x9c, 0xba, 0x85, 0x8d, 0x78, 0xf7, 0xeb, 0x06, 0x4e,
    0x7e, 0x54, 0x9d, 0x53, 0x39, 0x38, 0xb1, 0xa9, 0xaa, 0x55, 0x13, 0x39,
    0x68, 0xed, 0xfe, 0x39, 0x3a, 0x1f, 0x3f, 0x4f,
};
extern const uint8_t bsr_signer_key_id[16] = {
    0xff, 0x1e, 0xc5, 0x57, 0xfb, 0xf7, 0x92, 0x9d,
    0xf6, 0xf0, 0xfc, 0xd7, 0x6f, 0xfd, 0xc5, 0x0f,
};

#else
#error "BSR_PRODUCT_ID is defined but has no matching signing key in bsr_signing_keys.cpp"
#endif

#endif // BSR_PRODUCT_ID
