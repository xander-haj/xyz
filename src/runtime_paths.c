/*
 * runtime_paths.c - Runtime file location resolver.
 *
 * The original port assumed config, saves, and assets all lived together. Keep
 * that behavior for normal local builds and release wrappers, but use per-user
 * config/save directories for Linux installs under /opt.
 */
#include "runtime_paths.h"

#include "default_config.h"
#include "util.h"

#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <SDL.h>
#ifdef _WIN32
#include <direct.h>
#define chdir _chdir
#else
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>
#endif

/* Per-user app directory name for Linux XDG paths. */
static const char kRuntimeAppDir[] = "zelda3reborn-beta";
static const char kRuntimeDefaultConfigName[] = "zelda3.ini";
static const char kRuntimeUserConfigName[] = "zelda3.user.ini";
static const char kRuntimeAssetsName[] = "zelda3_assets.dat";
static const char kRuntimeBpsName[] = "zelda3_assets.bps";
static const char kRuntimeBpsSourceRomName[] = "zelda3.sfc";

static char g_runtime_dir[4096];
static char g_config_dir[4096];
static char g_data_dir[4096];
static char g_save_dir[4096];
static char g_default_config_file[4096];
static char g_user_config_file[4096];
static char g_assets_file[4096];
static char g_bps_file[4096];
static char g_bps_source_rom_file[4096];
static char g_path_scratch[4096];
static bool g_use_user_override_config_file;

/* RuntimePath_GetCwd: reads the current working directory with the host CRT.
 *
 * Parameters:
 *   dst      - destination path buffer.
 *   dst_size - destination capacity.
 *
 * Returns dst on success, or NULL when the platform call fails.
 */
static char *RuntimePath_GetCwd(char *dst, size_t dst_size) {
#ifdef _WIN32
  if (dst_size > (size_t)INT_MAX) {
    errno = ERANGE;
    return NULL;
  }
  return _getcwd(dst, (int)dst_size);
#else
  return getcwd(dst, dst_size);
#endif
}

/* RuntimePath_IsAbsolute: checks whether a path is absolute on the host OS.
 *
 * Parameters:
 *   path - path string to inspect.
 *
 * Returns true when path starts at a filesystem root or Windows drive root.
 */
static bool RuntimePath_IsAbsolute(const char *path) {
  if (!path || !path[0])
    return false;
#ifdef _WIN32
  if ((path[0] >= 'A' && path[0] <= 'Z') || (path[0] >= 'a' && path[0] <= 'z'))
    return path[1] == ':' && (path[2] == '/' || path[2] == '\\');
  return (path[0] == '/' || path[0] == '\\') && (path[1] == '/' || path[1] == '\\');
#else
  return path[0] == '/';
#endif
}

/* RuntimePath_Copy: copies a path into a fixed path buffer.
 *
 * Parameters:
 *   dst      - destination path buffer.
 *   dst_size - destination capacity.
 *   src      - source path.
 *
 * Returns nothing. Overlong paths are truncated but remain NUL-terminated.
 */
static void RuntimePath_Copy(char *dst, size_t dst_size, const char *src) {
  snprintf(dst, dst_size, "%s", src ? src : "");
}

/* RuntimePath_Join: joins a directory and filename with one slash.
 *
 * Parameters:
 *   dst      - destination path buffer.
 *   dst_size - destination capacity.
 *   dir      - parent directory.
 *   name     - child filename or relative path.
 *
 * Returns nothing. Forward slashes are accepted by the Windows CRT too.
 */
static void RuntimePath_Join(char *dst, size_t dst_size, const char *dir, const char *name) {
  const char *child = name ? name : "";
  if (!dir || !dir[0]) {
    RuntimePath_Copy(dst, dst_size, child);
    return;
  }
  size_t len = strlen(dir);
  const char *sep = (len != 0 && (dir[len - 1] == '/' || dir[len - 1] == '\\')) ? "" : "/";
  snprintf(dst, dst_size, "%s%s%s", dir, sep, child);
}

/* RuntimePath_LastSeparator: finds the final path separator in a path.
 *
 * Parameters:
 *   path - source path.
 *
 * Returns a pointer inside path, or NULL if no separator exists.
 */
static const char *RuntimePath_LastSeparator(const char *path) {
  const char *last = NULL;
  for (const char *p = path; *p; p++) {
    if (*p == '/' || *p == '\\')
      last = p;
  }
  return last;
}

