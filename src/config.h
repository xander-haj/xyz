/*
 * config.h — Configuration Data Structures and Key Binding Declarations
 *
 * Defines the Config struct that holds all user-configurable settings for the
 * zelda3 reimplementation: video output (resolution, scaling, shaders),
 * audio (frequency, channels, MSU-1 support), input (keyboard and gamepad
 * bindings), and gameplay feature toggles. Settings are populated at startup
 * by parsing an INI file in config.c.
 *
 * Also defines the key command enum (kKeys_*) which maps abstract game
 * actions (directional movement, save/load slots, cheats, UI controls) to
 * integer command IDs. These IDs serve as the bridge between physical input
 * (SDL keycodes, gamepad buttons) and game logic — config.c builds hash
 * tables that map physical inputs to these command IDs at startup.
 *
 * The gamepad button enum (kGamepadBtn_*) provides a platform-independent
 * abstraction over SDL's gamepad API, supporting modifier-key combos
 * (e.g., L1+A) through a bitmask system implemented in config.c.
 */
#pragma once
#include "types.h"

/*
 * Key command IDs — abstract game actions mapped to integer indices.
 *
 * Multi-slot commands (Controls, Load, Save, Replay, LoadRef, ReplayRef)
 * occupy contiguous ranges so a single base ID + slot offset can address
 * any slot. For example, kKeys_Load through kKeys_Load_Last spans 20
 * save-state slots addressable via F1-F10 (and 10 unused expansion slots).
 *
 * Controls occupies 12 slots: Up, Down, Left, Right, Select, Start,
 * A, B, X, Y, L, R — matching the SNES controller layout.
 */
enum {
  kKeys_Null,
  kKeys_Controls,
  kKeys_Controls_Last = kKeys_Controls + 11,
  kKeys_Load,
  kKeys_Load_Last = kKeys_Load + 19,
  kKeys_Save,
  kKeys_Save_Last = kKeys_Save + 19,
  kKeys_Replay,
  kKeys_Replay_Last = kKeys_Replay + 19,
  kKeys_LoadRef,
  kKeys_LoadRef_Last = kKeys_LoadRef + 19,
  kKeys_ReplayRef,
  kKeys_ReplayRef_Last = kKeys_ReplayRef + 19,
  // Debug and cheat commands — single-key toggles for development/testing
  kKeys_CheatLife,
  kKeys_CheatKeys,
  kKeys_CheatEquipment,
  kKeys_CheatWalkThroughWalls,
  // Replay system controls
  kKeys_ClearKeyLog,
  kKeys_StopReplay,
  // Application-level controls unrelated to in-game actions
  kKeys_Fullscreen,
  kKeys_Reset,
  kKeys_Pause,
  kKeys_PauseDimmed,
  kKeys_Turbo,
  kKeys_ReplayTurbo,
  kKeys_WindowBigger,
  kKeys_WindowSmaller,
  kKeys_DisplayPerf,
  kKeys_ToggleRenderer,
  kKeys_VolumeUp,
  kKeys_VolumeDown,
  kKeys_NewSettingsMenu,
  // Sentinel value — total number of bindable commands
  kKeys_Total,
};

/* Video output backend selection — determines which SDL/OpenGL rendering
 * path is used. SDL (hardware-accelerated) is the default; SDLSoftware
 * disables GPU acceleration; OpenGL/OpenGL_ES enable the GLSL shader
 * pipeline defined in glsl_shader.c for post-processing effects. */
enum {
  kOutputMethod_SDL,
  kOutputMethod_SDLSoftware,
  kOutputMethod_OpenGL,
  kOutputMethod_OpenGL_ES,
};

/*
 * Config — Central configuration struct populated from the INI file.
 *
 * All fields have sensible zero-value defaults (struct is zero-initialized).
 * Non-zero defaults (e.g., msuvolume=100) are set in ParseConfigFile()
 * before INI parsing begins.
 */
