# Discord Server
https://discord.gg/EQ6E7P3cC8

# Z3R

Z3R is a fork of the `zelda3` C reimplementation By SnesRev this project's widescreen,
HUD, settings, and early randomizer work. The source builds a native executable
and a generated runtime asset file named `zelda3_assets.dat`.

This repository does not replace owning the game. You need your own legally
dumped copy of `Legend of Zelda, The - A Link to the Past (USA)` to extract the
runtime assets. Do not commit or redistribute ROMs, generated asset packs, save
files, MSU packs, or local INI overrides.

## What You Need

All platforms need:

- Git, so you can clone and update the project.
- Python 3, so the asset extraction and randomizer scripts can run.
- A Python virtual environment with the packages in `requirements.txt`:
  `Pillow` and `PyYAML`.
- A C build path for your operating system.
- SDL2 development files or SDL2 runtime files, depending on the build path.
- A clean USA ALTTP ROM placed at the project root as `zelda3.sfc` or
  `zelda3.smc`.

Useful installer links:

- Git: <https://git-scm.com/downloads>
- Python: <https://www.python.org/downloads/>
- SDL releases: <https://github.com/libsdl-org/SDL/releases>
- Visual Studio Build Tools / MSBuild:
  <https://learn.microsoft.com/en-us/visualstudio/msbuild/msbuild>
- PowerShell:
  <https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell-on-windows>
- Tiny C Compiler for the Windows TCC route:
  <https://github.com/FitzRoyX/tinycc/releases/tag/tcc_20251005>

## Platform Setup

### macOS

Install Apple command line tools first. They provide `make`, `clang`, and other
basic build tools:

```sh
xcode-select --install
```

Install Git, Python 3, and SDL2. If you already use Homebrew, the usual route is:

```sh
brew install git python sdl2
```

After installation, reopen Terminal and confirm these commands work:

```sh
git --version
python3 --version
make --version
sdl2-config --version
```

### Linux

Install Git, Python 3, Python venv support, Make/build tools, and SDL2
development files through your distribution package manager.

On Debian or Ubuntu:

```sh
sudo apt-get install git python3 python3-venv build-essential libsdl2-dev
```

On other distributions, use the equivalent packages. Common names are `git`,
`python3`, `python3-venv`, `base-devel` or `build-essential`, and either
`libsdl2-dev` or `sdl2-devel`.

Confirm the tools:

```sh
git --version
python3 --version
make --version
sdl2-config --version
```

### Windows

Install Git for Windows and Python 3 first. In the Python installer, enable the
`Add python.exe to PATH` checkbox. Then open a new shell and check the tools.

PowerShell:

```powershell
git --version
py --version
python --version
```

Git Bash or MSYS2 Bash:

```sh
git --version
py --version
python --version
```

Choose one build route:

- Visual Studio route: install Visual Studio or Build Tools for Visual Studio
  with the `Desktop development with C++` workload. This route also restores
  the native SDL2 NuGet packages listed in `packages.config`.
- MSYS2 route: install the MSYS2 build tools and SDL2 packages, then use `make`.
- TCC route: place `tcc.exe` at `third_party\tcc\tcc.exe`, place `SDL2.dll` at
  `third_party\SDL2-2.26.3\lib\x64\SDL2.dll`, then use `run_with_tcc.bat`.

The TCC helper script checks specifically for the `SDL2-2.26.3` folder name.
If you download a newer SDL2 package, keep the expected folder layout or update
the script intentionally.

## Fresh Clone

Clone the project with submodules:

```sh
git clone --recursive https://github.com/xander-haj/Z3R
cd Z3R
```

If you already cloned without `--recursive`, initialize submodules before
building:

```sh
git submodule update --init --recursive
```

## Python Environment

Create a virtual environment from the project root.

macOS and Linux:

```sh
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -3 -m venv venv
.\venv\Scripts\python -m pip install -r requirements.txt
```

Windows Git Bash or MSYS2 Bash:

```sh
python -m venv venv
./venv/Scripts/python -m pip install -r requirements.txt
```

If PowerShell blocks activation scripts, you can still use the venv Python
directly with `.\venv\Scripts\python` and avoid changing execution policy.

## ROM and Asset Extraction

Place your legally dumped USA ROM at the project root:

```text
Z3R/
  zelda3.sfc
  assets/
  src/
  ...
```

The asset tool automatically searches for `zelda3.sfc` or `zelda3.smc` in the
project root. You can also pass a ROM path relative to the project root:

```sh
python assets/restool.py --extract-from-rom -r roms/zelda3.sfc
```

Normal extraction:

macOS and Linux:

```sh
venv/bin/python assets/restool.py --extract-from-rom
```

Windows PowerShell:

```powershell
.\venv\Scripts\python assets\restool.py --extract-from-rom
```

Windows Git Bash or MSYS2 Bash:

```sh
./venv/Scripts/python assets/restool.py --extract-from-rom
```

This writes `zelda3_assets.dat` at the project root and refreshes extracted
YAML, PNG, TXT, and sound files under `assets/`.

The normal extraction mode accepts only the USA ROM hash. Multi-language
dialogue extraction is a separate workflow described below.