/* RuntimePath_Dirname: extracts a path's parent directory.
 *
 * Parameters:
 *   dst      - destination path buffer.
 *   dst_size - destination capacity.
 *   path     - source file path.
 *
 * Returns nothing. Paths without a separator resolve to ".".
 */
static void RuntimePath_Dirname(char *dst, size_t dst_size, const char *path) {
  const char *last = RuntimePath_LastSeparator(path);
  if (!last) {
    RuntimePath_Copy(dst, dst_size, ".");
    return;
  }
  size_t len = (size_t)(last - path);
  if (len == 0)
    len = 1;
#ifdef _WIN32
  if (len == 2 && path[1] == ':' && (path[2] == '/' || path[2] == '\\'))
    len = 3;
#endif
  if (len >= dst_size)
    len = dst_size - 1;
  memcpy(dst, path, len);
  dst[len] = 0;
}

/* RuntimePath_FileExists: checks whether a file can be opened for reading.
 *
 * Parameters:
 *   filename - path to test.
 *
 * Returns true when the file opens successfully.
 */
static bool RuntimePath_FileExists(const char *filename) {
  FILE *f = fopen(filename, "rb");
  if (!f)
    return false;
  fclose(f);
  return true;
}

/* RuntimePath_MkdirOne: creates one directory level.
 *
 * Parameters:
 *   path - directory path to create.
 *
 * Returns true when the directory exists or was created.
 */
static bool RuntimePath_MkdirOne(const char *path) {
#ifdef _WIN32
  if (_mkdir(path) == 0 || errno == EEXIST)
    return true;
#else
  if (mkdir(path, 0700) == 0 || errno == EEXIST)
    return true;
#endif
  return false;
}

/* RuntimePath_Mkdirs: recursively creates a directory path.
 *
 * Parameters:
 *   path - directory path to create.
 *
 * Returns true when the full path exists or was created.
 */
static bool RuntimePath_Mkdirs(const char *path) {
  char tmp[4096];
  RuntimePath_Copy(tmp, sizeof(tmp), path);
  size_t len = strlen(tmp);
  if (len == 0)
    return false;
  size_t start = 1;
#ifdef _WIN32
  if (((tmp[0] >= 'A' && tmp[0] <= 'Z') || (tmp[0] >= 'a' && tmp[0] <= 'z')) && tmp[1] == ':')
    start = 3;
  else if ((tmp[0] == '/' || tmp[0] == '\\') && (tmp[1] == '/' || tmp[1] == '\\')) {
    start = 2;
    while (tmp[start] && tmp[start] != '/' && tmp[start] != '\\')
      start++;
    if (tmp[start])
      start++;
    while (tmp[start] && tmp[start] != '/' && tmp[start] != '\\')
      start++;
    if (tmp[start])
      start++;
  }
#endif
  for (size_t i = start; i < len; i++) {
    if (tmp[i] != '/' && tmp[i] != '\\')
      continue;
    char old = tmp[i];
    tmp[i] = 0;
    if (!RuntimePath_MkdirOne(tmp))
      return false;
    tmp[i] = old;
  }
  return RuntimePath_MkdirOne(tmp);
}

/* RuntimePath_AbsoluteFromCwd: converts a path to an absolute path.
 *
 * Parameters:
 *   dst      - destination path buffer.
 *   dst_size - destination capacity.
 *   path     - absolute or cwd-relative source path.
 *
 * Returns nothing.
 */
static void RuntimePath_AbsoluteFromCwd(char *dst, size_t dst_size, const char *path) {
  if (RuntimePath_IsAbsolute(path)) {
    RuntimePath_Copy(dst, dst_size, path);
    return;
  }
  char cwd[4096];
  if (!RuntimePath_GetCwd(cwd, sizeof(cwd))) {
    RuntimePath_Copy(dst, dst_size, path);
    return;
  }
  RuntimePath_Join(dst, dst_size, cwd, path);
}

/* RuntimePath_EnvOrFallback: resolves one platform user base directory.
 *
 * Parameters:
 *   dst       - destination path buffer.
 *   dst_size  - destination capacity.
 *   env_name  - preferred environment variable.
 *   fallback  - fallback path, usually relative to HOME or USERPROFILE.
 *
 * Returns nothing.
 */
static void RuntimePath_EnvOrFallback(char *dst, size_t dst_size, const char *env_name, const char *fallback) {
  const char *value = getenv(env_name);
  if (value && value[0] && RuntimePath_IsAbsolute(value)) {
    RuntimePath_Copy(dst, dst_size, value);
    return;
  }
  RuntimePath_Copy(dst, dst_size, fallback);
}

