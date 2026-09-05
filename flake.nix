{
  description = "Arduino development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        wheelLibs = with pkgs; [
          stdenv.cc.cc.lib
          libGL
          glib
          zlib
          libdrm
          mesa
          xorg.libX11
          xorg.libXext
          xorg.libXcomposite
          xorg.libXdamage
          xorg.libXfixes
          xorg.libXrender
          xorg.libXrandr
          xorg.libxcb
          xorg.libxkbfile
          udev
        ];
      in {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            arduino-cli
            avrdude
            minicom
            picocom
            git
          ];

          shellHook = ''
            export ARDUINO_DIRECTORIES_DATA="$PWD/.arduino15"
            export ARDUINO_DIRECTORIES_DOWNLOADS="$PWD/.arduino-downloads"
            export ARDUINO_DIRECTORIES_USER="$PWD/.arduino-user"

            echo "Arduino dev environment"
            echo "  arduino-cli version: $(arduino-cli version)"
            echo ""
            echo "First-time setup:"
            echo "  arduino-cli core update-index"
            echo "  arduino-cli core install arduino:avr"
            echo ""
            echo "Common commands:"
            echo "  arduino-cli board list"
            echo "  arduino-cli compile --fqbn arduino:avr:uno serial_7seg"
            echo "  arduino-cli upload -p /dev/ttyUSB0 --fqbn arduino:avr:uno serial_7seg"
          '';
        };

        devShells.vision = pkgs.mkShell {
          buildInputs = [
            (pkgs.python3.withPackages (ps: with ps; [
              tkinter
              pip
            ]))
            pkgs.git
          ];

          # Lets manylinux pip wheels (mediapipe, opencv-python, Pillow) run on NixOS
          shellHook = ''
            export NIX_LD="${pkgs.stdenv.cc.bintools.dynamicLinker}"
            export NIX_LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath wheelLibs}"
            export LD_LIBRARY_PATH="$NIX_LD_LIBRARY_PATH''${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
            me="$(id -un)"
            for grp in dialout video; do
              if ! id -nG "$me" 2>/dev/null | grep -qw "$grp"; then
                echo "WARNING: user '$me' is not in group '$grp' (needed for /dev/ttyUSB0 and the camera)."
                echo "  Add to /etc/nixos/configuration.nix and rebuild:"
                echo "    users.users.$me.extraGroups = [ \"dialout\" \"video\" ];"
                echo "  Or paste the udev snippet from finger_counter/README.md"
              fi
            done
            echo "FingerCounter dev environment"
            echo "  ./finger_counter/setup-dev.sh    # create .venv and install deps (first time)"
            echo "  .venv/bin/python finger_counter/finger_counter_app.py"
            echo "  nix run nixpkgs#arduino-cli -- upload -p /dev/ttyUSB0 --fqbn arduino:avr:uno serial_7seg"
          '';
        };
      });
}