## Build and Run

### macOS

From the project root:

```sh
make -j$(nproc)
```

### Linux

From the project root:

```sh
make -j$(nproc)
```

After building on macOS or Linux, run the game from the project root:

```sh
./zelda3
```

### Windows with Visual Studio

1. Extract assets first so `zelda3_assets.dat` exists at the project root.
2. Open `Zelda3.sln`.
3. Let Visual Studio restore the NuGet packages from `packages.config`.
4. Select `Release` and `x64`.
5. Build the `zelda3` project.
6. The executable is written under `bin\x64-Release\`.

The executable can find `zelda3.ini` when launched from `bin\x64-Release\`
because the program searches up to two parent directories for the project root.
If you move the executable somewhere else, keep `zelda3.ini` and
`zelda3_assets.dat` beside it.

### Windows with TCC

The lightweight TCC route builds and launches from a batch file:

PowerShell:

```powershell
.\run_with_tcc.bat
```

Git Bash or MSYS2 Bash:

```sh
cmd.exe /c run_with_tcc.bat
```

Before running it, make sure all of these exist:

```text
third_party\tcc\tcc.exe
third_party\SDL2-2.26.3\lib\x64\SDL2.dll
zelda3_assets.dat
```

`run_with_tcc.bat` builds `zelda3.exe`, copies `SDL2.dll` to the project root,
and starts the game.

### Clean Rebuild

macOS and Linux:

```sh
make clean && make -j$(nproc)
```

After pulling updates, rebuild the executable and regenerate assets if any
source, asset script, extracted YAML, or INI behavior changed.

## Randomizer Workflow

The current randomizer is an early conservative pass. It randomizes dungeon
chest item values in the extracted dungeon YAML before `zelda3_assets.dat` is
compiled. It does not yet randomize overworld checks, pot secrets, NPC rewards,
shops, boss prizes, entrances, exits, holes, sprites, or room layouts.

Fresh safe-mode workflow:

```sh
python assets/restool.py --extract-from-rom --no-build
python assets/restool-randomize.py --generate-masterlist
python assets/restool-randomize.py --seed my-first-seed --mode safe
python assets/restool.py
```

Then run the game normally. The compiled `zelda3_assets.dat` now contains the
randomized chest data.

Important notes:

- The same seed produces the same randomization.
- If `--seed` is omitted, the script generates and prints a random seed.
- Safe Mode currently keeps Lamp or Fire Rod accessible in an early light
  location before the castle throne.
- Small-key items and big-key-locked chest locations stay fixed unless you pass
  `--include-small-keys` or `--include-big-chests`.
- Spoiler logs are written to `assets/randomizer-spoilers/<seed>.md` unless
  `--no-spoiler` is used.
- Running `python assets/restool.py --extract-from-rom` after randomizing will
  overwrite the randomized YAML with clean ROM data before compiling.

Useful randomizer commands:

```sh
python assets/restool-randomize.py --seed 12345 --dry-run
python assets/restool-randomize.py --seed 12345 --exclude-room 260
python assets/restool-randomize.py --seed 12345 --exclude-item 0x32
python assets/restool-randomize.py --restore-vanilla
```

More detail lives in `assets/randomizer-instructions.md`.

## Multi-Language Assets

The default build uses the USA ROM and English assets. To build extra dialogue
assets, keep the USA ROM at the root and provide a supported localized ROM.

Example for German:

```sh
python assets/restool.py --extract-dialogue -r German.sfc
python assets/restool.py --languages=de
```

Then select the language in `zelda3.user.ini`:

```ini
!include zelda3.ini

[General]
Language = de
```

Supported language codes in the asset scripts include `de`, `fr`, `fr-c`, `en`,
`es`, `pl`, `pt`, `redux`, `nl`, and `sv`.

## Configuration Files

The default config is `zelda3.ini`. The executable tries `zelda3.user.ini`
first, then falls back to `zelda3.ini`. A good personal config starts by
including the default file, then overrides only what you want:

```ini
!include zelda3.ini

[Graphics]
WindowScale = 4
Fullscreen = 0

[General]
ExtendedAspectRatio = 16:9
FillExtendedAspectRatioBorders = 1