/* RuntimePath_IsOptRuntimeDir: checks whether the runtime dir is a Linux /opt
 * install.
 *
 * Parameters:
 *   dir - resolved runtime directory.
 *
 * Returns true only for non-wrapper Linux installs rooted in /opt.
 */
static bool RuntimePath_IsOptRuntimeDir(const char *dir) {
#if !defined(_WIN32) && !defined(__APPLE__) && !defined(__SWITCH__)
  return strcmp(dir, "/opt") == 0 || strncmp(dir, "/opt/", 5) == 0;
#else
  (void)dir;
  return false;
#endif
}

/* RuntimePath_InitUserDirs: resolves config and data directories.
 *
 * Parameters:
 *   explicit_config   - optional absolute --config path.
 *   use_xdg_user_dirs - true for Linux /opt installs that need per-user files.
 *
 * Returns nothing. Explicit config paths keep wrapper-managed layouts portable.
 */
static void RuntimePath_InitUserDirs(const char *explicit_config, bool use_xdg_user_dirs) {
  if (explicit_config) {
    RuntimePath_Dirname(g_config_dir, sizeof(g_config_dir), explicit_config);
    RuntimePath_Copy(g_data_dir, sizeof(g_data_dir), g_config_dir);
    return;
  }

  if (!use_xdg_user_dirs) {
    RuntimePath_Copy(g_config_dir, sizeof(g_config_dir), g_runtime_dir);
    RuntimePath_Copy(g_data_dir, sizeof(g_data_dir), g_runtime_dir);
    return;
  }

  char config_base[4096], data_base[4096];
#if !defined(_WIN32) && !defined(__APPLE__) && !defined(__SWITCH__)
  const char *home = getenv("HOME");
  char config_fallback[4096], data_fallback[4096];
  snprintf(config_fallback, sizeof(config_fallback), "%s/.config", home ? home : ".");
  snprintf(data_fallback, sizeof(data_fallback), "%s/.local/share", home ? home : ".");
  RuntimePath_EnvOrFallback(config_base, sizeof(config_base), "XDG_CONFIG_HOME", config_fallback);
  RuntimePath_EnvOrFallback(data_base, sizeof(data_base), "XDG_DATA_HOME", data_fallback);
#else
  RuntimePath_Copy(config_base, sizeof(config_base), g_runtime_dir);
  RuntimePath_Copy(data_base, sizeof(data_base), g_runtime_dir);
#endif
  RuntimePath_Join(g_config_dir, sizeof(g_config_dir), config_base, kRuntimeAppDir);
  RuntimePath_Join(g_data_dir, sizeof(g_data_dir), data_base, kRuntimeAppDir);
}

/* RuntimePath_CandidateHasAssets: tests whether a directory has shared assets.
 *
 * Parameters:
 *   dir - candidate runtime directory.
 *
 * Returns true when the directory can provide zelda3_assets.dat directly or
 * through the BPS fallback path.
 */
static bool RuntimePath_CandidateHasAssets(const char *dir) {
  char path[4096];
  RuntimePath_Join(path, sizeof(path), dir, kRuntimeAssetsName);
  if (RuntimePath_FileExists(path))
    return true;
  RuntimePath_Join(path, sizeof(path), dir, kRuntimeBpsName);
  return RuntimePath_FileExists(path);
}

/* RuntimePath_CandidateHasDefaultConfig: tests whether a directory has the
 * shipped default config template.
 *
 * Parameters:
 *   dir - candidate runtime directory.
 *
 * Returns true when zelda3.ini is present in the candidate directory.
 */
static bool RuntimePath_CandidateHasDefaultConfig(const char *dir) {
  char path[4096];
  RuntimePath_Join(path, sizeof(path), dir, kRuntimeDefaultConfigName);
  return RuntimePath_FileExists(path);
}

/* RuntimePath_CandidateMatches: checks a candidate according to the current
 * runtime-directory search phase.
 *
 * Parameters:
 *   dir            - candidate runtime directory.
 *   require_assets - true to accept only asset-bearing directories.
 *
 * Returns true when the candidate is acceptable for this search phase.
 */
static bool RuntimePath_CandidateMatches(const char *dir, bool require_assets) {
  return require_assets ? RuntimePath_CandidateHasAssets(dir) : RuntimePath_CandidateHasDefaultConfig(dir);
}