typedef struct Config {
  // --- Video Settings ---
  int window_width;                // Pixel width of the game window (0 = auto)
  int window_height;               // Pixel height of the game window (0 = auto)
  bool enhanced_mode7;             // Upscaled Mode 7 rendering (affine BGs)
  bool new_renderer;               // Use the new PPU renderer path
  bool ignore_aspect_ratio;        // Allow non-4:3 stretching
  uint8 fullscreen;                // 0=windowed, 1=fullscreen, 2=desktop FS
  uint8 window_scale;              // Integer scale factor for the 256px base
  bool linear_filtering;           // Bilinear vs nearest-neighbor scaling
  uint8 output_method;             // kOutputMethod_* enum value
  // --- Audio Settings ---
  bool enable_audio;               // Master audio enable
  uint16 audio_freq;               // Sample rate in Hz (e.g., 44100, 48000)
  uint8 audio_channels;            // 1=mono, 2=stereo
  uint16 audio_samples;            // SDL audio buffer size in samples
  // --- General Settings ---
  bool autosave;                   // Auto-save SRAM on exit
  uint8 extended_aspect_ratio;     // Extra horizontal pixels per side for widescreen
  bool extend_y;                   // Extend vertical resolution from 224 to 240
  bool fill_extended_aspect_ratio_borders; // Fill outdoor/dungeon widescreen side padding from edge art
  bool no_sprite_limits;           // Remove the SNES 32-sprite-per-scanline limit
  bool display_perf_title;         // Show FPS/performance stats in window title
  int16 hud_magic_frame_pos_x;     // Widescreen HUD magic-frame X half-tile
  int16 hud_magic_frame_pos_y;     // Widescreen HUD magic-frame Y half-tile
  int16 hud_magic_meter_pos_x;     // Widescreen HUD magic-fill X half-tile
  int16 hud_magic_meter_pos_y;     // Widescreen HUD magic-fill Y half-tile
  int16 hud_item_box_pos_x;        // Widescreen HUD item-frame X half-tile
  int16 hud_item_box_pos_y;        // Widescreen HUD item-frame Y half-tile
  int16 hud_item_icon_pos_x;       // Widescreen HUD item-icon X half-tile
  int16 hud_item_icon_pos_y;       // Widescreen HUD item-icon Y half-tile
  int16 hud_item_x_box_pos_x;      // Widescreen HUD X item-frame X half-tile
  int16 hud_item_x_box_pos_y;      // Widescreen HUD X item-frame Y half-tile
  int16 hud_item_x_icon_pos_x;     // Widescreen HUD X item-icon X half-tile
  int16 hud_item_x_icon_pos_y;     // Widescreen HUD X item-icon Y half-tile
  int16 hud_item_l_box_pos_x;      // Widescreen HUD L item-frame X half-tile
  int16 hud_item_l_box_pos_y;      // Widescreen HUD L item-frame Y half-tile
  int16 hud_item_l_icon_pos_x;     // Widescreen HUD L item-icon X half-tile
  int16 hud_item_l_icon_pos_y;     // Widescreen HUD L item-icon Y half-tile
  int16 hud_item_r_box_pos_x;      // Widescreen HUD R item-frame X half-tile
  int16 hud_item_r_box_pos_y;      // Widescreen HUD R item-frame Y half-tile
  int16 hud_item_r_icon_pos_x;     // Widescreen HUD R item-icon X half-tile
  int16 hud_item_r_icon_pos_y;     // Widescreen HUD R item-icon Y half-tile
  int16 hud_rupees_bg_pos_x;       // Widescreen HUD rupee-backdrop X half-tile
  int16 hud_rupees_bg_pos_y;       // Widescreen HUD rupee-backdrop Y half-tile
  int16 hud_rupees_pos_x;          // Widescreen HUD rupee digits X half-tile
  int16 hud_rupees_pos_y;          // Widescreen HUD rupee digits Y half-tile
  int16 hud_bombs_bg_pos_x;        // Widescreen HUD bomb-backdrop X half-tile
  int16 hud_bombs_bg_pos_y;        // Widescreen HUD bomb-backdrop Y half-tile
  int16 hud_bombs_pos_x;           // Widescreen HUD bomb digits X half-tile
  int16 hud_bombs_pos_y;           // Widescreen HUD bomb digits Y half-tile
  int16 hud_arrows_bg_pos_x;       // Widescreen HUD arrow-backdrop X half-tile
  int16 hud_arrows_bg_pos_y;       // Widescreen HUD arrow-backdrop Y half-tile
  int16 hud_arrow_upgrade_bg_pos_x;// Widescreen HUD silver-arrow backdrop X half-tile
  int16 hud_arrow_upgrade_bg_pos_y;// Widescreen HUD silver-arrow backdrop Y half-tile
  int16 hud_arrows_pos_x;          // Widescreen HUD arrow digits X half-tile
  int16 hud_arrows_pos_y;          // Widescreen HUD arrow digits Y half-tile
  int16 hud_keys_bg_pos_x;         // Widescreen HUD key-backdrop X half-tile
  int16 hud_keys_bg_pos_y;         // Widescreen HUD key-backdrop Y half-tile
  int16 hud_keys_pos_x;            // Widescreen HUD key digit X half-tile
  int16 hud_keys_pos_y;            // Widescreen HUD key digit Y half-tile
  int16 hud_floor_indicator_pos_x; // Widescreen HUD floor-indicator X half-tile
  int16 hud_floor_indicator_pos_y; // Widescreen HUD floor-indicator Y half-tile
  int16 hud_hearts_frame_pos_x;    // Widescreen HUD heart-frame X half-tile
  int16 hud_hearts_frame_pos_y;    // Widescreen HUD heart-frame Y half-tile
  int16 hud_hearts_pos_x;          // Widescreen HUD heart icons X half-tile
  int16 hud_hearts_pos_y;          // Widescreen HUD heart icons Y half-tile
  uint8 hud_shadow_size;           // Rearranged HUD bottom/right shadow size in pixels
  // --- MSU-1 Audio Settings (CD-quality music replacement) ---
  uint8 enable_msu;                // Bitmask of kMsuEnabled_* flags
  bool resume_msu;                 // Resume MSU track position after pause
  bool disable_frame_delay;        // Disable frame pacing (uncapped FPS)
  uint8 msuvolume;                 // MSU volume 0-100, default 100
  // --- Feature Toggles ---
  uint32 features0;                // Bitmask from features.h (kFeatures0_*)

  // --- Asset/Resource Paths ---
  const char *link_graphics;       // Custom Link sprite sheet filename
  char *memory_buffer;             // Backing buffer for INI file string data
  const char *shader;              // GLSL shader filename for post-processing
  const char *msu_path;            // Directory containing MSU-1 PCM tracks
  const char *language;            // Language code for dialogue text selection
} Config;

