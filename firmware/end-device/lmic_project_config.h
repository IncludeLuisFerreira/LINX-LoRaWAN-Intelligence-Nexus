// ============================================================
//  lmic_project_config.h
//  Place this file in the SAME folder as your .ino sketch.
//
//  Fixes ESP32 + MCCI LMIC compilation errors:
//    - "multiple definition of hal_init"
//    - "Board not supported -- use an explicit pinmap"
// ============================================================

// --- Radio type: RFM95 uses SX1276 ---
#define CFG_sx1276_radio

// --- Region: AU915 (Brazil / Australia 915 MHz band) ---
#define CFG_au915

// ============================================================
//  CRITICAL for ESP32: Rename LMIC's hal_init to avoid
//  conflict with ESP32 SDK's own hal_init in libpp.a
// ============================================================
#define hal_init LMIC_hal_init

// ============================================================
//  CRITICAL for ESP32: Tell LMIC not to use auto-detected
//  pinmap — we provide the pinmap explicitly in the sketch
//  via the lmic_pins struct (already done in your .ino).
// ============================================================
#define ARDUINO_LMIC_PROJECT_CONFIG_H_SUPPRESS_WARNING

// ============================================================
//  Optional: reduce flash usage for Class A only devices
// ============================================================
// #define DISABLE_BEACONS
// #define DISABLE_PING