/* RuntimePath_FindFromCwd: walks the cwd and two parents for runtime files.
 *
 * Parameters:
 *   dst            - destination directory buffer.
 *   dst_size       - destination capacity.
 *   require_assets - true to accept only asset-bearing directories.
 *
 * Returns true when a candidate was found.
 */
static bool RuntimePath_FindFromCwd(char *dst, size_t dst_size, bool require_assets) {
  char buf[4096];
  if (!RuntimePath_GetCwd(buf, sizeof(buf)))
    return false;
  size_t pos = strlen(buf);
  for (int step = 0; pos != 0 && step < 3; step++) {
    if (RuntimePath_CandidateMatches(buf, require_assets)) {
      RuntimePath_Copy(dst, dst_size, buf);
      return true;
    }
    pos--;
    while (pos != 0 && buf[pos] != '/' && buf[pos] != '\\')
      pos--;
    buf[pos] = 0;
  }
  return false;
}

/* RuntimePath_FindFromBasePath: checks the executable directory reported by
 * SDL.
 *
 * Parameters:
 *   dst            - destination directory buffer.
 *   dst_size       - destination capacity.
 *   require_assets - true to accept only asset-bearing directories.
 *
 * Returns true when SDL reports a usable executable/runtime directory.
 */
static bool RuntimePath_FindFromBasePath(char *dst, size_t dst_size, bool require_assets) {
  char *base_path = SDL_GetBasePath();
  if (!base_path)
    return false;

  size_t len = strlen(base_path);
  while (len != 0 && (base_path[len - 1] == '/' || base_path[len - 1] == '\\'))
    base_path[--len] = 0;
  bool found = RuntimePath_CandidateMatches(base_path, require_assets);
  if (found)
    RuntimePath_Copy(dst, dst_size, base_path);
  SDL_free(base_path);
  return found;
}

/* RuntimePath_FindRuntimeDir: locates the shared runtime/install directory.
 *
 * Parameters:
 *   dst      - destination directory buffer.
 *   dst_size - destination capacity.
 *
 * Returns nothing. Falls back to cwd when no stronger candidate exists.
 */
static void RuntimePath_FindRuntimeDir(char *dst, size_t dst_size) {
  if (RuntimePath_FindFromCwd(dst, dst_size, true))
    return;
  if (RuntimePath_FindFromBasePath(dst, dst_size, true))
    return;
  if (RuntimePath_FindFromCwd(dst, dst_size, false))
    return;
  if (RuntimePath_FindFromBasePath(dst, dst_size, false))
    return;

  if (!RuntimePath_GetCwd(dst, dst_size))
    RuntimePath_Copy(dst, dst_size, ".");
}

/* RuntimePath_CopyFile: copies one small text/binary file.
 *
 * Parameters:
 *   dst - destination path.
 *   src - source path.
 *
 * Returns true when the copy succeeded.
 */
static bool RuntimePath_CopyFile(const char *dst, const char *src) {
  size_t len = 0;
  uint8 *data = ReadWholeFile(src, &len);
  if (!data)
    return false;
  FILE *f = fopen(dst, "wb");
  if (!f) {
    free(data);
    return false;
  }
  bool ok = fwrite(data, 1, len, f) == len;
  if (fclose(f) != 0)
    ok = false;
  free(data);
  return ok;
}

/* RuntimePath_EnsureDefaultConfig: creates the selected writable zelda3.ini if
 * absent.
 *
 * Parameters:
 *   template_file - optional shipped template file from the runtime directory.
 *
 * Returns nothing.
 */
static void RuntimePath_EnsureDefaultConfig(const char *template_file) {
  if (RuntimePath_FileExists(g_default_config_file))
    return;
  bool copied = false;
  if (template_file && strcmp(template_file, g_default_config_file) != 0)
    copied = RuntimePath_CopyFile(g_default_config_file, template_file);
  if (copied)
    return;

  FILE *f = fopen(g_default_config_file, "wb");
  if (!f) {
    fprintf(stderr, "Warning: Unable to create %s\n", g_default_config_file);
    return;
  }
  size_t config_size = sizeof(kDefaultZelda3Ini) - 1;
  bool wrote_config = fwrite(kDefaultZelda3Ini, 1, config_size, f) == config_size;
  if (fclose(f) != 0)
    wrote_config = false;
  if (!wrote_config)
    fprintf(stderr, "Warning: Unable to write %s\n", g_default_config_file);
}