/* MSU-1 audio mode flags — combinable via bitwise OR.
 * MSU-1 is a SNES enhancement chip that plays CD-quality PCM audio.
 * "Deluxe" is an extended MSU pack; "Opuz" uses Opus-encoded tracks. */
enum {
  kMsuEnabled_Msu = 1,
  kMsuEnabled_MsuDeluxe = 2,
  kMsuEnabled_Opuz = 4,
};
/*
 * Gamepad button IDs — platform-independent abstraction over SDL's
 * gamepad button indices. Maps to standard Xbox-style layout names.
 * "Lb"/"Rb" in INI files are accepted as aliases for L1/R1 (see
 * ParseGamepadButtonName in config.c). L2/R2 are analog triggers
 * treated as digital buttons here.
 */
enum {
  kGamepadBtn_Invalid = -1,
  kGamepadBtn_A,
  kGamepadBtn_B,
  kGamepadBtn_X,
  kGamepadBtn_Y,
  kGamepadBtn_Back,
  kGamepadBtn_Guide,
  kGamepadBtn_Start,
  kGamepadBtn_L3,
  kGamepadBtn_R3,
  kGamepadBtn_L1,
  kGamepadBtn_R1,
  kGamepadBtn_DpadUp,
  kGamepadBtn_DpadDown,
  kGamepadBtn_DpadLeft,
  kGamepadBtn_DpadRight,
  kGamepadBtn_L2,
  kGamepadBtn_R2,
  kGamepadBtn_Count,
};

/* Global configuration instance — zero-initialized, then populated
 * by ParseConfigFile() during startup. Accessed throughout the codebase
 * to query user preferences. */
extern Config g_config;

/* ParseConfigFile — Reads and parses the INI configuration file.
 * If filename is NULL, tries "zelda3.user.ini" first, then "zelda3.ini".
 * After parsing, registers default key/gamepad bindings for any actions
 * not explicitly bound in the INI file. */
void ParseConfigFile(const char *filename);

/* FindCmdForSdlKey — Translates an SDL keycode + modifier state into
 * a kKeys_* command ID via hash table lookup. Returns 0 if the key
 * combination is not bound to any command. */
int FindCmdForSdlKey(int code, int mod);

/* FindCmdForGamepadButton — Translates a gamepad button + held-button
 * modifier bitmask into a kKeys_* command ID. Searches the per-button
 * linked list in priority order (most modifiers first) so that a
 * combo like "L1+A" takes precedence over bare "A". Returns 0 if
 * no matching binding is found. */
int FindCmdForGamepadButton(int button, uint32 modifiers);