[Features]
ItemSwitchLR = 1
NewSettingsMenu = 1
```

`zelda3.user.ini` is ignored by the repository's `.gitignore`, so it is the
right place for personal settings.

### General

- `Autosave`: save SRAM on quit and reload it on startup.
- `DisplayPerfInTitle`: show performance info in the window title.
- `ExtendedAspectRatio`: use `4:3`, `16:9`, `16:10`, or `18:9`.
- `ExtendedAspectRatio` can also include `extend_y`, `unchanged_sprites`, or
  `no_visual_fixes` as comma-separated tokens.
- `FillExtendedAspectRatioBorders`: fills widescreen side bars from nearby
  rendered art. It only takes effect when `ExtendedAspectRatio` is active.
- `DisableFrameDelay`: removes the per-frame SDL delay. Leave it off unless you
  know your display and sync setup behave correctly.
- `Language`: selects compiled language assets, such as `de`.

### Graphics

- `WindowSize`: `Auto` or an explicit size like `1280x720`.
- `Fullscreen`: `0` windowed, `1` desktop fullscreen, `2` fullscreen with mode
  change.
- `WindowScale`: integer scale factor for the window.
- `OutputMethod`: `SDL`, `SDL-Software`, `OpenGL`, or `OpenGL ES`.
- `NewRenderer`: enables the newer PPU renderer path.
- `EnhancedMode7`: renders world map Mode 7 at higher resolution.
- `IgnoreAspectRatio`: stretches instead of preserving the aspect ratio.
- `NoSpriteLimits`: removes the original per-scanline sprite limit.
- `LinkGraphics`: path to a `.zspr` Link sprite file.
- `Shader`: path to a `.glsl` or `.glslp` shader. Shaders require `OpenGL`.
- `LinearFiltering`: smooths scaled pixels. Leave it off for crisp pixels.
- `DimFlashes`: reduces some flashing effects.

### Sound

- `EnableAudio`: master audio toggle.
- `AudioFreq`: sample rate, commonly `44100` or `48000`.
- `AudioChannels`: `1` mono or `2` stereo.
- `AudioSamples`: audio buffer size. Try `1024` if sound crackles.
- `EnableMSU`: `false`, `true`, `deluxe`, `opuz`, or `deluxe-opuz`.
- `MSUPath`: prefix for MSU files. The track number and extension are appended.
- `ResumeMSU`: resumes supported MSU tracks when returning to an area.
- `MSUVolume`: MSU playback volume from `0%` to `100%`.

PCM MSU packs expect `AudioFreq = 44100`. OPUZ packs expect `AudioFreq = 48000`.

### Features

- `ItemSwitchLR`: enables item switching on L/R and item assignment in the
  inventory.
- `ItemSwitchLRLimit`: limits L/R cycling to the first four items.
- `TurnWhileDashing`, `MirrorToDarkworld`, `CollectItemsWithSword`,
  `BreakPotsWithSword`, `MoreActiveBombs`, and `CarryMoreRupees` are gameplay
  convenience toggles.
- `MiscBugFixes` enables bug fixes that preserve normal game intent.
- `GameChangingBugFixes` enables stronger fixes that can change behavior.
- `RearrangeHUD` moves the HUD when widescreen is active.
- `NewSettingsMenu` enables the in-game settings menu on the configured key or
  gamepad button.

HUD position settings use tile coordinates in the widescreen viewport. In 16:9,
useful X values are roughly `0` through `49`, and useful Y values are roughly
`0` through `29`. The sample `zelda3.ini` contains this fork's current HUD
layout.

### KeyMap and GamepadMap

`[KeyMap]` binds keyboard keys. The `Controls` order is:

```text
Up, Down, Left, Right, Select, Start, A, B, X, Y, L, R
```

SDL key names are accepted, including modifiers like `Shift+`, `Ctrl+`, and
`Alt+`.

`[GamepadMap]` uses button names such as `DpadUp`, `DpadDown`, `Back`, `Start`,
`A`, `B`, `X`, `Y`, `L1`, `R1`, `Lb`, `Rb`, `L2`, and `R2`.

## Launcher Dependency Checklist

The launcher's manual install guide checks the same dependencies described
above:

- macOS: Git, Python 3, Make, and SDL2 development files.
- Windows: Git, Python 3, MSBuild or another selected build path, PowerShell,
  TCC for the lightweight route, and SDL2 for runtime/TCC.
- Linux: Git, Python 3, Make/build tools, and SDL2 development files.

The launcher should guide users to install system tools themselves. It should
not install Git, Python, Visual Studio, Build Tools, Homebrew, TCC, SDL2, or
distribution packages automatically.

## Troubleshooting

`Could not find any ROMs`

Put `zelda3.sfc` or `zelda3.smc` at the project root, or pass `-r` with a path
relative to the project root.

`ROM with hash ... not supported`

Normal extraction expects the USA release:
`Legend of Zelda, The - A Link to the Past (USA)`.

`No module named PIL` or `No module named yaml`

Use the virtual environment Python and install `requirements.txt`.

`sdl2-config: command not found`

Install SDL2 development files. On macOS this is usually `brew install sdl2`.
On Debian or Ubuntu this is `sudo apt-get install libsdl2-dev`.

Visual Studio reports missing `packages\sdl2...targets`

Restore NuGet packages for `Zelda3.sln`. Visual Studio usually prompts for
this automatically when the solution opens.

TCC says `third_party\tcc\tcc.exe` is missing

Download the Windows TCC ZIP and place `tcc.exe` under `third_party\tcc\`.

TCC says SDL is not unzipped properly

Place `SDL2.dll` at `third_party\SDL2-2.26.3\lib\x64\SDL2.dll`.

The game starts but cannot find config or assets

Launch it from the project root or from `bin\x64-Release\`. If you move the
executable elsewhere, copy `zelda3.ini` and `zelda3_assets.dat` beside it.

## License

The project source is MIT licensed. See `LICENSE.txt` for the main project
license and bundled Opus license text.
