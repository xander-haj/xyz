#define SDL_MAIN_HANDLED
#include <SDL.h>

int main(int argc, char **argv) {
  const char *path = argc > 1 ? argv[1] : "~/.local/share/Z3R/zelda3_assets.dat";
  char message[1024];

  if (SDL_Init(SDL_INIT_VIDEO) != 0)
    return 2;

  SDL_snprintf(message, sizeof(message),
      "Z3R could not find zelda3_assets.dat.\n\n"
      "Generate zelda3_assets.dat from your own legally dumped compatible ROM, "
      "then place it here:\n\n%s", path);
  int shown = SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "Z3R Missing Assets", message, NULL);
  SDL_Quit();
  return shown == 0 ? 0 : 3;
}