void RuntimePaths_Init(const char *config_file) {
  char explicit_config[4096] = {0};
  if (config_file)
    RuntimePath_AbsoluteFromCwd(explicit_config, sizeof(explicit_config), config_file);

  RuntimePath_FindRuntimeDir(g_runtime_dir, sizeof(g_runtime_dir));
  bool use_xdg_user_dirs = config_file == NULL && RuntimePath_IsOptRuntimeDir(g_runtime_dir);
  g_use_user_override_config_file = use_xdg_user_dirs;
  RuntimePath_InitUserDirs(config_file ? explicit_config : NULL, use_xdg_user_dirs);
  RuntimePath_Mkdirs(g_config_dir);
  RuntimePath_Mkdirs(g_data_dir);
  RuntimePath_Join(g_save_dir, sizeof(g_save_dir), g_data_dir, "saves");
  RuntimePath_Mkdirs(g_save_dir);

  char runtime_default_config[4096];
  RuntimePath_Join(runtime_default_config, sizeof(runtime_default_config), g_runtime_dir, kRuntimeDefaultConfigName);
  bool has_runtime_default_config = RuntimePath_FileExists(runtime_default_config);

  if (config_file)
    RuntimePath_Copy(g_default_config_file, sizeof(g_default_config_file), explicit_config);
  else if (has_runtime_default_config)
    RuntimePath_Copy(g_default_config_file, sizeof(g_default_config_file), runtime_default_config);
  else
    RuntimePath_Join(g_default_config_file, sizeof(g_default_config_file), g_config_dir, kRuntimeDefaultConfigName);
  if (g_use_user_override_config_file)
    RuntimePath_Join(g_user_config_file, sizeof(g_user_config_file), g_config_dir, kRuntimeUserConfigName);
  else
    RuntimePath_Copy(g_user_config_file, sizeof(g_user_config_file), g_default_config_file);

  if (config_file || !has_runtime_default_config)
    RuntimePath_EnsureDefaultConfig(has_runtime_default_config ? runtime_default_config : NULL);

  RuntimePath_Join(g_assets_file, sizeof(g_assets_file), g_runtime_dir, kRuntimeAssetsName);
  if (!RuntimePath_FileExists(g_assets_file))
    RuntimePath_Join(g_assets_file, sizeof(g_assets_file), g_data_dir, kRuntimeAssetsName);
  RuntimePath_Join(g_bps_file, sizeof(g_bps_file), g_runtime_dir, kRuntimeBpsName);
  RuntimePath_Join(g_bps_source_rom_file, sizeof(g_bps_source_rom_file), g_runtime_dir, kRuntimeBpsSourceRomName);

  if (chdir(g_runtime_dir) != 0)
    fprintf(stderr, "Warning: Unable to enter runtime directory %s\n", g_runtime_dir);
}

void RuntimePaths_EnsureSaveDir(void) {
  RuntimePath_Mkdirs(g_save_dir);
}

const char *RuntimePath_DefaultConfigFile(void) {
  return g_default_config_file;
}

const char *RuntimePath_UserConfigFile(void) {
  return g_user_config_file;
}

const char *RuntimePath_AssetsFile(void) {
  return g_assets_file;
}

const char *RuntimePath_BpsFile(void) {
  return g_bps_file;
}

const char *RuntimePath_BpsSourceRomFile(void) {
  return g_bps_source_rom_file;
}

const char *RuntimePath_SaveSlotFile(int which) {
  char filename[32];
  snprintf(filename, sizeof(filename), "save%d.sav", which);
  RuntimePath_Join(g_path_scratch, sizeof(g_path_scratch), g_save_dir, filename);
  return g_path_scratch;
}

const char *RuntimePath_ReferenceSaveFile(const char *filename) {
  char ref_dir[4096];
  RuntimePath_Join(ref_dir, sizeof(ref_dir), g_runtime_dir, "saves/ref");
  RuntimePath_Join(g_path_scratch, sizeof(g_path_scratch), ref_dir, filename);
  return g_path_scratch;
}

const char *RuntimePath_SramFile(void) {
  RuntimePath_Join(g_path_scratch, sizeof(g_path_scratch), g_save_dir, "sram.dat");
  return g_path_scratch;
}

const char *RuntimePath_SramBackupFile(void) {
  RuntimePath_Join(g_path_scratch, sizeof(g_path_scratch), g_save_dir, "sram.bak");
  return g_path_scratch;
}
