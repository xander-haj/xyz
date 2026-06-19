/*
 * runtime_paths.h - Runtime file location resolver.
 *
 * This module keeps the legacy local-file layout for normal builds, but moves
 * config and saves to Linux XDG directories when the runtime assets are under
 * /opt.
 */
#ifndef ZELDA3_RUNTIME_PATHS_H_
#define ZELDA3_RUNTIME_PATHS_H_

#include "types.h"

/* RuntimePaths_Init: resolves install, config, data, and save paths.
 *
 * Parameters:
 *   config_file - optional --config argument. When non-NULL, its directory is
 *                 treated as the user config/data directory for compatibility
 *                 with AppImage/Flatpak wrapper scripts.
 *
 * Returns nothing. Missing runtime/config/save directories are created when
 * possible.
 */
void RuntimePaths_Init(const char *config_file);

/* RuntimePaths_EnsureSaveDir: creates the configured save directory if needed.
 *
 * Parameters: none.
 *
 * Returns nothing. Failures are reported by the later save write path.
 */
void RuntimePaths_EnsureSaveDir(void);

/* RuntimePath_DefaultConfigFile: returns the default config path.
 *
 * Parameters: none.
 *
 * Returns the absolute zelda3.ini path used by the config loader. This can be
 * a read-only shipped template or a generated fallback.
 */
const char *RuntimePath_DefaultConfigFile(void);

/* RuntimePath_UserConfigFile: returns the editable config path.
 *
 * Parameters: none.
 *
 * Returns the path written by the New Settings menu. Linux /opt installs use a
 * per-user zelda3.user.ini; all other builds keep writing zelda3.ini.
 */
const char *RuntimePath_UserConfigFile(void);

/* RuntimePath_AssetsFile: returns the shared asset blob path.
 *
 * Parameters: none.
 *
 * Returns the absolute zelda3_assets.dat path used by LoadAssets.
 */
const char *RuntimePath_AssetsFile(void);

/* RuntimePath_BpsFile: returns the shared fallback BPS asset patch path.
 *
 * Parameters: none.
 *
 * Returns the absolute zelda3_assets.bps path beside the runtime assets.
 */
const char *RuntimePath_BpsFile(void);

/* RuntimePath_BpsSourceRomFile: returns the shared fallback ROM source path.
 *
 * Parameters: none.
 *
 * Returns the absolute zelda3.sfc path beside the runtime assets.
 */
const char *RuntimePath_BpsSourceRomFile(void);

/* RuntimePath_SaveSlotFile: formats a save-state slot path.
 *
 * Parameters:
 *   which - save slot index.
 *
 * Returns a pointer to an internal buffer containing the absolute save path.
 */
const char *RuntimePath_SaveSlotFile(int which);

/* RuntimePath_ReferenceSaveFile: formats a bundled reference save path.
 *
 * Parameters:
 *   filename - reference save filename from the built-in chapter list.
 *
 * Returns a pointer to an internal buffer under the shared runtime directory.
 */
const char *RuntimePath_ReferenceSaveFile(const char *filename);

/* RuntimePath_SramFile: returns the SRAM save path.
 *
 * Parameters: none.
 *
 * Returns the absolute path to sram.dat in the resolved save directory.
 */
const char *RuntimePath_SramFile(void);

/* RuntimePath_SramBackupFile: returns the SRAM backup path.
 *
 * Parameters: none.
 *
 * Returns the absolute path to sram.bak in the resolved save directory.
 */
const char *RuntimePath_SramBackupFile(void);

#endif  // ZELDA3_RUNTIME_PATHS_H_
